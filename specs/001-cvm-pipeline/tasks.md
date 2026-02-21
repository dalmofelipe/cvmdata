# Tasks: Pipeline CVM — Indicadores Fundamentalistas

**Branch**: `001-cvm-pipeline`
**Input**: [spec.md](./spec.md), [plan.md](./plan.md)
**Prerequisites**: plan.md ✅, spec.md ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências entre si)
- **[USx]**: User Story de referência (US1=download/ingestão, US2=normalização, US3=indicadores, US4=consulta)

---

## Phase 0: Ambiente e Estrutura do Projeto

**Purpose**: Projeto Python instalável, com linter, testes e CLI funcionando antes de qualquer lógica de negócio.

- [x] T001 Criar `pyproject.toml` com dependências (`duckdb`, `httpx`, `typer`, `pydantic-settings`), `[project.scripts]`, `[tool.ruff.lint]` e extras `api` e `dev`
- [x] T002 Criar `.python-version` com `3.12` e executar `uv python pin 3.12 && uv sync`
- [x] T003 [P] Criar `.gitignore` cobrindo `data/`, `*.duckdb`, `.env`, `__pycache__/`, `.venv/`, `*.pyc`
- [x] T004 [P] Criar estrutura de pastas: `src/cvmdata/{ingestion/,transform/,api/}`, `data/{raw/,db/}`, `tests/fixtures/`, `docs/`
- [x] T005 [P] Criar todos os arquivos `__init__.py` vazios: `src/cvmdata/__init__.py`, `src/cvmdata/ingestion/__init__.py`, `src/cvmdata/transform/__init__.py`
- [x] T006 Criar `src/cvmdata/config.py` com classe `Settings` via `pydantic-settings` lendo `DATA_DIR`, `DB_PATH`, `YEARS`, `ITR_URL`, `DFP_URL` do `.env`; criar `.env.example` com valores padrão
- [x] T007 Criar `src/cvmdata/cli.py` com app Typer e subcomandos `download`, `load`, `normalize` (stub), `indicators` (stub)
- [x] T008 [P] Criar `Makefile` com targets: `install`, `download`, `load`, `normalize`, `indicators`, `all`, `test`, `lint`
- [x] T009 [P] Criar `tests/conftest.py` com fixture `db` instanciando DuckDB in-memory

**Checkpoint** ✅: `uv run cvmdata --help` exibe os subcomandos; `uv run ruff check src/` passa sem erros; `uv run pytest` coleta 0 testes sem falhar.

---

## Phase 1: US1 — Downloader e Ingestão

**Goal**: Baixar os ZIPs da CVM e carregar os CSVs no DuckDB.

**Independent Test**: Executar `cvmdata download --year 2024 && cvmdata load --year 2024` e verificar `SELECT COUNT(*) FROM itr_bpa_con` > 0.

### Infraestrutura compartilhada (bloqueante)

- [x] T010 Criar `src/cvmdata/ingestion/db.py` com DDLs dos 3 demonstrativos em escopo (BPA, BPP, DRE), `get_connection()` e `init_schema()`
- [x] T010b [P] Verificar schemas reais dos CSVs: 3 grupos descobertos (BALANCE 14 cols, FLOW 15 cols+DT_INI_EXERC, DMPL 16 cols); bugs de schema corrigidos (encoding `latin-1`, DMPL sem VL_CONTA_01..09, FLOW com DT_INI_EXERC)
- [x] T010c [P] Refatoração de escopo — definir `INDICATOR_DEMOS = {"BPA", "BPP", "DRE"}` em `db.py` e `downloader.py`; filtrar extração do ZIP para apenas esses 3 demos; remover DDLs de DFC_MD, DFC_MI, DMPL, DRA, DVA; atualizar spec.md/plan.md/tasks.md com ADR *(descoberta pós-análise de dados reais: nenhuma conta dos 5 demos descartados é necessária para os 7 indicadores planejados)*

### Implementação do Downloader

- [x] T011 [P] [US1] Implementar `src/cvmdata/ingestion/downloader.py`: download streaming httpx, extração filtrada por `INDICATOR_DEMOS`, idempotência por existência do arquivo
- [x] T012 [US1] Conectar `downloader.py` ao CLI `cvmdata download [--year INT] [--force] [--verbose]`

