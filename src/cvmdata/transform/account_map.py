"""Mapeamento CD_CONTA → componente semântico, parametrizado por perfil de empresa.

Cada empresa resolve um ``profile_id`` (``"default"`` | ``"banking"``) antes de
mapear contas.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ACCOUNT_MAP: dict[str, dict[str, str]] = {
    "default": {
        # BPA — Balanço Patrimonial Ativo
        "1": "ativo_total",
        "1.01": "ativo_circulante",
        "1.01.01": "caixa_equivalentes",
        "1.01.02": "aplicacoes_financeiras",
        "1.01.04": "estoques",
        "1.02": "ativo_nao_circulante",
        "1.02.01": "realizavel_longo_prazo",
        # BPP — Balanço Patrimonial Passivo
        "2": "passivo_total",
        "2.01": "passivo_circulante",
        "2.01.04": "emprestimos_cp",
        "2.02": "passivo_nao_circulante",
        "2.02.01": "emprestimos_lp",
        "2.03": "patrimonio_liquido",
        # DRE — Demonstração de Resultado
        "3.01": "receita_liquida",
        "3.03": "resultado_bruto",
        "3.05": "ebit",
        "3.06.02": "despesas_financeiras",
        "3.11": "lucro_liquido",
    },
    "banking": {
        # BPA — 1.01 remapeado: valor agregado de caixa (sem subdivisão 1.01.01)
        "1": "ativo_total",
        "1.01": "caixa_equivalentes",
        "1.02": "ativo_nao_circulante",
        # BPP — 2.01/2.02 com semântica de mensuração (valor justo / custo
        # amortizado), não de prazo; PL vive na cauda (2.07)
        "2": "passivo_total",
        "2.01": "passivo_circulante",
        "2.02": "passivo_nao_circulante",
        "2.07": "patrimonio_liquido",
        # DRE — 3.02 remapeado: despesa de intermediação financeira
        "3.01": "receita_liquida",
        "3.03": "resultado_bruto",
        "3.02": "despesas_financeiras",
        "3.11": "lucro_liquido",
        # Ausentes (sem equivalente em banking): aplicacoes_financeiras, estoques,
        # realizavel_longo_prazo, emprestimos_cp, emprestimos_lp, ebit.
    },
}

# Códigos da cauda de resultado e de patrimônio líquido. Não pertencem ao
# ACCOUNT_MAP: a posição desliza por empresa. São carregados explicitamente 
# para ficarem disponíveis ao fetch e resolvidos por texto normalizado (dre_tail_map).
DRE_TAIL_CODES: list[str] = [
    "3.05",
    "3.06",
    "3.07",
    "3.08",
    "3.09",
    "3.10",
    "3.10.01",
    "3.11",
]

BPP_TAIL_CODES: list[str] = [
    "2.07",
    "2.08"
]

ALL_BALANCE_CODES: list[str] = sorted(
    {cd for profile in ACCOUNT_MAP.values() for cd in profile if not cd.startswith("3.")}
)

ALL_DRE_CODES: list[str] = sorted(
    {cd for profile in ACCOUNT_MAP.values() for cd in profile if cd.startswith("3.")}
    | set(DRE_TAIL_CODES)
)

ALL_ACCOUNT_CODES: list[str] = sorted(
    set(ALL_BALANCE_CODES) | set(ALL_DRE_CODES) | set(BPP_TAIL_CODES)
)


def get_component(cd_conta: str, profile_id: str = "default") -> str | None:
    """Retorna o componente semântico para um CD_CONTA, dado o perfil da empresa.

    Falls back para o mapa ``"default"`` se ``profile_id`` for desconhecido.
    Retorna ``None`` se a conta não estiver mapeada nesse perfil. Nunca lança exceção.
    """
    profile_map = ACCOUNT_MAP.get(profile_id, ACCOUNT_MAP["default"])
    return profile_map.get(cd_conta)