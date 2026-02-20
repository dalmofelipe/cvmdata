# Plano de Implementação do cvmdata

## Objetivo

Pipeline Python que baixa os ZIPs da CVM dos últimos 5 anos (2021–2025, configurável por `--year`), ingere todos os 8 tipos de demonstrativo financeiro de todas as empresas abertas da B3 em DuckDB, normaliza e deduplica os dados, mapeia contas contábeis e calcula os indicadores de análise fundamentalista (rentabilidade, liquidez, endividamento). Indicadores de Valuation (P/L, P/VPA, DY) documentados para iteração futura.

Referências de produto final:
- http://www.investido10.com.br
- https://statusinvest.com.br

---

## Stack Tecnológica

| Camada | Tecnologia | Observação |
|---|---|---|
| Package manager | `uv` | Substitui pip + venv + pyenv + poetry em uma ferramenta só |
| Banco (Fase 1) | DuckDB | Arquivo único `data/db/cvmdata.duckdb`, sem servidor |
| Banco (Fase 2) | PostgreSQL via Docker Compose | Migração via extensão `postgres` nativa do DuckDB |
| Leitura CSV | DuckDB nativo `read_csv` | Suporte a `delim=';'` e `encoding='latin1'` built-in, sem Pandas |
| CLI | Typer | Comandos com flags `--year`, `--cnpj` |
| Config/env | pydantic-settings + `.env` | Centraliza paths, URLs e credenciais |
| HTTP | httpx | Download dos ZIPs da CVM |
| Linter/Formatter | ruff | Substitui flake8 + black + isort |
| Testes | pytest | Fixtures com DuckDB in-memory |
| API futura | FastAPI + uvicorn | Fase 2 |
| Dashboard futuro | React | Fase 3 |

---

## Fonte de Dados

| Tipo | URL base | Anos disponíveis |
|---|---|---|
| ITR (trimestral) | `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip` | 2021–2025 |
| DFP (anual) | `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip` | 2021–2025 |

Cada ZIP contém 8 CSVs de demonstrativos + arquivos auxiliares:
- **BPA** — Balanço Patrimonial Ativo
- **BPP** — Balanço Patrimonial Passivo
- **DRE** — Demonstração de Resultado
- **DFC_MD** — Demonstração de Fluxo de Caixa (Método Direto)
- **DFC_MI** — Demonstração de Fluxo de Caixa (Método Indireto)
- **DRA** — Demonstração de Resultado Abrangente
- **DMPL** — Demonstração das Mutações do Patrimônio Líquido
- **DVA** — Demonstração de Valor Adicionado

Variantes por escopo consolidado (`con`) e individual (`ind`) para cada demonstrativo.

### Schema dos CSVs (14 colunas, separador `;`, encoding Latin-1)

| Coluna | Tipo | Descrição |
|---|---|---|
| `CNPJ_CIA` | varchar | CNPJ da companhia |
| `DT_REFER` | date | Data de referência do documento |
| `VERSAO` | smallint | Versão do documento (manter a maior) |
| `DENOM_CIA` | varchar | Nome da empresa |
| `CD_CVM` | char(6) | Código CVM (pode ter zero à esquerda) |
| `GRUPO_DFP` | varchar | Nome e nível de agregação do demonstrativo |
| `MOEDA` | varchar | Moeda (`REAL`) |
| `ESCALA_MOEDA` | varchar | Escala (`MIL` = R$ milhares) |
| `ORDEM_EXERC` | varchar | `ÚLTIMO` (período atual) ou `PENÚLTIMO` (comparativo) |
| `DT_FIM_EXERC` | date | Data fim do exercício |
| `CD_CONTA` | varchar | Código hierárquico da conta (ex: `1`, `1.01`, `1.02.04`) |
| `DS_CONTA` | varchar | Descrição da conta |
| `VL_CONTA` | decimal | Valor em R$ na escala indicada por `ESCALA_MOEDA` |
| `ST_CONTA_FIXA` | char(1) | Conta fixa (`S`) ou variável (`N`) |

