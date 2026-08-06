"""Configurações do projeto via pydantic-settings.

Carrega variáveis do arquivo .env (ou ambiente) com prefixo CVM_.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from cvmdata.utils.database import sanitize_duckdb_memory_limit, sanitize_duckdb_threads
from cvmdata.utils.years import parse_years


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CVM_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # ── years ──────────────────────────────────────────────────────────────

    years: str = "2021,2022,2023,2024,2025"

    @property
    def years_list(self) -> list[int]:
        return parse_years(self.years)


    # ── Pipeline ──────────────────────────────────────────────────────────────

    force_download: bool = False
    verbose: bool = False
    cnpj: str | None = None

    itr_url_template: str = (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
    )
    dfp_url_template: str = (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
    )

    def itr_url(self, year: int) -> str:
        return self.itr_url_template.format(year=year)

    def dfp_url(self, year: int) -> str:
        return self.dfp_url_template.format(year=year)

    # URLs dos arquivos cadastrais da CVM
    cad_meta_url: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/META/meta_cad_cia_aberta.txt"
    cad_csv_url: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"


    # ── Database ──────────────────────────────────────────────────────────────

    duckdb_memory_limit: str | None = None
    duckdb_threads: int | None = None

    @property
    def sanitized_duckdb_memory_limit(self) -> str | None:
        return sanitize_duckdb_memory_limit(self.duckdb_memory_limit)
        
    @property
    def sanitized_duckdb_threads(self) -> int | None:
        return sanitize_duckdb_threads(self.duckdb_threads)


    # ── Data Directories ──────────────────────────────────────────────────────────────

    # Diretório raiz dos dados (relativo ao CWD ou absoluto)
    data_dir: Path = Path("data")

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def itr_dir(self) -> Path:
        return self.raw_dir / "itr"

    @property
    def dfp_dir(self) -> Path:
        return self.raw_dir / "dfp"

    @property
    def cad_dir(self) -> Path:
        return self.raw_dir / "cad"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db" / "cvmdata.duckdb"


    # ── B3 Directories ──────────────────────────────────────────────────────────────

    b3_tickers_glob: str = "page_*.json"

    @property
    def b3_tickers_dir(self) -> Path:
        return self.data_dir / "b3_tickers"


settings = Settings()
