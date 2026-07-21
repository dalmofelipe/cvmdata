"""Download e extração dos ZIPs da CVM.

Fluxo por source+ano:
  1. Baixa o ZIP para data/raw/{source}/{source}_cia_aberta_{year}.zip
  2. Extrai apenas os CSVs relevantes para data/raw/{source}/{year}/

Fluxo de Informação Cadastral:
  download_info_cad() baixa meta_cad_cia_aberta.txt + cad_cia_aberta.csv
  para data/raw/cad/.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import httpx

from cvmdata.ingestion.catalog import CATALOG

logger = logging.getLogger(__name__)


def _should_extract(filename: str) -> bool:
    """Retorna True se o arquivo CSV corresponde a algum dataset do catálogo."""
    fname = filename.lower()
    if not fname.endswith(".csv"):
        return False
    return any(ds.pattern in fname for ds in CATALOG.values())


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
    """Extrai CSVs dos datasets do catálogo de *zip_path* em *dest_dir*.

    Retorna lista dos CSVs extraídos.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if _should_extract(m)]
        for member in members:
            # Evitar path traversal: usar só o basename
            basename = Path(member).name
            target = dest_dir / basename
            with zf.open(member) as src, target.open("wb") as dst:
                dst.write(src.read())
            extracted.append(target)

    logger.info("%d CSVs extraídos em %s", len(extracted), dest_dir)
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


# ── Informação Cadastral CVM ──────────────────────────────────────────────────────────────

# Nomes dos arquivos cadastrais oficiais
CAD_META_FILENAME = "meta_cad_cia_aberta.txt"
CAD_CSV_FILENAME = "cad_cia_aberta.csv"


def download_info_cad(
    cad_meta_url: str,
    cad_csv_url: str,
    cad_dir: Path,
    *,
    force: bool = False,
) -> tuple[Path, Path]:
    """Baixa os arquivos cadastrais da CVM para *cad_dir*.

    Returns:
        (meta_path, csv_path) — caminhos locais dos arquivos.

    Idempotente: pula arquivos já existentes a menos que *force=True*.
    Falha de download não corrompe arquivo previamente baixado.
    """
    cad_dir.mkdir(parents=True, exist_ok=True)
    meta_path = cad_dir / CAD_META_FILENAME
    csv_path = cad_dir / CAD_CSV_FILENAME

    for url, dest in [(cad_meta_url, meta_path), (cad_csv_url, csv_path)]:
        if dest.exists() and not force:
            logger.info("Arquivo cadastral já existe, pulando: %s", dest.name)
            continue
        # Baixar para temporário e só mover ao final (evita corromper arquivo prévio)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            logger.info("Baixando %s …", url)
            with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
                r.raise_for_status()
                downloaded = 0
                with tmp.open("wb") as fh:
                    for chunk in r.iter_bytes(chunk_size=65_536):
                        fh.write(chunk)
                        downloaded += len(chunk)
            mb = downloaded / 1_048_576
            logger.info("  %.1f MB → %s", mb, dest.name)
            tmp.replace(dest)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

    return meta_path, csv_path
