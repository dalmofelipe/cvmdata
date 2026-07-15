"""Testes unitários do normalize (Phase 2 — T019)."""

from __future__ import annotations

import duckdb
import pytest

from cvmdata.ingestion.db import init_schema
from cvmdata.transform.normalize import normalize_all, normalize_table

# ── Helpers ─────────────────────────────────────────────────────────────────


def _insert_bpa(
    db: duckdb.DuckDBPyConnection,
    *,
    cnpj: str = "00.000.000/0001-91",
    dt_refer: str = "2024-03-31",
    versao: int = 1,
    cd_conta: str = "1.01",
    vl_conta: float = 1000.0,
    ordem_exerc: str = "ÚLTIMO",
    cd_cvm: str = "001000",
) -> None:
    """Insere uma linha mínima na tabela raw_bpa (BPA tem 14+3 colunas)."""
    db.execute(
        """
        INSERT INTO raw_bpa VALUES (
            ?, ?, ?, 'EMPRESA TEST', ?,
            'DF Consolidado - BPA', 'REAL', 'UNIDADE',
            ?, ?,
            ?, 'Conta Teste', ?, 'S',
            'itr', 2024, 'con'
        )
        """,
        [cnpj, dt_refer, versao, cd_cvm, ordem_exerc, dt_refer, cd_conta, vl_conta],
    )


# ── Testes: normalize_table ──────────────────────────────────────────────────


def test_normalize_dedup_keeps_latest_versao(db: duckdb.DuckDBPyConnection) -> None:
    """Duas linhas com mesmo (CNPJ, DT_REFER, CD_CONTA) e VERSAO 1/2 → apenas VERSAO 2."""
    init_schema(db)
    _insert_bpa(db, versao=1, vl_conta=1000.0)
    _insert_bpa(db, versao=2, vl_conta=2000.0)

    count = normalize_table("raw_bpa", db)

    assert count == 1
    row = db.execute("SELECT VERSAO, VL_CONTA FROM raw_bpa_clean").fetchone()
    assert row[0] == 2
    assert float(row[1]) == pytest.approx(2000.0)


def test_normalize_dedup_returns_correct_count(db: duckdb.DuckDBPyConnection) -> None:
    """Retorna número de linhas no resultado limpo."""
    init_schema(db)
    # 2 contas distintas, cada uma com duplicata de versao
    _insert_bpa(db, cd_conta="1.01", versao=1)
    _insert_bpa(db, cd_conta="1.01", versao=2)
    _insert_bpa(db, cd_conta="1.02", versao=1)
    _insert_bpa(db, cd_conta="1.02", versao=3)

    count = normalize_table("raw_bpa", db)

    assert count == 2


def test_normalize_removes_penultimo(db: duckdb.DuckDBPyConnection) -> None:
    """Linhas com ORDEM_EXERC = 'PENÚLTIMO' devem ser descartadas."""
    init_schema(db)
    _insert_bpa(db, cd_conta="1.01", ordem_exerc="ÚLTIMO")
    _insert_bpa(db, cd_conta="1.01", ordem_exerc="PENÚLTIMO")

    normalize_table("raw_bpa", db)

    remaining = db.execute("SELECT ORDEM_EXERC FROM raw_bpa_clean").fetchall()
    assert len(remaining) == 1
    assert remaining[0][0] == "ÚLTIMO"


def test_normalize_no_penultimo_in_clean(db: duckdb.DuckDBPyConnection) -> None:
    """Após normalização, tabela limpa nunca contém ORDEM_EXERC != 'ÚLTIMO'."""
    init_schema(db)
    for ordem in ("ÚLTIMO", "PENÚLTIMO", "ÚLTIMO"):
        _insert_bpa(db, cd_conta=f"1.0{ordem[:2]}", ordem_exerc=ordem)

    normalize_table("raw_bpa", db)

    count_bad = db.execute(
        "SELECT COUNT(*) FROM raw_bpa_clean WHERE ORDEM_EXERC != 'ÚLTIMO'"
    ).fetchone()[0]
    assert count_bad == 0


def test_normalize_dt_refer_is_date(db: duckdb.DuckDBPyConnection) -> None:
    """DT_REFER deve ser tipo DATE na tabela limpa."""
    init_schema(db)
    _insert_bpa(db)

    normalize_table("raw_bpa", db)

    col_type = db.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'raw_bpa_clean'
          AND column_name = 'DT_REFER'
        """
    ).fetchone()[0]
    assert col_type.upper() == "DATE"


def test_normalize_vl_conta_is_decimal(db: duckdb.DuckDBPyConnection) -> None:
    """VL_CONTA deve ser tipo DECIMAL após normalização."""
    init_schema(db)
    _insert_bpa(db, vl_conta=12345.678)

    normalize_table("raw_bpa", db)

    col_type = db.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'raw_bpa_clean'
          AND column_name = 'VL_CONTA'
        """
    ).fetchone()[0]
    assert "DECIMAL" in col_type.upper()