---

## Estrutura de Pastas

```
cvmdata/
├── pyproject.toml          # deps, scripts, ruff config
├── uv.lock                 # lockfile — commitar no git
├── .python-version         # ex: "3.12"
├── .env                    # variáveis de ambiente (não commitar)
├── .gitignore
├── Makefile
├── README.md
│
├── data/
│   ├── raw/                # ZIPs + CSVs extraídos (.gitignore)
│   │   ├── itr/
│   │   │   └── {year}/     # ex: 2024/itr_cia_aberta_BPA_con_2024.csv
│   │   └── dfp/
│   │       └── {year}/
│   └── db/
│       └── cvmdata.duckdb  # banco DuckDB (.gitignore)
│
├── docs/
│   ├── analise_fundamentalista.md
│   └── valuation_future.md
│
├── src/
│   └── cvmdata/
│       ├── __init__.py
│       ├── config.py           # Config via pydantic-settings + .env
│       ├── db.py               # Repository abstrato + DuckDBRepository
│       ├── cli.py              # Entrypoint Typer
│       │
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── downloader.py   # Download + extração dos ZIPs da CVM
│       │   └── loader.py       # Ingestão dos CSVs no DuckDB
│       │
│       └── transform/
│           ├── __init__.py
│           ├── normalize.py    # Deduplicação, tipos, padronização
│           ├── account_map.py  # Mapeamento CD_CONTA → componente
│           └── indicators.py   # Cálculo dos indicadores fundamentalistas
│
└── tests/
    ├── conftest.py             # Fixtures: DuckDB in-memory
    ├── fixtures/               # CSVs de amostra por setor
    │   ├── sample_bank_bpa.csv         # ex: BCO Brasil, BRB
    │   ├── sample_industrial_bpa.csv   # ex: VALE, PETROBRAS
    │   └── sample_industrial_dre.csv
    ├── test_loader.py
    ├── test_normalize.py
    └── test_indicators.py
```

---

## Steps de Implementação

### Step 1 — Estrutura e Ambiente

- Instalar `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `uv init cvmdata && cd cvmdata && uv python pin 3.12`
- Criar estrutura de pastas conforme seção acima
- `pyproject.toml` com dependências:
  ```toml
  [project]
  name = "cvmdata"
  version = "0.1.0"
  requires-python = ">=3.12"
  dependencies = [
      "duckdb>=1.2",
      "httpx>=0.27",
      "typer>=0.12",
      "pydantic-settings>=2.0",
  ]

  [project.optional-dependencies]
  api = ["fastapi>=0.115", "uvicorn[standard]>=0.32"]
  dev = ["pytest>=8", "ruff>=0.9"]

  [project.scripts]
  cvmdata = "cvmdata.cli:app"

  [tool.ruff.lint]
  select = ["E", "F", "I"]
  ```
- `.gitignore` cobrindo `data/`, `*.duckdb`, `.env`
- `config.py` com `pydantic-settings` lendo `DATA_DIR`, `DB_PATH`, `YEARS` do `.env`

### Step 2 — Downloader com Janela de 5 Anos

**Arquivo:** `src/cvmdata/ingestion/downloader.py`

- Construir URLs dinamicamente para ITR e DFP por ano:
  - `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip`
  - `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip`
- Baixar com `httpx` em streaming para não estourar memória
- Extrair ZIPs para `data/raw/itr/{year}/` e `data/raw/dfp/{year}/`
- Redownload incremental: salvar checksum MD5 do ZIP; se arquivo já existe e checksum bate, pular
- Logar progresso por arquivo (tamanho, status)
- CLI: `cvmdata download` (todos os anos 2021–2025) ou `cvmdata download --year 2024`

### Step 3 — Ingestão e Schema DuckDB

**Arquivos:** `src/cvmdata/ingestion/loader.py`, `src/cvmdata/db.py`

**`db.py` — Abstração Repository:**
```python
# Padrão Repository para isolar DuckDB e facilitar migração para PostgreSQL
class BaseRepository(ABC):
    def create_schema(self): ...
    def upsert_statements(self, doc_type: str, year: int): ...
    def get_statements(self, cnpj: str, doc_type: str): ...

