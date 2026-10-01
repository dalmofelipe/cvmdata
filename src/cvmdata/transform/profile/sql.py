"""Renderização SQL das regras de assinatura e da precedência de perfil.

A precedência mora aqui, e não no consumidor, para que a regra de classificação
e o texto que a identifica em ``rule_applied`` não possam divergir do SQL que
produz a classificação. As funções são puras: recebem regras e expressões, devolvem
SQL e uma lista de params — nenhuma delas abre conexão nem conhece tabela
cadastral.

Precedência aplicada:

1. assinatura estrutural (:data:`cvmdata.transform.profile.rules.SIGNATURE_RULES`);
2. override de governança em ``setor_profile_map``;
3. :data:`~cvmdata.transform.profile.models.FALLBACK_PROFILE`.
"""

from __future__ import annotations

from cvmdata.transform.profile.models import FALLBACK_PROFILE, SignatureRule

# Equivalente SQL de text_map.normalize_text: minúsculo, sem acento, sem espaços
# nas pontas. ``starts_with`` (função, não operador LIKE) é usado no lugar de
# ``LIKE 'x%'`` para que o rótulo seja comparado literalmente, sem curingas.
NORM_DS_CONTA_SQL = "lower(strip_accents(trim({alias}.DS_CONTA)))"


def _sql_str(value: str) -> str:
    """Literal SQL entre aspas simples, com escape."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def signature_predicate(
    rule: SignatureRule,
    cnpj_expr: str,
    params: list[object],
) -> str:
    """Renderiza o predicado SQL de ``rule`` e anexa seus params a ``params``.

    Um ``EXISTS`` por sinal, correlacionado por CNPJ. A ordem dos params segue a
    ordem dos sinais — quem consome precisa montar a lista de Criteria na mesma
    ordem em que os predicados são concatenados.

    Args:
        rule: Regra a renderizar.
        cnpj_expr: Expressão SQL com o CNPJ da linha sendo classificada.
        params: Lista de params accumulating — mutada in place.

    Returns:
        Predicado SQL booleano.
    """
    clauses: list[str] = []
    for index, signal in enumerate(rule.signals):
        alias = f"sig{index}"
        clauses.append(
            f"EXISTS ("
            f"  SELECT 1 FROM {signal.table} {alias}"
            f"  WHERE {alias}.CNPJ_CIA = {cnpj_expr}"
            f"    AND {alias}.CD_CONTA = ?"
            f"    AND {signal.sql_condition(NORM_DS_CONTA_SQL.format(alias=alias))}"
            f")"
        )
        params.extend([signal.cd_conta, signal.ds_conta_normalized])
    return " AND ".join(clauses)


def signature_flags_sql(
    rules: list[SignatureRule],
    cnpj_expr: str,
    params: list[object],
) -> tuple[str, list[str]]:
    """Renderiza as flags de assinatura como SELECT list de uma CTE.

    Cada regra vira um booleano ``sig_<i>``, o que evita avaliar o mesmo
    ``EXISTS`` duas vezes — uma para ``profile_id`` e outra para
    ``rule_applied`` — e mantém os params em uma posição só.

    Args:
        rules: Regras a avaliar.
        cnpj_expr: Expressão SQL com o CNPJ da linha em classificação.
        params: Lista de params — mutada in place.

    Returns:
        Tupla ``(select_list, aliases)`` com um alias por regra, na ordem de
        ``rules``.
    """
    flags: list[str] = []
    aliases: list[str] = []
    for index, rule in enumerate(rules):
        alias = f"sig_{index}"
        flags.append(f"{signature_predicate(rule, cnpj_expr, params)} AS {alias}")
        aliases.append(alias)
    return ", ".join(flags), aliases


def classification_sql(
    rules: list[SignatureRule],
    signature_exprs: list[str],
    setor_expr: str,
    in_cadastro_expr: str,
    override_expr: str,
) -> tuple[str, str]:
    """Renderiza as expressões de ``profile_id`` e ``rule_applied``.

    1. assinatura estrutural (na ordem de ``rules``);
    2. override setorial explícito (``setor_profile_map``);
    3. ``default`` — distinguindo cadastro ausente de setor vazio ou não
       mapeado, porque são causas diferentes com conserto diferente.

    Args:
        rules: Regras, na mesma ordem de ``signature_exprs``.
        signature_exprs: Booleano por regra, tipicamente as colunas da CTE de
            flags.
        setor_expr: Expressão SQL com o setor (pode ser NULL).
        in_cadastro_expr: Expressão SQL que é NULL quando o CNPJ não está no
            cadastro — o nome ``cad.cnpj_cia`` serve.
        override_expr: Expressão SQL com o ``profile_id`` do override, ou NULL.

    Returns:
        Tupla ``(profile_id_sql, rule_applied_sql)``.
    """
    signatures = list(zip(signature_exprs, rules))

    if signatures:
        profile_branches = " ".join(
            f"WHEN {expr} THEN {_sql_str(rule.profile_id)}" for expr, rule in signatures
        )
        applied_branches = " ".join(
            f"WHEN {expr} THEN {_sql_str(rule.rule_applied)}" for expr, rule in signatures
        )
    else:
        profile_branches = ""
        applied_branches = ""

    return (
        f"CASE {profile_branches} ELSE COALESCE({override_expr}, {_sql_str(FALLBACK_PROFILE)}) END",
        f"CASE {applied_branches}"
        f" WHEN {override_expr} IS NOT NULL"
        f"  THEN 'override:setor:' || trim({setor_expr})"
        f" WHEN {in_cadastro_expr} IS NULL THEN 'default:sem_cadastro:sem_assinatura'"
        f" WHEN {setor_expr} IS NULL OR trim({setor_expr}) = '' THEN 'default:setor_vazio'"
        f" ELSE 'default:setor_nao_mapeado:' || trim({setor_expr})"
        f" END",
    )