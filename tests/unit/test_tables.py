"""Testes da convenção de nomenclatura das tabelas DuckDB.

O guard ``LEGACY_CLEAN_RE`` impede que os nomes pré-padronização voltem a
aparecer no código. O padrão é montado a partir das constantes de propósito:
escrever o nome legado literalmente aqui faria o teste acusar a si mesmo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cvmdata.ingestion.tables import (
    BALANCE_CLEAN_TABLES,
    BPA_CLEAN,
    BPP_CLEAN,
    CLEAN_SUFFIX,
    CLEAN_TABLES,
    DRE_CLEAN,
    RAW_PREFIX,
    clean_table_name,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

LEGACY_CLEAN_RE = re.compile(rf"{RAW_PREFIX}\w+{CLEAN_SUFFIX}")

# Único arquivo autorizado a citar os nomes antigos: é onde a descarte do banco
# e a ausência de aliases ficam documentados.
LEGACY_DOC_ALLOWLIST = {"docs/tabelas.md"}

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
