"""Testes unitários da resolução estrutural de perfil.

Nível: metadados das regras e o SQL que elas renderizam. O comportamento —
qual empresa cai em qual perfil — é coberto em
``tests/integration/test_info_cad.py``, contra as clean.

O SQL vive em :mod:`cvmdata.transform.info_cad.sql`; o que se testa aqui é que
a regra vira ``EXISTS ... AND ...`` na ordem certa e que os params acompanham.
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError

import pytest

from cvmdata.ingestion.tables import TB_BPA_CLEAN, TB_BPP_CLEAN
from cvmdata.transform.info_cad.sql import (
    classification_sql,
    rule_conditions_sql,
    rule_matches_sql,
)
from cvmdata.transform.profile import (
    FALLBACK_PROFILE,
    STRUCTURAL_RULES,
    RuleCondition,
    StructuralRule,
)

pytestmark = pytest.mark.unit

BANKING_RULE = STRUCTURAL_RULES[0]


def _params_and_flags(rules=None):
    params: list[object] = []
    flags = rule_matches_sql(rules if rules is not None else STRUCTURAL_RULES, params)
    return params, flags


# ── metadados da regra ────────────────────────────────────────────────────────


def test_banking_rule_requires_both_sides():
    """A regra de banco precisa dos dois sinais: cada um sozinho tem falso
    positivo (BPP financeiro com BPA padrão é layout híbrido real)."""
    tables = [s.clean_table for s in BANKING_RULE.conditions]
    assert tables == [TB_BPA_CLEAN, TB_BPP_CLEAN]
    assert [s.cd_conta for s in BANKING_RULE.conditions] == ["1.01", "2.01"]
    assert BANKING_RULE.profile_id == "banking"


def test_rule_applied_is_stable_identifier():
    assert BANKING_RULE.rule_applied == "structure:banking:bpa.1.01+bpp.2.01"


def test_conditions_are_immutable():
    with pytest.raises(FrozenInstanceError):
        BANKING_RULE.conditions[0].cd_conta = "9.99"  # type: ignore[misc]


# ── predicate ─────────────────────────────────────────────────────────────────


def test_predicate_conjoins_one_exists_per_signal():
    predicate = rule_conditions_sql(BANKING_RULE, [])

    assert predicate.count("EXISTS") == 2
    assert " AND " in predicate
    assert f"FROM {TB_BPA_CLEAN}" in predicate
    assert f"FROM {TB_BPP_CLEAN}" in predicate


def test_predicate_correlates_conditions_by_cnpj():
    """O alias `u` não é configuração: é o contrato com a CTE `sig` de
    `SQL_CLASSIFY`. Este teste fixa o contrato dos dois lados."""
    predicate = rule_conditions_sql(BANKING_RULE, [])

    assert predicate.count("= u.CNPJ_CIA") == 2


def test_predicate_normalizes_label_like_python_side():
    """A classificação roda em SQL e o fetch roda em Python; as duas
    normalizações precisam ser a mesma Regra, em ponto."""
    predicate = rule_conditions_sql(BANKING_RULE, [])

    assert predicate.count("lower(strip_accents(trim(") == 2


def test_exact_signal_uses_equality():
    signal = RuleCondition(clean_table=TB_BPA_CLEAN, cd_conta="1.01", ds_conta_normalized="caixa")
    params: list[object] = []

    predicate = rule_conditions_sql(StructuralRule("p", (signal,)), params)

    assert "= ?" in predicate
    assert "starts_with" not in predicate
    assert params == ["1.01", "caixa"]


def test_prefix_signal_uses_starts_with_not_like():
    """``starts_with`` compara literalmente; ``LIKE 'x%'`` trataria ``_`` da
    query como coringa."""
    signal = RuleCondition(
        clean_table=TB_BPP_CLEAN,
        cd_conta="2.01",
        ds_conta_normalized="passivos financeiros",
        starts_with=True,
    )
    params: list[object] = []

    predicate = rule_conditions_sql(StructuralRule("p", (signal,)), params)

    assert "starts_with(" in predicate
    assert "LIKE" not in predicate.upper()
    assert params == ["2.01", "passivos financeiros"]


def test_params_follow_signal_order():
    params, _ = _params_and_flags()

    assert params == [
        "1.01",
        "caixa e equivalentes de caixa",
        "2.01",
        "passivos financeiros",
    ]


# ── flags ─────────────────────────────────────────────────────────────────────


def test_flags_name_one_column_per_rule():
    _, flags = _params_and_flags()

    assert "AS rule_0_match" in flags


def test_flags_supports_multiple_rules():
    rules = [
        BANKING_RULE,
        StructuralRule(
            profile_id="insurance",
            conditions=(
                RuleCondition(TB_BPA_CLEAN, "1.01", "ativos intangiveis"),
            ),
        ),
    ]
    params, flags = _params_and_flags(rules)

    assert "AS rule_0_match" in flags
    assert "AS rule_1" in flags
    assert len(params) == 6


def test_empty_rules_emit_valid_select_expression():
    params: list[object] = []

    flags = rule_matches_sql([], params)

    assert flags == "TRUE AS no_rule_match"
    assert params == []


# ── classificação ─────────────────────────────────────────────────────────────


def test_profile_id_uses_signature_then_default():
    """Sem override, são duas vias: a assinatura ou o fallback."""
    profile_sql, _ = classification_sql(STRUCTURAL_RULES)

    assert profile_sql == f"CASE WHEN rm.rule_0_match THEN 'banking' ELSE '{FALLBACK_PROFILE}' END"


@pytest.mark.parametrize(
    "trecho",
    [
        "WHEN rm.rule_0_match THEN 'structure:banking:bpa.1.01+bpp.2.01'",
        "WHEN c.CNPJ_CIA IS NULL THEN 'default:sem_cadastro:sem_assinatura'",
        "THEN 'default:setor_vazio'",
        "ELSE 'default:setor:'",
    ],
)
def test_rule_applied_vocabulary(trecho):
    """Cada causa tem texto próprio: 'setor vazio', 'setor preenchido' e 'sem
    cadastro' têm consertos diferentes e precisam ser distinguíveis."""
    _, applied_sql = classification_sql(STRUCTURAL_RULES)

    assert trecho in applied_sql


