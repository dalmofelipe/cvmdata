"""Download e extração dos ZIPs da CVM.

Fluxo por source+ano:
  1. Baixa o ZIP para data/raw/{source}/{source}_cia_aberta_{year}.zip
  2. Extrai apenas os CSVs relevantes para data/raw/{source}/{year}/
"""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Todos os demonstrativos disponíveis nos ZIPs da CVM (para referência)
DEMOS: list[str] = ["BPA", "BPP", "DFC_MD", "DFC_MI", "DMPL", "DRA", "DRE", "DVA"]

# Subset necessário para calcular os 7 indicadores planejados
# [ADR 2026-02-20]: DFC_MD, DFC_MI, DMPL, DRA, DVA descartados — nenhum
# indicador planejado requer contas desses demonstrativos.
INDICATOR_DEMOS: frozenset[str] = frozenset({"BPA", "BPP", "DRE"})

# Arquivos que NÃO são demonstrativos — ignorados no load
_SKIP_PATTERNS: tuple[str, ...] = (
    "composicao_capital",
    "parecer",
    # arquivo-índice sem sufixo de scope (ex: itr_cia_aberta_2024.csv)
)


def _is_demo_csv(filename: str) -> bool:
    """Retorna True se o arquivo é um CSV de demonstrativo (com scope con/ind)."""
    fname = filename.lower()
    if not fname.endswith(".csv"):
        return False
    if any(skip in fname for skip in _SKIP_PATTERNS):
        return False
    # Deve conter _con_ e ser um demo em escopo (INDICATOR_DEMOS) — _ind_ ignorado
    if "_con_" not in fname:
        return False
    return any(f"_{demo.lower()}_" in fname for demo in INDICATOR_DEMOS)


def download_zip(url: str, dest: Path, *, force: bool = False) -> Path:
    """Baixa *url* para *dest* com streaming.

    Idempotente: pula o download se o arquivo já existir, a menos que *force=True*.
    """
    if dest.exists() and not force:
        logger.info("ZIP já existe, pulando: %s", dest.name)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Baixando %s …", url)

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            downloaded = 0
            with dest.open("wb") as fh:
                for chunk in r.iter_bytes(chunk_size=65_536):
                    fh.write(chunk)
                    downloaded += len(chunk)
        mb = downloaded / 1_048_576
        logger.info("  %.1f MB baixados → %s", mb, dest)
    except httpx.HTTPStatusError as exc:
        logger.error("Erro HTTP %s ao baixar %s", exc.response.status_code, url)
        raise

    return dest


def extract_zip(zip_path: Path, dest_dir: Path) -> list[Path]:
    """Extrai CSVs de demonstrativos de *zip_path* em *dest_dir*.

    Ignora arquivos não-demo (composicao_capital, parecer, etc.).
    Retorna lista dos CSVs extraídos.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if _is_demo_csv(m)]
        for member in members:
            # Evitar path traversal: usar só o basename
            basename = Path(member).name
            target = dest_dir / basename
            with zf.open(member) as src, target.open("wb") as dst:
                dst.write(src.read())
            extracted.append(target)

    logger.info("%d CSVs de demonstrativos extraídos em %s", len(extracted), dest_dir)
    return extracted


def download_source_year(
    source: str,
    year: int,
    url_template: str,
    raw_dir: Path,
    *,
    force: bool = False,
) -> list[Path]:
    """Download + extração para um *source* (itr|dfp) e *year*.

    Estrutura criada:
        raw_dir/{source}/{source}_cia_aberta_{year}.zip   ← ZIP
        raw_dir/{source}/{year}/*.csv                      ← CSVs extraídos
    """
    zip_name = f"{source}_cia_aberta_{year}.zip"
    zip_path = raw_dir / source / zip_name
    csv_dir = raw_dir / source / str(year)

    url = url_template.format(year=year)
    download_zip(url, zip_path, force=force)
    return extract_zip(zip_path, csv_dir)
