from __future__ import annotations

import unicodedata

# SQL equivalente a :func:`normalize_text`. 
# O `{alias}` é o nome da tabela/alias cujo DS_CONTA será lido.
NORM_DS_CONTA_SQL = "lower(strip_accents(trim({alias}.DS_CONTA)))"


def normalize_text(ds_conta: str) -> str:
    """Normaliza a descrição de conta (DS_CONTA) para comparação:
    minúsculo, sem acento, sem espaço nas pontas.

    É o que permite casar ``"Patrimônio Líquido Consolidado"`` contra o esperado
    ``"patrimonio liquido consolidado"`` na resolução de contas por texto, sem enumerar as 
    variações encontradas nos resultados da CVM.

    Remove somente acento, não pontuação: ``"Lucro/Prejuízo"`` vira ``"lucro/prejuizo"`` 
    e mantém a barra.

    Args:
        ds_conta: descrição de conta como vem da CVM.

    Returns:
        ds_conta_normalized: ``"  PATRIMÔNIO LÍQUIDO "`` → ``"patrimonio liquido"``.
    """
    text = unicodedata.normalize("NFKD", ds_conta)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip().lower()