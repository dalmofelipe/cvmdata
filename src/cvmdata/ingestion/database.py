"""Abertura da conexão DuckDB.

O schema — todo ``CREATE TABLE`` e a reconciliação de bancos legados — vive em
:mod:`cvmdata.ingestion.schema`. Aqui fica só como o banco é aberto.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)


def get_connection(
    *,
    db_path: Path,
    memory_limit: str | None = None,
    threads: int | None = None,
) -> duckdb.DuckDBPyConnection:
    """Retorna conexão DuckDB persistente. Cria o arquivo se não existir.

    Por padrão NÃO fixa memory_limit/threads — deixa o DuckDB usar sua
    heurística nativa (memory_limit ≈ 80% da RAM; threads = nº de cores).
    Isso favorece cargas grandes (CVM_YEARS amplo) sem exigir tuning manual.

    Os parâmetros memory_limit/threads (default: CVM_DUCKDB_MEMORY_LIMIT /
    CVM_DUCKDB_THREADS via Settings) permitem override explícito quando
    necessário.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    if memory_limit:
        conn.execute(f"SET memory_limit = '{memory_limit}'")
    if threads:
        conn.execute(f"SET threads = {int(threads)}")

    logger.debug(
        "Conectado a %s (memory_limit=%s, threads=%s)",
        db_path,
        memory_limit or "default(duckdb)",
        threads or "default(duckdb)",
    )
    return conn