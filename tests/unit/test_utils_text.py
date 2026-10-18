"""Testes unitários da normalização de rótulo contábil.

Cobre a paridade Python/SQL de :mod:`cvmdata.utils.text` — a invariante de que a
classificação (SQL) e o fetch de indicadores (Python) comparam o mesmo rótulo.
"""

from __future__ import annotations

import duckdb
import pytest

from cvmdata.utils.text import NORM_DS_CONTA_SQL, normalize_text

pytestmark = pytest.mark.unit


# Rótulos reais do universo: acento, caixa alta, espaço nas pontas, e os dois
# formatos de "Passivos Financeiros" que o prefixo precisa cobrir.
AMOSTRAS = [
    "Caixa e Equivalentes de Caixa",
    "Passivos Financeiros Avaliados ao Valor Justo",
    "Passivos Financeiros ao Custo Amortizado",
    "Patrimônio Líquido Consolidado",
    "  RESULTADO ANTES DOS TRIBUTOS SOBRE O LUCRO  ",
    "Lucro/Prejuízo Líquido Consolidado do Período",
    "Ativo Circulante",
    "Imposto de Renda e Contribuição Social sobre o Lucro",
]


@pytest.mark.parametrize("rotulo", AMOSTRAS)
def test_parity_holds_on_real_labels(rotulo: str) -> None:
    """As duas normalizações precisam concordar, rótulo por rótulo.

    Executa a expressão SQL contra um DuckDB real e compara com o Python. O
    desacordo aqui quebraria em silêncio: a classificação deixaria de casar com a
    empresa, e ela cairia no ``default`` sem erro nenhum.
    """
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (DS_CONTA VARCHAR)")
        conn.execute("INSERT INTO t VALUES (?)", [rotulo])
        from_sql = conn.execute(
            f"SELECT {NORM_DS_CONTA_SQL.format(alias='t')} FROM t"
        ).fetchone()[0]
    finally:
        conn.close()

    assert from_sql == normalize_text(rotulo)


def test_parity_preserves_punctuation():
    """A barra de "Lucro/Prejuízo" sobrevive: é separador, não ruído.

    Removê-la faria "Lucro/Prejuízo" e "Lucro Prejuízo" colidirem.
    """
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (DS_CONTA VARCHAR)")
        conn.execute("INSERT INTO t VALUES ('Lucro/Prejuízo Líquido')")
        from_sql = conn.execute(
            f"SELECT {NORM_DS_CONTA_SQL.format(alias='t')} FROM t"
        ).fetchone()[0]
    finally:
        conn.close()

    assert from_sql == "lucro/prejuizo liquido"


def test_normalize_text_handles_empty_string():
    """Rótulo vazio é plausível em conta sem descrição, e não deve estourar."""
    assert normalize_text("") == ""