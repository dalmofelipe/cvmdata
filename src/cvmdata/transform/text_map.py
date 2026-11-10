from __future__ import annotations

from cvmdata.transform.account_map import BPP_PL_CODES
from cvmdata.utils.text import normalize_text

DRE_TAIL_TEXT_MAP: dict[str, str] = {
    "resultado antes dos tributos sobre o lucro": "resultado_antes_tributos",
    "imposto de renda e contribuicao social sobre o lucro": "imposto_renda_csll",
    "resultado liquido das operacoes continuadas": "resultado_liquido_continuadas",
    "lucro/prejuizo liquido das operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido de operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido das operacoes descontinuadas": "ajuste_descontinuadas",
}

BPP_PL_TEXT_MAP: dict[str, str] = {
    "patrimonio liquido": "patrimonio_liquido",
}


def _resolve_prefix_map(
    text_map: dict[str, str], 
    ds_conta: str
) -> str | None:
    """
    Resolve prefixo: 
    'patrimonio liquido consolidado' casa o prefixo 'patrimonio liquido'.
    
    Mais específico primeiro evita que um prefixo curto capture o rótulo de 
    outro componente.
    """
    normalized = normalize_text(ds_conta)
    for prefix in sorted(text_map, key=len, reverse=True):
        if normalized.startswith(prefix):
            return text_map[prefix]
    return None


def resolve_tail(
    ds_conta: str,
    cd_conta: str,
    *,
    max_depth: int = 2
) -> str | None:
    """Resolve componente da cauda de resultado por texto normalizado.

    Restrito a CD_CONTA com no máximo ``max_depth`` pontos (ex: '3.10.01') —
    contas de 3+ níveis (ex: '3.10.01.01') são subcontas de detalhe e ficam
    fora de escopo por desenho, não por omissão. O limite vem de investigação:
    '3.10.01.01' na DOTZ traz texto de IR corrente e '3.01.01' no BTG traz
    'Resultado líquido com instrumentos financeiros', ambos ruído de
    detalhamento.
    """
    if cd_conta.count(".") > max_depth:
        return None
    return DRE_TAIL_TEXT_MAP.get(normalize_text(ds_conta))


def resolve_pl(
    ds_conta: str, 
    cd_conta: str
) -> str | None:
    """Resolve patrimônio líquido por texto normalizado.

    O código precisa ser uma das posições conhecidas do BPP; o rótulo confirma
    que a linha nessa posição é realmente patrimônio líquido. O chamador deve
    tentar primeiro ``account_map.get_component`` e só cair aqui quando o
    código não resolveu — é o que impede ``2.03 Provisões`` (19 bancos) de
    virar patrimônio.
    """
    if cd_conta not in BPP_PL_CODES:
        return None
    return _resolve_prefix_map(BPP_PL_TEXT_MAP, ds_conta)