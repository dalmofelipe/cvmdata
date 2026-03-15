# cvmdata

Pipeline de dados CVM para cálculo de **indicadores de análise fundamentalista** de companhias abertas brasileiras.

Baixa os demonstrativos contábeis publicados na CVM (BPA, BPP, DRE), ingere no DuckDB, normaliza/deduplica e calcula 15 indicadores por empresa/período — sem dependência de banco de dados externo.

---

## Indicadores calculados

| Categoria | Indicadores |
|---|---|
| **Rentabilidade** | ROE, ROA, Margem Bruta, Margem Operacional, Margem Líquida, Giro do Ativo |
| **Liquidez** | Liquidez Corrente, Liquidez Seca, Liquidez Imediata, Liquidez Geral |
| **Endividamento** | Endividamento Geral, Dívida Bruta, Dívida Líquida, Dívida Líquida/PL, Cobertura de Juros |

Fórmulas completas e mapeamento de contas CVM: [`docs/analise_fundamentalista.md`](docs/analise_fundamentalista.md).

Indicadores de valuation (P/L, P/VPA, DY) dependem de preço de ação e estão documentados em [`docs/valuation_future.md`](docs/valuation_future.md).

---

## Pré-requisitos

| Ferramenta | Versão mínima |
|---|---|
| Python | 3.12 |
| [uv](https://docs.astral.sh/uv/) | 0.5+ |
| make | qualquer |

Conexão com a internet é necessária apenas na etapa de download.

---

## Instalação

```bash
git clone https://github.com/dalmofelipe/cvmdata.git
cd cvmdata
uv sync                  # cria .venv e instala todas as dependências
```

Para desenvolvimento (linter + testes + cobertura):

```bash
uv sync --extra dev
```

---

## Uso rápido

```bash
make all                 # executa download → load → normalize → indicators
```

Ou passo a passo:

```bash
make download            # baixa ZIPs CVM para data/raw/ (ITR + DFP, 2021–2025)
make load                # ingere CSVs em DuckDB (data/db/cvmdata.duckdb)
make normalize           # dedup + cast de tipos → tabelas *_clean
make indicators          # calcula 15 indicadores → tabela indicators
```

No Windows:

```bash
uv run cvmdata download
uv run cvmdata load
uv run cvmdata normalize
uv run cvmdata indicators
```

---

## Comandos CLI

### `cvmdata download`

Baixa os arquivos ZIP da CVM e extrai os CSVs de BPA, BPP e DRE.

```bash
cvmdata download                     # todos os anos configurados (2021–2025)
cvmdata download --year 2024         # apenas 2024
cvmdata download --year 2024 --force # re-baixa mesmo se ZIP já existir
cvmdata download --verbose           # log detalhado
```

### `cvmdata load`

Ingere os CSVs extraídos nas tabelas raw do DuckDB (idempotente: DELETE + INSERT).

```bash
cvmdata load                         # todos os anos disponíveis em data/raw/
cvmdata load --year 2024             # apenas 2024
cvmdata load --verbose
```

### `cvmdata normalize`

Deduplica (mantém `VERSAO` mais recente), filtra `ORDEM_EXERC = 'ÚLTIMO'` e faz cast de tipos.
Cria tabelas `raw_*_clean` no DuckDB.

```bash
cvmdata normalize
```

### `cvmdata indicators`

Calcula os 15 indicadores fundamentalistas para todos os pares `(cnpj_cia, dt_refer)` e persiste em `indicators`.

```bash
cvmdata indicators                           # todas as empresas
cvmdata indicators --cnpj "00.000.000/0001-91"  # apenas BCO Brasil
```

### `cvmdata query`

Exibe os indicadores calculados em tabela formatada.

```bash
cvmdata query --cnpj "00.000.000/0001-91"        # todos os períodos de uma empresa Ex.: BCO BRASIL S.A.
cvmdata query --cnpj "00.000.000/0001-91" --year 2024  # filtrar por ano
cvmdata query                                    # top-10 empresas com mais indicadores
```

### `cvmdata download-cad`

Baixa os arquivos cadastrais oficiais da CVM para `data/raw/cad/`.

```bash
cvmdata download-cad               # baixa meta + CSV cadastral
cvmdata download-cad --force       # re-baixa mesmo se já existir
```

### `cvmdata load-cad`

Faz recarga total do `cad_cia_aberta.csv` na tabela `cad_cia_aberta_raw` do DuckDB.
Valida paridade de linhas CSV × tabela (SC-001) e registra no log.

```bash
cvmdata load-cad
```

### `cvmdata classify-cad`

Classifica todos os CNPJs com `SIT='ATIVO'` pelo `SETOR_ATIV` e persiste em `company_classification`.
CNPJs mapeados recebem `confidence=high`; ambíguos/vazios/não-mapeados recebem `industrial_default` e `confidence=low`.

```bash
cvmdata classify-cad
```

### `cvmdata query-cad`

Consulta classificação cadastral no DuckDB.

```bash
cvmdata query-cad                              # últimas 20 classificações
cvmdata query-cad --cnpj "00.000.000/0001-91" # detalhe de uma empresa
```

### `Scripts`

`list_companies.py` - Listar as empresas presentes no banco de dados cvmdata.

```bash
uv run scripts/list_companies.py
uv run scripts/list_companies.py --limit 50
uv run scripts/list_companies.py --filter petro
```


---

## Estrutura do projeto

```
cvmdata/
├── src/cvmdata/
│   ├── cli.py               # entrypoint Typer (download/load/normalize/indicators/query/cadastro)
│   ├── config.py            # Settings via pydantic-settings (.env)
│   ├── ingestion/
│   │   ├── db.py            # DDLs e get_connection()
│   │   ├── downloader.py    # download streaming + extração ZIP + cadastro CVM
│   │   └── loader.py        # parse CSV → INSERT DuckDB + load_cadastro
│   └── transform/
│       ├── account_map.py   # mapeamento CD_CONTA → componente
│       ├── cadastro.py      # classificação setorial por CNPJ
│       ├── indicators.py    # funções puras + orquestrador calculate_all()
│       └── normalize.py     # dedup + cast de tipos
├── tests/
│   ├── conftest.py          # fixture db (DuckDB in-memory)
│   ├── fixtures/            # CSVs de amostra para testes
│   ├── test_downloader.py
│   ├── test_indicators.py
│   ├── test_loader.py
│   └── test_normalize.py
├── data/
│   ├── raw/{itr,dfp}/{ano}/ # CSVs baixados da CVM
│   ├── raw/cad/             # CSV cadastral da CVM (download-cad)
│   └── db/cvmdata.duckdb    # banco de dados local
├── docs/
│   ├── analise_fundamentalista.md
│   ├── dados_cadastrais.md  # documentação do fluxo cadastral
│   └── valuation_future.md
├── specs/001-cvm-pipeline/  # spec, plan e tasks do pipeline
├── .env.example             # variáveis de ambiente disponíveis
├── Makefile
└── pyproject.toml
```

---

## Configuração (`.env`)

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

---

## Desenvolvimento

```bash
make test                # uv run pytest --tb=short
make lint                # uv run ruff check src/ tests/

# Cobertura de testes
uv run pytest --cov=src/cvmdata/transform --cov-report=term-missing
```

Cobertura atual de `transform/`: **99%** (100/100 testes passando, 2 xfailed esperados).

---

## Notas de implementação

- **Encoding**: arquivos CVM usam `latin-1`; o loader converte automaticamente.
- **Idempotência**: `download` pula ZIPs já existentes (use `--force` para re-baixar); `load` faz DELETE+INSERT por `(source, year, demo, consolidation)`; `load-cad` faz recarga total via CTAS.
- **Deduplicação**: `normalize` mantém apenas o registro com `VERSAO` mais alta para cada `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)`.
- **Mapeamento multi-setor**: contas de bancos e industriais diferem; casos xfail documentados em `tests/test_indicators.py`. Ver `account_map.py` para `# TODO: sector_profile`.
- **Cadastro CVM**: fluxo dedicado `download-cad → load-cad → classify-cad`. Classificação usa apenas `SIT='ATIVO'` e `SETOR_ATIV`. Mapeamento setorial governado via `setor_profile_map`. Ver [`docs/dados_cadastrais.md`](docs/dados_cadastrais.md).
