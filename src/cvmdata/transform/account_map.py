"""Mapeamento CD_CONTA → componente semântico para cálculo de indicadores.

Contas verificadas nos dados CVM 2024 (BPA + BPP + DRE).
Match exato apenas — sem inferência de prefixo.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ACCOUNT_MAP: dict[str, str] = {
    # BPA — Balanço Patrimonial Ativo (confirmado nos dados CVM 2024)
    "1":        "ativo_total",
    "1.01":     "ativo_circulante",
    "1.01.01":  "caixa_equivalentes",
    "1.01.02":  "aplicacoes_financeiras",
    "1.01.04":  "estoques",
    "1.02":     "ativo_nao_circulante",
    "1.02.01":  "realizavel_longo_prazo",
    # BPP — Balanço Patrimonial Passivo (confirmado nos dados CVM 2024)
    "2":        "passivo_total",
    "2.01":     "passivo_circulante",
    "2.01.04":  "emprestimos_cp",   # TODO: sector_profile — bancos usam CD_CONTA diferente
    "2.02":     "passivo_nao_circulante",
    "2.02.01":  "emprestimos_lp",   # TODO: sector_profile — bancos usam CD_CONTA diferente
    "2.03":     "patrimonio_liquido",
    # DRE — Demonstração de Resultado (confirmado nos dados CVM 2024)
    "3.01":     "receita_liquida",
    "3.03":     "resultado_bruto",
    "3.05":     "ebit",
    "3.06.02":  "despesas_financeiras",
    "3.11":     "lucro_liquido",
}


def get_component(cd_conta: str) -> str | None:
    """Retorna o nome do componente semântico para um CD_CONTA (match exato).

    Retorna ``None`` se a conta não estiver mapeada e emite WARNING no log.
    Nunca lança exceção.
    """
    component = ACCOUNT_MAP.get(cd_conta)
    if component is None:
        logger.warning("CD_CONTA '%s' não encontrado no ACCOUNT_MAP", cd_conta)
    return component