### Implementação do Loader

- [x] T013 [US1] Implementar `src/cvmdata/ingestion/loader.py`: `parse_csv_filename()`, `_build_insert_sql()` (3 branches por grupo de schema), `load_csv()` idempotente (DELETE+INSERT), `load_source_year()`
- [x] T014 [US1] Conectar `loader.py` ao CLI `cvmdata load [--year INT] [--verbose]`

### Testes US1

- [x] T015 [P] [US1] Criar `tests/test_loader.py` com 17 testes: `parse_csv_filename` (válido/inválido), `load_csv` (insert, idempotência), `load_source_year` (dir vazio, multi-demo, skip não-demo); criar `tests/test_downloader.py` com 4 testes
- [x] T016 [P] [US1] Fixtures in-memory via helpers `_make_bpa_csv()` e `_make_flow_csv()` — dados reais não necessários para testes unitários

**Checkpoint US1** ✅: `cvmdata download --year 2024` (ITR 31.2 MB, DFP 12.7 MB); `cvmdata load --year 2024` (5.016.187 linhas em 6 tabelas — BPA/BPP/DRE × con/ind, ITR+DFP); `uv run pytest` 24/24 passando; `ruff check` limpo.

---

## Phase 2: US2 — Normalização e Deduplicação

**Goal**: Tabelas `*_clean` com dados deduplicados, tipos corretos, apenas `ORDEM_EXERC = 'ÚLTIMO'`.

**Independent Test**: Inserir fixture com 2 versões da mesma conta → após `cvmdata normalize`, verificar que existe apenas 1 registro com `VERSAO` maior.

### Implementação

- [x] T017 [US2] Implementar `src/cvmdata/transform/normalize.py`:
  - Função `normalize_table(table: str, repo: BaseRepository) -> int` que cria `{table}_clean`
  - SQL de deduplicação: `ROW_NUMBER() OVER (PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC ORDER BY VERSAO DESC)` mantendo `rn = 1` e `ORDEM_EXERC = 'ÚLTIMO'`
  - Cast de tipos: `DT_REFER::DATE`, `DT_FIM_EXERC::DATE`, `VL_CONTA::DECIMAL(29,10)`
  - Padronização `CD_CVM`: `TRY_CAST(TRIM(CD_CVM) AS INTEGER)`
  - Retornar contagem de linhas na tabela limpa
  - Função `normalize_all(repo: BaseRepository) -> dict[str, int]` que itera sobre todas as tabelas raw existentes
- [x] T018 [US2] Conectar `normalize.py` ao comando CLI `cvmdata normalize` em `cli.py`

### Testes US2

- [x] T019 [P] [US2] Criar `tests/test_normalize.py` com 13 testes: dedup (VERSAO mais alta), remoção PENÚLTIMO, tipos DATE/DECIMAL, CD_CVM stripped, idempotência, tabela vazia, normalize_all

**Checkpoint US2** ✅: `cvmdata normalize` cria tabelas `*_clean`; `uv run pytest tests/test_normalize.py` 13/13 passando; `uv run pytest` 37/37 passando; `ruff check` limpo.

---

## Phase 3: US3 — Calculadora de Indicadores

**Goal**: 7 indicadores fundamentalistas calculados e persistidos em tabela `indicators` para todas as empresas/períodos.

**Independent Test**: `cvmdata indicators --cnpj "00.000.000/0001-91"` insere registros em `indicators` para BCO Brasil; ROE e ROA retornam valores plausíveis.

### Account Map

- [x] T020 [US3] Criar `src/cvmdata/transform/account_map.py`:
  - Dicionário `ACCOUNT_MAP: dict[str, str]` com 16 contas mapeadas (BPA: 6, BPP: 5, DRE: 5) — ver plan.md Phase 4
  - Função `get_component(cd_conta: str) -> str | None` com match exato
  - Logar `WARNING` para cada `cd_conta` não encontrado
  - Comentários `# TODO: sector_profile` nas entradas suspeitas de variação por setor (ex: `emprestimos_cp` em bancos)

### Funções de Cálculo