def test_normalize_cd_cvm_stripped_of_leading_zeros(db: duckdb.DuckDBPyConnection) -> None:
    """CD_CVM = '001023' deve se tornar inteiro 1023 após normalização."""
    init_schema(db)
    _insert_bpa(db, cd_cvm="001023")

    normalize_table("raw_bpa", db)

    cd_cvm_val = db.execute("SELECT CD_CVM FROM raw_bpa_clean").fetchone()[0]
    assert cd_cvm_val == 1023


def test_normalize_cd_cvm_non_numeric_becomes_null(db: duckdb.DuckDBPyConnection) -> None:
    """CD_CVM não numérico deve virar NULL (TRY_CAST) sem exception."""
    init_schema(db)
    _insert_bpa(db, cd_cvm="ABC")

    normalize_table("raw_bpa", db)

    cd_cvm_val = db.execute("SELECT CD_CVM FROM raw_bpa_clean").fetchone()[0]
    assert cd_cvm_val is None


def test_normalize_idempotent(db: duckdb.DuckDBPyConnection) -> None:
    """Executar normalize_table duas vezes não deve duplicar linhas."""
    init_schema(db)
    _insert_bpa(db, versao=1)
    _insert_bpa(db, versao=2)

    normalize_table("raw_bpa", db)
    normalize_table("raw_bpa", db)

    count = db.execute("SELECT COUNT(*) FROM raw_bpa_clean").fetchone()[0]
    assert count == 1


def test_normalize_empty_table(db: duckdb.DuckDBPyConnection) -> None:
    """Tabela raw vazia deve produzir tabela clean vazia (count = 0)."""
    init_schema(db)

    count = normalize_table("raw_bpa", db)

    assert count == 0
    # A tabela clean deve existir mesmo vazia
    exists = db.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'raw_bpa_clean'"
    ).fetchone()[0]
    assert exists == 1


# ── Testes: normalize_all ────────────────────────────────────────────────────


def test_normalize_all_processes_all_raw_tables(db: duckdb.DuckDBPyConnection) -> None:
    """normalize_all deve processar todas as tabelas raw_* (BPA, BPP, DRE)."""
    init_schema(db)
    _insert_bpa(db)

    results = normalize_all(db)

    # Deve retornar ao menos raw_bpa (as outras existem e ficam com 0 linhas)
    assert "raw_bpa" in results
    assert results["raw_bpa"] == 1


def test_normalize_all_returns_empty_when_no_raw_tables(db: duckdb.DuckDBPyConnection) -> None:
    """Sem tabelas raw_*, normalize_all retorna dict vazio."""
    # Não cria schema — banco in-memory limpo
    results = normalize_all(db)
    assert results == {}


def test_normalize_all_keys_match_raw_tables(db: duckdb.DuckDBPyConnection) -> None:
    """normalize_all deve retornar chaves com os nomes exatos das tabelas raw_*."""
    init_schema(db)

    results = normalize_all(db)

    # init_schema cria raw_bpa, raw_bpp, raw_dre
    assert set(results.keys()) == {"raw_bpa", "raw_bpp", "raw_dre"}


# ── Helpers DRE ──────────────────────────────────────────────────────────────


def _insert_dre(
    db: duckdb.DuckDBPyConnection,
    *,
    cnpj: str = "00.000.000/0001-91",
    dt_refer: str = "2024-09-30",
    versao: int = 1,
    cd_conta: str = "3.01",
    vl_conta: float = 369.561,
    ordem_exerc: str = "ÚLTIMO",
    dt_ini_exerc: str = "2024-01-01",
    dt_fim_exerc: str = "2024-09-30",
    cd_cvm: str = "009512",
    source: str = "itr",
) -> None:
    """Insere uma linha mínima na tabela raw_dre (DRE tem 18 colunas incluindo DT_INI_EXERC)."""
    db.execute(
        """
        INSERT INTO raw_dre VALUES (
            ?, ?, ?, 'EMPRESA TEST', ?,
            'DF Consolidado - DRE', 'REAL', 'UNIDADE',
            ?, ?, ?,
            ?, 'Conta Teste', ?, 'S',
            ?, 2024, 'con'
        )
        """,
        [
            cnpj,
            dt_refer,
            versao,
            cd_cvm,
            ordem_exerc,
            dt_ini_exerc,
            dt_fim_exerc,
            cd_conta,
            vl_conta,
            source,
        ],
    )


