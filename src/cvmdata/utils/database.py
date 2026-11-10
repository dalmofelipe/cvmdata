from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import duckdb

logger = logging.getLogger(__name__)

_MEMORY_LIMIT_REGEX = re.compile(r"^[1-9]\d*(\.\d+)?\s*(MB|GB|%)$", re.IGNORECASE)


@dataclass(frozen=True)
class DuckDBValidationError(ValueError):
    """Exceção customizada para parâmetros inválidos do DuckDB."""

    param_name: str
    value: object
    reason: str

    def __str__(self) -> str:
        return f"Parâmetro inválido '{self.param_name}'={self.value!r}: {self.reason}"


def sanitize_duckdb_memory_limit(memory_limit: str | None) -> str | None:
    """Valida o formato do limite de memória para o DuckDB."""
    if memory_limit is None:
        return None

    value_clean = memory_limit.strip()

    if not _MEMORY_LIMIT_REGEX.match(value_clean):
        raise DuckDBValidationError(
            param_name="memory_limit",
            value=memory_limit,
            reason="Use um número positivo seguido de MB, GB ou % (ex: '2GB', '500MB', '80%').",
        )

    return value_clean.upper()


def sanitize_duckdb_threads(threads: int | None) -> int | None:
    """Valida a quantidade de threads para o DuckDB."""
    if threads is None:
        return None

    if threads <= 0:
        raise DuckDBValidationError(
            param_name="threads",
            value=threads,
            reason="O número de threads deve ser maior que 0.",
        )

    return threads


# ── Introspecção do catálogo ──────────────────────────────────────────────────


def existing_tables(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Nomes de todas as tabelas do schema ``main``."""
    return {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }


def table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    """Se ``table`` existe no schema ``main``."""
    return table in existing_tables(conn)


def column_names(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Nomes das colunas de uma ``table``, na ordem de definição."""
    rows = conn.execute(
        "SELECT column_name FROM duckdb_columns() WHERE table_name = ?",
        [table],
    ).fetchall()
    return [row[0] for row in rows]


# ── Escrita ───────────────────────────────────────────────────────────────────


def replace_table_contents(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    insert_sql: str,
    params: list[object] | None = None,
) -> None:
    """Substitui todo o conteúdo de ``table`` por um ``INSERT``, em transação.

    ### Args
        **conn**: Conexão DuckDB.
        **table**: Tabela a reconstruir.
        **insert_sql**: Statement ``INSERT`` já renderizado, apontando para ``table``.
        **params**: Params do ``insert_sql``, na mesma ordem dos ``?``.
    """
    conn.execute("BEGIN")
    try:
        conn.execute(f"DELETE FROM {table}")
        conn.execute(insert_sql, params or [])
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise