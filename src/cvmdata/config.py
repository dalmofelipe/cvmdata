"""Configurações do projeto via pydantic-settings.

Carrega variáveis do arquivo .env (ou ambiente) com prefixo CVM_.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CVM_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Anos a processar (separados por vírgula na env: "2021,2022,2023,2024,2025")
    years: list[int] = [2021, 2022, 2023, 2024, 2025]

    # URLs base dos ZIPs da CVM
    itr_url_template: str = (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
    )
    dfp_url_template: str = (
        "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
    )

    # URLs dos arquivos cadastrais da CVM
    cad_meta_url: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/META/meta_cad_cia_aberta.txt"
    cad_csv_url: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"

    def itr_url(self, year: int) -> str:
        return self.itr_url_template.format(year=year)

    def dfp_url(self, year: int) -> str:
        return self.dfp_url_template.format(year=year)

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
    
    # Integração com dados de tickers da B3
    b3_tickers_glob: str = "page_*.json"

    @property
    def b3_tickers_dir(self) -> Path:
        return self.data_dir / "b3_tickers"


# instância global — importar com `from cvmdata.config import settings`
settings = Settings()