# ── Testes US1: normalização DRE ─────────────────────────────────────────────


def test_normalize_dre_retains_ytd(db: duckdb.DuckDBPyConnection) -> None:
    """T006 — DRE com duas linhas (YTD vs trimestral) → clean retém apenas YTD.

    YTD tem DT_INI_EXERC mais antigo (2024-01-01) e vale 369M.
    Trimestral tem DT_INI_EXERC mais recente (2024-07-01) e vale 129M.
    Após normalização, raw_dre_clean deve ter apenas a linha com VL_CONTA=369.
    """
    init_schema(db)
    # Linha YTD (DT_INI mais antigo — deve vencer)
    _insert_dre(db, dt_ini_exerc="2024-01-01", vl_conta=369.561)
    # Linha trimestral (DT_INI mais recente — deve ser descartada)
    _insert_dre(db, dt_ini_exerc="2024-07-01", vl_conta=129.582)

    count = normalize_table("raw_dre", db)

    assert count == 1
    row = db.execute("SELECT VL_CONTA FROM raw_dre_clean WHERE ORDEM_EXERC = 'ÚLTIMO'").fetchone()
    assert row is not None
    assert float(row[0]) == pytest.approx(369.561)


def test_normalize_dre_preserves_penultimo(db: duckdb.DuckDBPyConnection) -> None:
    """T007 — PENÚLTIMO deve estar presente em raw_dre_clean após normalização DRE."""
    init_schema(db)
    _insert_dre(db, ordem_exerc="ÚLTIMO", vl_conta=369.561, dt_ini_exerc="2024-01-01")
    _insert_dre(db, ordem_exerc="PENÚLTIMO", vl_conta=377.736, dt_ini_exerc="2023-01-01")

    count = normalize_table("raw_dre", db)

    assert count == 2
    ordens = {r[0] for r in db.execute("SELECT DISTINCT ORDEM_EXERC FROM raw_dre_clean").fetchall()}
    assert "ÚLTIMO" in ordens
    assert "PENÚLTIMO" in ordens


def test_normalize_dre_non_january_fiscal_year(db: duckdb.DuckDBPyConnection) -> None:
    """T008 — Empresa com ano fiscal abril: DT_INI=2024-04-01 ganha sobre 2024-07-01."""
    init_schema(db)
    # Fiscal year starts April — YTD from April
    _insert_dre(db, dt_ini_exerc="2024-04-01", vl_conta=200.0)
    # Q trimestral from July
    _insert_dre(db, dt_ini_exerc="2024-07-01", vl_conta=80.0)

    normalize_table("raw_dre", db)

    row = db.execute("SELECT VL_CONTA FROM raw_dre_clean WHERE ORDEM_EXERC = 'ÚLTIMO'").fetchone()
    assert row is not None
    assert float(row[0]) == pytest.approx(200.0)


def test_normalize_balance_still_filters_penultimo(db: duckdb.DuckDBPyConnection) -> None:
    """T009 — Regressão: BPA/BPP continuam descartando PENÚLTIMO (sem mudança de comportamento)."""
    init_schema(db)
    _insert_bpa(db, cd_conta="1.01", ordem_exerc="ÚLTIMO")
    _insert_bpa(db, cd_conta="1.01", ordem_exerc="PENÚLTIMO")

    normalize_table("raw_bpa", db)

    count = db.execute("SELECT COUNT(*) FROM raw_bpa_clean").fetchone()[0]
    assert count == 1

    ordem = db.execute("SELECT ORDEM_EXERC FROM raw_bpa_clean").fetchone()[0]
    assert ordem == "ÚLTIMO"


def test_normalize_dre_q1_single_line(db: duckdb.DuckDBPyConnection) -> None:
    """T010 — DRE Q1 com uma única linha por conta não causa erro (YTD = trimestral)."""
    init_schema(db)
    _insert_dre(
        db,
        dt_refer="2024-03-31",
        dt_ini_exerc="2024-01-01",
        dt_fim_exerc="2024-03-31",
        vl_conta=90.0,
        ordem_exerc="ÚLTIMO",
    )

    count = normalize_table("raw_dre", db)

    assert count == 1
    row = db.execute("SELECT VL_CONTA FROM raw_dre_clean").fetchone()
    assert float(row[0]) == pytest.approx(90.0)
