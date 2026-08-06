## Configuração (`.env`) para personalizar o Pipeline

Copie `.env.example` e ajuste conforme necessário:

```bash
cp .env.example .env
```


### Variáveis de Ambiente

Todas as configurações são lidas via `pydantic-settings` com prefixo `CVM_`.
O arquivo `.env` na raiz do projeto é carregado automaticamente.

| Variável | Tipo | Default | Descrição |
|---|---|---|---|
| `CVM_YEARS` | `string` | `2021,2022,2023,2024,2025` | Anos a processar. Aceita lista por vírgula ou range inclusivo (`2021:2025`, `2021-2025`). |
| `CVM_DATA_DIR` | `Path` | `data` | Diretório raiz dos dados |
| `CVM_FORCE_DOWNLOAD` | `bool` | `False` | Forçar re-download mesmo com cache |
| `CVM_VERBOSE` | `bool` | `False` | Logging detalhado (DEBUG) |
| `CVM_CNPJ` | `str` | `None` | Filtrar cálculo de indicadores por CNPJ |
| `CVM_ITR_URL_TEMPLATE` | `str` | (URL CVM) | Template URL dos ZIPs ITR |
| `CVM_DFP_URL_TEMPLATE` | `str` | (URL CVM) | Template URL dos ZIPs DFP |
| `CVM_CAD_META_URL` | `str` | (URL CVM) | URL do metadata cadastral |
| `CVM_CAD_CSV_URL` | `str` | (URL CVM) | URL do CSV cadastral |
| `CVM_DUCKDB_MEMORY_LIMIT` | `str \| None` | `None` | Override do memory_limit do DuckDB. None = heurística nativa (~80% RAM). |
| `CVM_DUCKDB_THREADS` | `int \| None` | `None` | Override do nº de threads do DuckDB. None = heurística nativa (nº de cores). |


## Fluxo de Execução

```
.env / environment
    │
    ▼
config.py (Settings singleton)
    │
    ▼
pipeline/__main__.py (entry point)
    │
    ▼
pipeline/orchestrator.py: run_full()
    │
    ├── Step: ingestion/downloader.py  (download ZIPs)
    ├── Step: ingestion/downloader.py  (download cadastro)
    ├── Step: ingestion/loader.py      (load B3 tickers)
    ├── Step: ingestion/loader.py      (load cadastro)
    ├── Step: ingestion/loader.py      (load CSVs → raw_*)
    └── Step: transform/info_cad.py    (classificar setores)
    ├── Step: transform/normalize.py   (raw_* → *_clean)
    ├── Step: transform/indicators.py  (calcular indicadores)
    │
    ▼
PipelineReport → stdout
```