def test_rule_applied_records_the_sector():
    """O setor entra no rótulo, não na decisão — é o que permite auditar
    *qual* empresa caiu no default e por quê."""
    _, applied_sql = classification_sql(STRUCTURAL_RULES)

    assert "|| trim(c.setor_ativ)" in applied_sql


def test_classification_sql_without_rules_still_valid():
    """Lista vazia de regras degrada para o fallback sem gerar SQL inválido —
    é o que mantém o módulo utilizável se STRUCTURAL_RULES for esvaziada."""
    profile_sql, applied_sql = classification_sql([])

    assert profile_sql.startswith("CASE  ELSE")
    assert applied_sql.startswith("CASE  WHEN")


def test_case_refers_to_exactly_the_flags_emitted():
    """`rule_match_flags_sql` e `classification_sql` derivam os nomes de
    `rule_match_alias`. Antes o caller montava a lista, e um nome errado só aparecia
    como erro de SQL em runtime; agora a concordância é testável."""
    rules = [
        BANKING_RULE,
        StructuralRule(
            profile_id="insurance",
            conditions=(RuleCondition(TB_BPA_CLEAN, "1.01", "ativos intangiveis"),),
        ),
    ]
    _, flags = _params_and_flags(rules)
    profile_sql, applied_sql = classification_sql(rules)

    emitted = {f"AS rule_{i}_match" for i in range(len(rules))}
    for fragment in (profile_sql, applied_sql):
        referenced = {
            f"AS {alias.split('.', 1)[1]}"
            for alias in re.findall(r"\b(rm\.rule_\d+_match)\b", fragment)
        }
        assert referenced, fragment
        assert referenced <= emitted, (referenced, emitted)