class DuckDBRepository(BaseRepository):
    def __init__(self, path: str):
        self.con = duckdb.connect(path)
    # Migração futura: implementar PostgresRepository com mesma interface
    # usando extensão nativa: INSTALL postgres; LOAD postgres;
    # COPY FROM DATABASE duckdb TO pg;
```

**`loader.py` — Ingestão:**
- Para cada tipo (BPA, BPP, DRE, DFC_MD, DFC_MI, DRA, DMPL, DVA) e variante (con/ind):
  ```sql
  CREATE TABLE IF NOT EXISTS {doc_type}_{scope} AS
  SELECT * FROM read_csv(
      'data/raw/itr/{year}/itr_cia_aberta_{doc_type}_{scope}_{year}.csv',
      delim       = ';',
      header      = true,
      encoding    = 'latin1',
      auto_detect = true
  )
  ```
- `INSERT INTO ... SELECT * FROM read_csv(...)` para anos subsequentes (não recriar tabela)
- Tabela única por tipo acumulando todos os anos carregados

### Step 4 — Normalização e Deduplicação

**Arquivo:** `src/cvmdata/transform/normalize.py`

- Deduplicação: manter apenas a versão mais recente de cada conta por empresa/período:
  ```sql
  CREATE OR REPLACE TABLE {doc_type}_{scope}_clean AS
  SELECT * EXCLUDE (rn) FROM (
      SELECT *,
          ROW_NUMBER() OVER (
              PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
              ORDER BY VERSAO DESC
          ) AS rn
      FROM {doc_type}_{scope}
  ) WHERE rn = 1
  ```
- Filtrar apenas `ORDEM_EXERC = 'ÚLTIMO'` para cálculos (ignorar comparativos `PENÚLTIMO`)
- Padronizar `CD_CVM`: remover zero à esquerda (`LPAD` reverso → `CAST(CD_CVM AS INTEGER)`)
- Garantir tipos: `DT_REFER::DATE`, `DT_FIM_EXERC::DATE`, `VL_CONTA::DECIMAL(29,10)`
- Normalizar `ESCALA_MOEDA`: valores em `MIL` devem ser multiplicados por 1000 para comparação consistente (ou documentar que tudo está em R$ mil)

### Step 5 — Mapeamento de Contas (Perfil Único Inicial)

**Arquivo:** `src/cvmdata/transform/account_map.py`

- Dicionário `ACCOUNT_MAP: dict[str, str]` mapeando `CD_CONTA → nome_componente`:
  ```python
  ACCOUNT_MAP = {
      # BPA
      "1":      "ativo_total",
      "1.01":   "ativo_circulante",
      "1.01.01": "caixa_equivalentes",
      "1.02":   "ativo_nao_circulante",
      "1.02.03": "realizavel_longo_prazo",
      # BPP
      "2":      "passivo_total",
      "2.01":   "passivo_circulante",
      "2.02":   "passivo_nao_circulante",
      "2.03":   "patrimonio_liquido",
      # DRE
      "3.01":   "receita_liquida",
      "3.11":   "lucro_liquido",
      # DFC
      "6.01":   "caixa_operacional",  # pode variar entre DFC_MD e DFC_MI
      # TODO: sector_profile — bancos podem usar hierarquias diferentes
      # Evoluir conforme encontrar dados fora do padrão nos testes multi-setor
  }
  ```
- Função `get_component(cd_conta: str) -> str | None` com fallback para prefixo mais longo
- **Sem perfis múltiplos por enquanto** — adicionar `# TODO: sector_profile` nos pontos de variação encontrados nos testes de fixtures (Step 8)

### Step 6 — Calculadora de Indicadores

**Arquivo:** `src/cvmdata/transform/indicators.py`

- Funções puras que recebem `dict[str, float]` com os componentes mapeados e retornam `float | None`:

