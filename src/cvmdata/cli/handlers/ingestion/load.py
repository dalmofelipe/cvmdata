# Load handler implementation
from cvmdata.cli.models import LoadInput, Outcome
from cvmdata.config import settings
from cvmdata.ingestion.db import get_connection
from cvmdata.ingestion.loader import load_source_year


def handle(input: LoadInput) -> Outcome[dict[str, int]]:
    """Carrega CSVs extraídos para o DuckDB.

    O loader base retorna contagens por demonstrativo/tabela. Este handler
    agrega o total por origem/ano para manter um payload enxuto no CLI.
    """
    results: dict[str, int] = {}
    
    with get_connection(settings.db_path) as conn:
        for year in input.years:
            for source in ("itr", "dfp"):
                try:
                    table_counts = load_source_year(conn, source, year, settings.raw_dir)
                    if table_counts:
                        results[f"{source}_{year}"] = sum(table_counts.values())
                except Exception as exc:
                    return Outcome.error(f"Falha no load {source}/{year}: {exc}")
    
    if not results:
        return Outcome.warning("Nenhum arquivo CSV encontrado — rode 'download' primeiro")
    
    total = sum(results.values())
    return Outcome.success(
        message=f"{total:,} linhas carregadas em {len(results)} origem(ns)/ano(s)",
        payload=results
    )

