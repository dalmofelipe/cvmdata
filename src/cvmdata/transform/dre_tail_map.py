"""Resolução textual da cauda de resultado.

A posição dos componentes da cauda (``resultado_antes_tributos``,
``imposto_renda_csll``, ``resultado_liquido_continuadas``,
``ajuste_descontinuadas``) desliza conforme a estrutura reportada por cada
empresa — ``CD_CONTA`` fixo não a resolve. Este módulo resolve pelo texto
normalizado de ``DS_CONTA``, restrito a contas de 1-2 níveis (evita colisão
com subcontas de detalhe de 3+ níveis, confirmadas como ruído na investigação.

Independe de perfil: vale igualmente para ``default`` e ``banking``.
"""

from __future__ import annotations

import unicodedata

DRE_TAIL_TEXT_MAP: dict[str, str] = {
    "resultado antes dos tributos sobre o lucro": "resultado_antes_tributos",
    "imposto de renda e contribuicao social sobre o lucro": "imposto_renda_csll",
    "resultado liquido das operacoes continuadas": "resultado_liquido_continuadas",
    "lucro/prejuizo liquido das operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido de operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido das operacoes descontinuadas": "ajuste_descontinuadas",
}


def normalize_ds_conta(ds_conta: str) -> str:
    """lower + strip_accents + trim — mesma normalização da investigação empírica."""
    text = unicodedata.normalize("NFKD", ds_conta)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip().lower()


def get_tail_component(ds_conta: str, cd_conta: str) -> str | None:
    """Resolve componente da cauda de resultado por texto normalizado.

    Restrito a CD_CONTA com no máximo 2 pontos (ex: '3.10.01') — contas de
    3+ níveis (ex: '3.10.01.01') são subcontas de detalhe e ficam fora
    de escopo por desenho, não por omissão.
    """
    if cd_conta.count(".") > 2:
        return None
    return DRE_TAIL_TEXT_MAP.get(normalize_ds_conta(ds_conta))