```python
# Rentabilidade
def roe(lucro_liquido, patrimonio_liquido) -> float | None
def roa(lucro_liquido, ativo_total) -> float | None
def margem_liquida(lucro_liquido, receita_liquida) -> float | None

# Liquidez
def liquidez_corrente(ativo_circulante, passivo_circulante) -> float | None
def liquidez_geral(ativo_circulante, realizavel_lp, passivo_circulante, passivo_nao_circulante) -> float | None
def liquidez_imediata(caixa_equivalentes, passivo_circulante) -> float | None

# Endividamento
def endividamento_geral(passivo_circulante, passivo_nao_circulante, ativo_total) -> float | None
```

- Retornar `None` quando qualquer componente necessário estiver ausente ou for zero no denominador
- Orquestrador `calculate_all(cnpj: str, dt_refer: str) -> dict[str, float | None]` que extrai os componentes do DuckDB via `account_map` e chama todas as funções
- Salvar resultados em tabela:
  ```sql
  CREATE TABLE IF NOT EXISTS indicators (
      cnpj_cia    VARCHAR,
      dt_refer    DATE,
      indicador   VARCHAR,
      valor       DOUBLE,
      PRIMARY KEY (cnpj_cia, dt_refer, indicador)
  )
  ```

### Step 7 — CLI, Makefile e Documentação de Valuation

**Arquivo:** `src/cvmdata/cli.py` (Typer)

```
cvmdata download [--year 2024]         # baixa ZIPs da CVM (padrão: 2021-2025)
cvmdata load [--year 2024]             # ingere CSVs no DuckDB
cvmdata normalize                      # deduplicação e limpeza
cvmdata indicators [--cnpj <cnpj>]     # calcula indicadores (todas ou uma empresa)
```

**`Makefile`:**
```makefile
install:    uv sync
download:   uv run cvmdata download
load:       uv run cvmdata load
normalize:  uv run cvmdata normalize
indicators: uv run cvmdata indicators
all:        download load normalize indicators
```

**`docs/valuation_future.md`** — documentar para iteração futura:
- Indicadores: P/L, P/VPA, Dividend Yield
- Dependência: preço histórico da ação (não disponível na CVM)
- Problema: mapear `CD_CVM` (6 dígitos CVM) → ticker B3 (ex: `BBAS3`)
- Solução proposta: arquivo YAML `config/tickers.yaml` com mapeamento manual inicial + enriquecimento automático via `brapi.dev`
- Bibliotecas: `yfinance` (histórico OHLCV com sufixo `.SA`) e/ou `brapi.dev` (real-time + dividendos)
- Fórmulas: conforme `docs/analise_fundamentalista.md`

### Step 8 — Fixtures de Teste Multi-Setor

**Diretório:** `tests/fixtures/`

- Adicionar samples de empresas **não-financeiras** (ex: VALE S.A., PETROBRAS) extraídos dos CSVs reais da CVM para `tests/fixtures/`
- `tests/conftest.py`: fixture `duckdb_memory` que cria banco in-memory e carrega fixtures
- Testes devem verificar:
  - Se `account_map.py` encontra os componentes corretamente para bancos **e** industriais
  - Se diferenças de `CD_CONTA` entre setores aparecem (guiará evolução do mapeamento)
  - Se cálculos de indicadores retornam `None` graciosamente quando conta não existe
- Marcar testes que falham por diferença de setor com `@pytest.mark.xfail(reason="sector_profile pending")`

---

## Evolução Futura (Fora do Escopo da Fase 1)

| Fase | Entregável |
|---|---|
| Fase 1.1 | Perfis de setor no `account_map.py` após análise dos testes multi-setor |
| Fase 2 | Migração DuckDB → PostgreSQL, Docker Compose, FastAPI REST |
| Fase 3 | Dashboard React com gráficos históricos de indicadores |
| Fase 4 | Indicadores de Valuation (P/L, P/VPA, DY) — ver `docs/valuation_future.md` | 

