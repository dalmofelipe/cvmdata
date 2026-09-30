"""Testes da convenção de nomenclatura das tabelas DuckDB.

Dois guards:

- ``LEGACY_CLEAN_RE`` impede que os nomes pré-padronização voltem a aparecer;
- ``DECLARATION_SITES`` fixa onde um nome pode continuar escrito por extenso.

O padrão é montado a partir das constantes de propósito: escrever um nome
literal aqui faria o teste acusar a si mesmo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cvmdata.ingestion.catalog import CATALOG
from cvmdata.ingestion.tables import (
    B3_TICKERS,
    BALANCE_CLEAN_TABLES,
    BPA_CLEAN,
    BPP_CLEAN,
    CAD_CIA_ABERTA_RAW,
    CLASSIFICATION_CURATION_EVENTS,
    CLEAN_SUFFIX,
    CLEAN_TABLES,
    COMPANY_CLASSIFICATION,
    COMPOSICAO_CAPITAL,
    DRE_CLEAN,
    INDICATORS,
    RAW_PREFIX,
    SETOR_PROFILE_MAP,
    clean_table_name,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

LEGACY_CLEAN_RE = re.compile(rf"{RAW_PREFIX}\w+{CLEAN_SUFFIX}")

# Único arquivo autorizado a citar os nomes antigos: é onde a descarte do banco
# e a ausência de aliases ficam documentados.
LEGACY_DOC_ALLOWLIST = {"docs/tabelas.md"}

# Nomes que passam a ser centralizados. O literal só é aceito no CREATE TABLE
# que o declara — em qualquer outro SQL, o nome vem da constante.
CENTRALIZED_NAMES = (
    CAD_CIA_ABERTA_RAW,
    COMPANY_CLASSIFICATION,
    CLASSIFICATION_CURATION_EVENTS,
    SETOR_PROFILE_MAP,
    INDICATORS,
    B3_TICKERS,
    COMPOSICAO_CAPITAL,
    BPA_CLEAN,
    BPP_CLEAN,
    DRE_CLEAN,
)

# database.py é o único módulo de produção com DDL (CREATE TABLE) — lá o literal
# é o sítio de declaração e deve permanecer.
DECLARATION_SITES = {"src/cvmdata/ingestion/database.py"}

# O guard vale para código de produção. Em tests/ o literal é proposital: um
# fixture que declara `CREATE TABLE bpa_clean` com a constante passaria mesmo
# se o código de produção usasse outro nome — o literal é a asserção.
_GUARDED_DIRS = ("src", "scripts")

# O qualifier opcional de schema (main., db., "main".) é pulado para capturar
# o nome da tabela — senão `FROM main.indicators` casaria "main" e escaparia.
_SQL_RE = re.compile(
    r"\b(?:FROM|INTO|JOIN|UPDATE|TRUNCATE|TABLE)\s+[\"'`\s]*"
    r"(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:[\"'`]?\w+[\"'`]?\.)?"
    r"(?P<name>\w+)",
    re.IGNORECASE,
)

_SCAN_SUFFIXES = (".py", ".md")


def _scan(relative_dir: str) -> list[tuple[str, int, str]]:
    """Ocorrências do padrão legado em ``relative_dir`` (relativas à raiz)."""
    found: list[tuple[str, int, str]] = []
    for path in sorted((ROOT / relative_dir).rglob("*")):
        if path.suffix not in _SCAN_SUFFIXES or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in LEGACY_DOC_ALLOWLIST:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_CLEAN_RE.search(line):
                found.append((rel, lineno, line.strip()))
    return found


# ── clean_table_name ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw_table", "expected"),
    [
        ("raw_bpa", BPA_CLEAN),
        ("raw_bpp", BPP_CLEAN),
        ("raw_dre", DRE_CLEAN),
    ],
)
def test_clean_table_name_derives_expected_names(raw_table: str, expected: str) -> None:
    assert clean_table_name(raw_table) == expected


@pytest.mark.parametrize("raw_table", ["bpa", "bpp", "dre", "clean", "", "BPA"])
def test_clean_table_name_rejects_names_without_raw_prefix(raw_table: str) -> None:
    """Sem o guard, ``"bpa"`` viraria ``"bpa_clean"`` e colidiria com a real."""
    with pytest.raises(ValueError, match="não é uma tabela raw_"):
        clean_table_name(raw_table)


def test_clean_table_name_rejects_prefix_without_statement() -> None:
    """``"raw_"`` não identifica nenhum demonstrativo — não pode virar ``"_clean"``."""
    with pytest.raises(ValueError, match="não é uma tabela raw_"):
        clean_table_name(RAW_PREFIX)


# ── Constantes ────────────────────────────────────────────────────────────────


def test_clean_tables_hold_the_canonical_names() -> None:
    """Contrato de nomenclatura — se isto mudar, a padronização foi desfeita."""
    assert CLEAN_TABLES == ("bpa_clean", "bpp_clean", "dre_clean")
    assert BALANCE_CLEAN_TABLES == frozenset({BPA_CLEAN, BPP_CLEAN})
    assert BPA_CLEAN != BPP_CLEAN and BPA_CLEAN != DRE_CLEAN


def test_clean_tables_are_not_prefixed_as_raw() -> None:
    """Tabelas normalizadas não carregam o prefixo reservado ao dado bruto."""
    for name in CLEAN_TABLES:
        assert not name.startswith(RAW_PREFIX)
        assert name.endswith(CLEAN_SUFFIX)


def test_catalog_is_the_source_of_truth_for_raw_table_names() -> None:
    """O DDL de init_schema deve criar exatamente as tabelas do catálogo."""
    import duckdb

    from cvmdata.ingestion.database import init_schema

    conn = duckdb.connect(":memory:")
    try:
        init_schema(conn)
        created = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert {ds.table for ds in CATALOG.values()} <= created


# ── Guard anti-regressão ──────────────────────────────────────────────────────


def test_no_legacy_clean_names_in_source_or_tests() -> None:
    """Nenhuma referência aos nomes antigos pode voltar a src/ ou tests/."""
    found = _scan("src") + _scan("tests")
    assert not found, "nomes legados reintroduzidos:\n" + "\n".join(
        f"  {rel}:{lineno}: {line}" for rel, lineno, line in found
    )


def test_legacy_clean_names_only_documented_in_tables_doc() -> None:
    """Fora de docs/tabelas.md, nem docs/ nem o README podem citar os nomes antigos."""
    found = _scan("docs")
    readme = ROOT / "README.md"
    if readme.exists():
        for lineno, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_CLEAN_RE.search(line):
                found.append(("README.md", lineno, line.strip()))

    assert not found, "nomes legados fora de docs/tabelas.md:\n" + "\n".join(
        f"  {rel}:{lineno}: {line}" for rel, lineno, line in found
    )


def test_centralized_names_are_not_hardcoded_in_sql() -> None:
    """Em código de produção, SQL referencia a constante — não o literal.

    Cobre ``src/`` e ``scripts/``. Duas exceções, ambas declaration sites:
    o ``CREATE TABLE`` em database.py, que é onde a tabela é declarada. Em
    ``tests/`` o literal é intencional (ver ``_GUARDED_DIRS``).
    """
    violations: list[str] = []

    for module_dir in _GUARDED_DIRS:
        for path in sorted((ROOT / module_dir).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in DECLARATION_SITES:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for match in _SQL_RE.finditer(line):
                    if match.group("name") in CENTRALIZED_NAMES:
                        violations.append(f"  {rel}:{lineno}: {line.strip()}")

    assert not violations, (
        "nomes de tabela escritos à mão em SQL; use cvmdata.ingestion.tables:\n"
        + "\n".join(violations)
    )


@pytest.mark.parametrize(
    "line",
    [
        "SELECT * FROM indicators",
        "SELECT * FROM indicators AS i JOIN b3_tickers b ON true",
        "DELETE FROM main.indicators WHERE cnpj_cia = ?",
        'INSERT INTO "indicators" (v) VALUES (?)',
        "TRUNCATE indicators",
        "SELECT * FROM\n    dre_clean",
    ],
)
def test_sql_regex_captures_the_table_not_the_schema(line: str) -> None:
    """O guard precisa enxergar o nome da tabela em todas essas formas.

    Regressão de `FROM main.indicators`: o qualificador de schema fazia o
    regex casar "main" e o teste passava com o literal no código.
    """
    captured = {m.group("name") for m in _SQL_RE.finditer(line)}
    assert captured & set(CENTRALIZED_NAMES), f"não capturou nome de tabela em: {line!r}"


def test_every_centralized_name_has_a_declaration() -> None:
    """Toda constante centralizada precisa ter onde a tabela é declarada.

    Duas vias de declaração distintas:

    - as tabelas de esquema têm ``CREATE TABLE`` em ``ingestion/database.py``;
    - as ``*_clean`` são derivadas em runtime, por ``CREATE OR REPLACE TABLE``
      nos templates de ``transform/normalize.py``.

    Fecha o buraco de centralizar um nome que nenhuma DDL cria.
    """
    ddl = (ROOT / "src/cvmdata/ingestion/database.py").read_text(encoding="utf-8")
    declared = {
        m.group(1)
        for m in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", ddl, re.IGNORECASE
        )
    }
    normalize_py = (ROOT / "src/cvmdata/transform/normalize.py").read_text(encoding="utf-8")
    derived = bool(re.search(r"CREATE\s+OR\s+REPLACE\s+TABLE", normalize_py, re.IGNORECASE))

    declarable = set(CENTRALIZED_NAMES) - set(CLEAN_TABLES)
    missing = declarable - declared
    assert not missing, f"constantes sem CREATE TABLE correspondente: {sorted(missing)}"
    assert derived, "transform/normalize.py deixou de criar as tabelas *_clean"