- [x] T021 [P] [US3] Implementar funções puras de rentabilidade em `src/cvmdata/transform/indicators.py`:
  - `roe`, `roa`, `margem_bruta`, `margem_operacional`, `margem_liquida`, `giro_ativo`
  - Retornar `None` se qualquer argumento for `None` ou denominador for `0`
- [x] T022 [P] [US3] Implementar funções puras de liquidez em `src/cvmdata/transform/indicators.py`:
  - `liquidez_corrente`, `liquidez_seca`, `liquidez_imediata`, `liquidez_geral`
- [x] T023 [P] [US3] Implementar funções puras de endividamento em `src/cvmdata/transform/indicators.py`:
  - `endividamento_geral`, `divida_bruta`, `divida_liquida`, `divida_liquida_pl`, `cobertura_juros`

### Schema e Orquestrador

- [x] T024 [US3] Criar tabela `indicators` no schema DuckDB via `repo.create_schema()` (depende de T021, T022, T023):
  ```sql
  CREATE TABLE IF NOT EXISTS indicators (
      cnpj_cia  VARCHAR NOT NULL,
      dt_refer  DATE    NOT NULL,
      indicador VARCHAR NOT NULL,
      valor     DOUBLE,
      PRIMARY KEY (cnpj_cia, dt_refer, indicador)
  )
  ```
- [x] T025 [US3] Implementar orquestrador `calculate_all(cnpj: str | None, repo: BaseRepository)` em `indicators.py`:
  - Listar todos os `(cnpj_cia, dt_refer)` distintos nas tabelas `*_clean`
  - Filtrar por `cnpj` se fornecido
  - Para cada empresa/período: extrair componentes via `get_component` das tabelas `*_clean`
  - Calcular todos os 15 indicadores (6 rentabilidade + 4 liquidez + 5 endividamento)
  - `INSERT OR REPLACE INTO indicators` para cada resultado
  - Nunca interromper por empresa com dados incompletos — `try/except` por empresa, logar `ERROR` e continuar
- [x] T026 [US3] Conectar orquestrador ao comando CLI `cvmdata indicators [--cnpj TEXT]` em `cli.py`

### Testes US3

- [x] T027 [P] [US3] Criar `tests/test_indicators.py` — funções puras (pelo menos 1 caso feliz + 1 None por função):
  - Rentabilidade: `roe(100,500)`→`20.0`; `margem_bruta(300,1000)`→`30.0`; `margem_operacional(200,1000)`→`20.0`; `giro_ativo(1000,2000)`→`0.5`
  - Liquidez: `liquidez_corrente(200,100)`→`2.0`; `liquidez_seca(200,50,100)`→`1.5`; `liquidez_imediata(80,100)`→`0.8`
  - Endividamento: `endividamento_geral(100,200,1000)`→`30.0`; `divida_liquida(300,400,80,120)`→`500.0`; `cobertura_juros(200,50)`→`4.0`
  - Denominador zero → `None` para todas as funções; argumento `None` → `None`
- [x] T028 [P] [US3] Criar `tests/fixtures/sample_bank_bpp.csv` e `tests/fixtures/sample_bank_dre.csv` com linhas de BCO Brasil
- [x] T029 [US3] Adicionar teste de integração em `tests/test_indicators.py` usando fixture in-memory:
  - Carregar `sample_bank_bpa.csv` + `sample_bank_bpp.csv` + `sample_bank_dre.csv` → normalizar → calcular indicadores
  - Verificar que `indicators` contém registros para BCO Brasil
  - Verificar que `ROE` não é `None` para empresa com todos os dados presentes

### Testes Multi-Setor (descoberta empírica de diferenças)

- [x] T030 [P] [US3] Criar `tests/fixtures/sample_industrial_bpa.csv` e `tests/fixtures/sample_industrial_dre.csv` com linhas de VALE S.A. ou PETROBRAS extraídas dos CSVs reais
- [x] T031 [US3] Adicionar testes em `tests/test_indicators.py` para empresas industriais:
  - Calcular indicadores para empresa industrial via fixture
  - Marcar com `@pytest.mark.xfail(reason="sector_profile pending")` os casos onde `CD_CONTA` difere do mapeamento atual
  - Documentar nos comentários do teste qual `CD_CONTA` foi encontrado e qual era o esperado

