"""Testes unitários da resolução estrutural de perfil.

Nível: renderização de SQL e metadados das regras. O comportamento —
qual empresa cai em qual perfil — é coberto em
``tests/integration/test_info_cad.py``, contra as clean.
"""

from __future__ import annotations

import pytest

from cvmdata.ingestion.tables import TB_BPA_CLEAN, TB_BPP_CLEAN
from cvmdata.transform.profile import (
    FALLBACK_PROFILE,
    SIGNATURE_RULES,
    SignatureRule,
    SignatureSignal,
    classification_sql,
    signature_flags_sql,
    signature_predicate,
)

pytestmark = pytest.mark.unit

BANKING_RULE = SIGNATURE_RULES[0]


def _params_and_flags(rules=None):
    params: list[object] = []
    flags, aliases = signature_flags_sql(
        rules if rules is not None else SIGNATURE_RULES,
        cnpj_expr="u.CNPJ_CIA",
        params=params,
    )
    return params, flags, aliases


# ── metadados da regra ────────────────────────────────────────────────────────


def test_banking_rule_requires_both_sides():
    """A regra de banco precisa dos dois sinais: cada um sozinho tem falso
    positivo (BPP financeiro com BPA padrão é layout híbrido real)."""
    tables = [s.table for s in BANKING_RULE.signals]
    assert tables == [TB_BPA_CLEAN, TB_BPP_CLEAN]
    assert [s.cd_conta for s in BANKING_RULE.signals] == ["1.01", "2.01"]
    assert BANKING_RULE.profile_id == "banking"


def test_rule_applied_is_stable_identifier():
    assert BANKING_RULE.rule_applied == "structure:banking:bpa.1.01+bpp.2.01"


def test_signals_are_immutable():
    with pytest.raises(Exception):
        BANKING_RULE.signals[0].cd_conta = "9.99"  # type: ignore[misc]


# ── predicate ─────────────────────────────────────────────────────────────────


def test_predicate_conjoins_one_exists_per_signal():
    predicate = signature_predicate(BANKING_RULE, "u.CNPJ_CIA", [])

    assert predicate.count("EXISTS") == 2
    assert " AND " in predicate
    assert f"FROM {TB_BPA_CLEAN}" in predicate
    assert f"FROM {TB_BPP_CLEAN}" in predicate


def test_predicate_correlates_signals_by_cnpj():
    predicate = signature_predicate(BANKING_RULE, "u.CNPJ_CIA", [])

    assert predicate.count("= u.CNPJ_CIA") == 2


def test_predicate_normalizes_label_like_python_side():
    """A classificação roda em SQL e o fetch roda em Python; as duas
    normalizações precisam ser a mesma Regra, em ponto."""
    predicate = signature_predicate(BANKING_RULE, "u.CNPJ_CIA", [])

    assert predicate.count("lower(strip_accents(trim(") == 2


def test_exact_signal_uses_equality():
    signal = SignatureSignal(table=TB_BPA_CLEAN, cd_conta="1.01", ds_conta_normalized="caixa")
    params: list[object] = []

    predicate = signature_predicate(SignatureRule("p", (signal,)), "c", params)

    assert "= ?" in predicate
    assert "starts_with" not in predicate
    assert params == ["1.01", "caixa"]


def test_prefix_signal_uses_starts_with_not_like():
    """``starts_with`` compara literalmente; ``LIKE 'x%'`` trataria ``_`` da
    query como coringa."""
    signal = SignatureSignal(
        table=TB_BPP_CLEAN,
        cd_conta="2.01",
        ds_conta_normalized="passivos financeiros",
        starts_with=True,
    )
    params: list[object] = []

    predicate = signature_predicate(SignatureRule("p", (signal,)), "c", params)

    assert "starts_with(" in predicate
    assert "LIKE" not in predicate.upper()
    assert params == ["2.01", "passivos financeiros"]


def test_params_follow_signal_order():
    params, _, _ = _params_and_flags()

    assert params == [
        "1.01",
        "caixa e equivalentes de caixa",
        "2.01",
        "passivos financeiros",
    ]


# ── flags ─────────────────────────────────────────────────────────────────────


def test_flags_returns_one_alias_per_rule():
    _, _, aliases = _params_and_flags()

    assert aliases == ["sig_0"]


def test_flags_supports_multiple_rules():
    rules = [
        BANKING_RULE,
        SignatureRule(
            profile_id="insurance",
            signals=(
                SignatureSignal(TB_BPA_CLEAN, "1.01", "ativos intangiveis"),
            ),
        ),
    ]
    params, flags, aliases = _params_and_flags(rules)

    assert aliases == ["sig_0", "sig_1"]
    assert flags.count("AS sig_") == 2
    assert len(params) == 6


# ── classificação ─────────────────────────────────────────────────────────────


def test_profile_id_precedence_puts_signature_first():
    profile_sql, _ = classification_sql(
        SIGNATURE_RULES,
        signature_exprs=["s.sig_0"],
        setor_expr="c.setor_ativ",
        in_cadastro_expr="c.CNPJ_CIA",
        override_expr="spm.profile_id",
    )

    assert profile_sql.index("WHEN s.sig_0 THEN 'banking'") < profile_sql.index(
        f"ELSE COALESCE(spm.profile_id, '{FALLBACK_PROFILE}')"
    )


def test_profile_id_falls_back_to_default_without_override():
    profile_sql, _ = classification_sql(
        SIGNATURE_RULES,
        signature_exprs=["s.sig_0"],
        setor_expr="c.setor_ativ",
        in_cadastro_expr="c.CNPJ_CIA",
        override_expr="NULL",
    )

    assert profile_sql.endswith(f"ELSE COALESCE(NULL, '{FALLBACK_PROFILE}') END")


@pytest.mark.parametrize(
    "trecho",
    [
        "WHEN s.sig_0 THEN 'structure:banking:bpa.1.01+bpp.2.01'",
        "WHEN spm.profile_id IS NOT NULL  THEN 'override:setor:'",
        "WHEN c.CNPJ_CIA IS NULL THEN 'default:sem_cadastro:sem_assinatura'",
        "THEN 'default:setor_vazio'",
        "ELSE 'default:setor_nao_mapeado:'",
    ],
)
def test_rule_applied_vocabulary(trecho):
    """Cada causa tem texto próprio: 'setor vazio', 'setor não mapeado' e 'sem
    cadastro' têm consertos diferentes e precisam ser distinguíveis."""
    _, applied_sql = classification_sql(
        SIGNATURE_RULES,
        signature_exprs=["s.sig_0"],
        setor_expr="c.setor_ativ",
        in_cadastro_expr="c.CNPJ_CIA",
        override_expr="spm.profile_id",
    )

    assert trecho in applied_sql


def test_classification_sql_without_rules_still_valid():
    """Lista vazia de regras degrada para override/default sem gerar SQL inválido
    — é o que mantém o módulo utilizável se SIGNATURE_RULES for esvaziada."""
    profile_sql, applied_sql = classification_sql(
        [],
        signature_exprs=[],
        setor_expr="c.setor_ativ",
        in_cadastro_expr="c.CNPJ_CIA",
        override_expr="spm.profile_id",
    )

    assert profile_sql.startswith("CASE  ELSE")
    assert applied_sql.startswith("CASE  WHEN")