## Configuração (`.env`) para personalizar o Pipeline

Copie `.env.example` e ajuste conforme necessário:

```bash
cp .env.example .env
```

| Variável | Padrão | Descrição |
|---|---|---|
| `DATA_DIR` | `data` | Diretório raiz dos dados |
| `DB_PATH` | `data/db/cvmdata.duckdb` | Caminho do arquivo DuckDB |
| `YEARS` | `2021,2022,2023,2024,2025` | Anos a baixar/processar |
| `ITR_URL` | URL CVM ITR | Base URL dos ZIPs de ITR |
| `DFP_URL` | URL CVM DFP | Base URL dos ZIPs de DFP |
| `B3_TICKERS_DIR` | `data/b3_tickers` | Diretório com `page_*.json` gerados pelo projeto externo |
| `B3_TICKERS_GLOB` | `page_*.json` | Padrão de arquivos JSON a processar |