**Checkpoint US3** ✅: `calculate_all` guarda contra tabelas *_clean ausentes; 15 indicadores (6 rentabilidade + 4 liquidez + 5 endividamento) calculados via `_CALC_PLAN`; `INSERT OR REPLACE` em `indicators`; CLI `cvmdata indicators [--cnpj]` wired; `uv run pytest` 90/90 passando; `ruff check` limpo.

---

## Phase 4: US4 — Consulta de Indicadores

**Goal**: Comando CLI para consultar e exibir indicadores calculados em tabela formatada.

**Independent Test**: `cvmdata query --cnpj "00.000.000/0001-91"` exibe tabela com colunas `dt_refer`, `indicador`, `valor` para todos os períodos de BCO Brasil.

### Implementação

- [x] T032 [US4] Adicionar comando `cvmdata query --cnpj TEXT [--year INT]` em `cli.py`:
  - Executar `SELECT cnpj_cia, dt_refer, indicador, valor FROM indicators WHERE cnpj_cia = ? ORDER BY dt_refer, indicador`
  - Formatar saída como tabela ASCII via `typer.echo` ou `rich.table` (se `rich` já é dep transitiva do Typer)
  - Sem `--cnpj`: listar as 10 empresas com mais indicadores calculados como sumário

### Testes US4

- [x] T033 [P] [US4] Adicionar teste em `tests/test_indicators.py`:
  - Popular `indicators` com dados conhecidos → verificar que query retorna os registros corretos ordenados por `dt_refer`

**Checkpoint US4** ✅: `cvmdata query --cnpj "00.000.000/0001-91"` exibe indicadores em tabela; `uv run pytest` 100/100 passando, 2 xfailed esperados; `ruff check` limpo.

---

## Phase 5: Documentação de Valuation (Trabalho Futuro)

**Goal**: Documentar P/L, P/VPA, DY para iteração futura sem bloquear o pipeline atual.

- [x] T034 [P] Criar `docs/valuation_future.md` com:
  - Fórmulas de P/L, P/VPA, Dividend Yield (referenciando `docs/analise_fundamentalista.md`)
  - Dependência de preço histórico da ação (não disponível nos dados CVM)
  - Problema do mapeamento `CD_CVM → ticker B3` com exemplo (`1023 → BBAS3`)
  - Abordagem proposta: `config/tickers.yaml` + `yfinance`/`brapi.dev`
  - Estimativa de esforço e pré-requisitos para implementação futura

---

## Phase 6: Integração Final e Qualidade

**Goal**: Pipeline completo funcionando end-to-end; cobertura ≥ 80% em `transform/`.

- [x] T035 Executar pipeline completo para 2024: `make all` — documentar quaisquer erros encontrados e corrigir
- [x] T036 [P] Verificar cobertura de testes: `uv run pytest --cov=src/cvmdata/transform --cov-report=term-missing` — garantir ≥ 80%
- [x] T037 [P] Executar `uv run ruff check src/ tests/` e corrigir todos os warnings
- [x] T038 [P] Criar `README.md` com: pré-requisitos, instalação (`uv sync`), uso (`make all`), descrição dos comandos CLI e estrutura de pastas

**Checkpoint Final**: `make all` executa sem erros fatais para 2024; `make test` passa com ≥ 80% cobertura em `transform/`; `make lint` sem warnings.

---

## Dependências entre Tasks

```
T001-T009 (Phase 0)
    └── T010 (db.py BaseRepository)
         ├── T011 → T012 (downloader → CLI download)
         ├── T013 → T014 (loader → CLI load)
         └── T017 → T018 (normalize → CLI normalize)
              └── T020 (account_map)
                   ├── T021 [P]
                   ├── T022 [P]
                   └── T023 [P]
                        └── T024 → T025 → T026 (schema → orchestrator → CLI indicators)
                                            └── T032 → T033 (query CLI)
T015, T016 [P após T013]
T019 [P após T017]
T027, T028 [P após T021-T023]
T029 [após T024-T025 + T028]
T030, T031 [P após T029]
T034 [P — sem dependências]
T035-T038 [após T026]
```
