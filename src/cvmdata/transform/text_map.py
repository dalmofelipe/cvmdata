"""Resolução de componente por rótulo, quando a posição não resolve.

``account_map`` mapeia ``CD_CONTA`` → componente. Ele falha quando a posição
desliza: o mesmo componente aparece em códigos diferentes entre empresas e
entre anos da mesma empresa.

Duas formas de deslocamento, ambas reais no universo:

- **entre perfis** — o patrimônio líquido está em ``2.03`` no layout padrão e em
  ``2.07``/``2.08`` no layout financeiro. No universo, 538 empresas reportam em
  ``2.03``, 19 em ``2.07`` e 16 em ``2.08``: 573 > 562, ou seja, pelo menos 11
  empresas mudam de código entre períodos. Nenhum mapa por código resolve
  isso, nem um ciente de perfil, porque o drift é temporal.
- **dentro do perfil** — o mesmo código significa coisas diferentes: ``2.03`` é
  "Patrimônio Líquido" para 5 empresas financeiras, "Provisões" para 19 e
  "Passivos Financeiros ao Custo Amortizado" para 16. Só o rótulo separa.

O rótulo, ao contrário, é estável: "Patrimônio Líquido Consolidado" é a única
formulação de PL em todo o universo, em qualquer código. Este módulo resolve
por ele, e é independente de perfil — vale para ``default``, ``banking`` e
qualquer perfil futuro que reporte os mesmos rótulos.
"""

from __future__ import annotations

import unicodedata

# Equivalente SQL de normalize_text, para a classificação rodar em SQL.
NORM_DS_CONTA_SQL = "lower(strip_accents(trim({alias}.DS_CONTA)))"

DRE_TAIL_TEXT_MAP: dict[str, str] = {
    "resultado antes dos tributos sobre o lucro": "resultado_antes_tributos",
    "imposto de renda e contribuicao social sobre o lucro": "imposto_renda_csll",
    "resultado liquido das operacoes continuadas": "resultado_liquido_continuadas",
    "lucro/prejuizo liquido das operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido de operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido das operacoes descontinuadas": "ajuste_descontinuadas",
}

# Chave é o prefixo do rótulo normalizado. Prefixo em vez de igualdade porque
# "Patrimônio Líquido" sem "Consolidado" é variação previsível e não vale um
# segundo mapa; hoje o universo só produz a forma com "Consolidado", de modo que
# as duas regras são equivalentes — a diferença só aparece em ano futuro.
BPP_PL_TEXT_MAP: dict[str, str] = {
    "patrimonio liquido": "patrimonio_liquido",
}


def normalize_text(ds_conta: str) -> str:
    """lower + strip_accents + trim — mesma normalização da investigação empírica."""
    text = unicodedata.normalize("NFKD", ds_conta)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip().lower()


def _resolve_prefix_map(
    text_map: dict[str, str], 
    ds_conta: str
) -> str | None:
    """Mai prefixo que casa wins — 'patrimonio liquido consolidado' casa o prefixo
    'patrimonio liquido'. Mais específico primeiro evita que um prefixo curto
    capture o rótulo de outro componente."""
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

    Sem restrição de profundidade: o PL aparece em 2.03, 2.07 e 2.08, todos de
    um ponto, e o rótulo é inequívoco. O chamador deve tentar primeiro
    ``account_map.get_component`` e só cair aqui quando o código não resolveu —
    é o que impede '2.03 Provisões' (19 bancos) de virar patrimônio.
    """
    return _resolve_prefix_map(BPP_PL_TEXT_MAP, ds_conta)