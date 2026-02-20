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

- [ ] T001 Criar `pyproject.toml` com dependências (`duckdb`, `httpx`, `typer`, `pydantic-settings`), `[project.scripts]`, `[tool.ruff.lint]` e extras `api` e `dev`
- [ ] T002 Criar `.python-version` com `3.12` e executar `uv python pin 3.12 && uv sync`
- [ ] T003 [P] Criar `.gitignore` cobrindo `data/`, `*.duckdb`, `.env`, `__pycache__/`, `.venv/`, `*.pyc`
- [ ] T004 [P] Criar estrutura de pastas: `src/cvmdata/{ingestion/,transform/,api/}`, `data/{raw/,db/}`, `tests/fixtures/`, `docs/`
- [ ] T005 [P] Criar todos os arquivos `__init__.py` vazios: `src/cvmdata/__init__.py`, `src/cvmdata/ingestion/__init__.py`, `src/cvmdata/transform/__init__.py`
- [ ] T006 Criar `src/cvmdata/config.py` com classe `Settings` via `pydantic-settings` lendo `DATA_DIR`, `DB_PATH`, `YEARS`, `ITR_URL`, `DFP_URL` do `.env`; criar `.env.example` com valores padrão
- [ ] T007 Criar `src/cvmdata/cli.py` com app Typer vazio e subcomandos stub: `download`, `load`, `normalize`, `indicators` — cada um imprimindo `"not implemented"` por enquanto
- [ ] T008 [P] Criar `Makefile` com targets: `install`, `download`, `load`, `normalize`, `indicators`, `all`, `test`, `lint`
- [ ] T009 [P] Criar `tests/conftest.py` com fixture `repo` que instancia `DuckDBRepository(":memory:")` (stub — `DuckDBRepository` será implementado em T011)

**Checkpoint**: `uv run cvmdata --help` exibe os subcomandos; `uv run ruff check src/` passa sem erros; `uv run pytest` coleta 0 testes sem falhar.

---

## Phase 1: US1 — Downloader e Ingestão

**Goal**: Baixar os ZIPs da CVM e carregar os CSVs no DuckDB.

**Independent Test**: Executar `cvmdata download --year 2024 && cvmdata load --year 2024` e verificar `SELECT COUNT(*) FROM itr_bpa_con` > 0.

### Infraestrutura compartilhada (bloqueante)

- [ ] T010 Criar `src/cvmdata/db.py` com `BaseRepository` (ABC) e `DuckDBRepository` implementando `create_schema()`, `load_csv(path, table) -> int`, `execute(sql)` e `query(sql) -> list[dict]`
- [ ] T010b [P] Verificar schemas reais dos CSVs antes de implementar o loader: para cada tipo de demonstrativo, executar `SELECT * FROM read_csv('data/raw/itr/2024/itr_cia_aberta_{TIPO}_con_2024.csv', delim=';', encoding='latin1', auto_detect=true) LIMIT 0` no DuckDB e listar colunas retornadas; documentar diferenças em relação às 14 colunas padrão (atenção especial a `DMPL`, `DFC_MD`, `DFC_MI`); referência: `meta_itr_cia_aberta_*.txt` disponível em `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/META/meta_itr_cia_aberta_txt.zip`

### Implementação do Downloader

- [ ] T011 [P] [US1] Implementar `src/cvmdata/ingestion/downloader.py`:
  - Função `download_year(doc_type: str, year: int, settings: Settings) -> Path`
  - Download em streaming com `httpx` para `data/raw/{doc_type}/{year}/`
  - Cálculo e verificação de checksum MD5 (arquivo `.md5` ao lado do ZIP)
  - Se MD5 confere: pular download, logar `INFO "skipped {filename} (cached)"`
  - Extrair ZIP para o mesmo diretório após download bem-sucedido
  - Logar tamanho do arquivo e status
- [ ] T012 [US1] Conectar `downloader.py` ao comando CLI `cvmdata download [--year INT]` em `cli.py`:
  - Sem `--year`: iterar sobre todos os anos em `settings.years`
  - Com `--year`: processar apenas aquele ano
  - Processar `itr` e `dfp` para cada ano

### Implementação do Loader

- [ ] T013 [US1] Implementar `src/cvmdata/ingestion/loader.py`:
  - Função `load_year(doc_type: str, year: int, repo: BaseRepository, settings: Settings) -> dict[str, int]`
  - Iterar sobre todos os tipos (`BPA`, `BPP`, `DRE`, `DFC_MD`, `DFC_MI`, `DRA`, `DMPL`, `DVA`) e escopos (`con`, `ind`)
  - Nome da tabela: `{doc_type}_{tipo}_{escopo}` (ex: `itr_bpa_con`, `dfp_dre_ind`)
  - Usar `repo.load_csv(path, table)` — `CREATE TABLE IF NOT EXISTS … WHERE 1=0` seguido de `INSERT INTO … SELECT * FROM read_csv(…, delim=';', encoding='latin1', auto_detect=true)`
  - Retornar dict `{tabela: linhas_inseridas}`
  - Logar contagem de linhas por arquivo; pular arquivo silenciosamente se não existir no ZIP
- [ ] T014 [US1] Conectar `loader.py` ao comando CLI `cvmdata load [--year INT]` em `cli.py`

### Testes US1

- [ ] T015 [P] [US1] Criar `tests/test_loader.py`:
  - Carregar `tests/fixtures/sample_bank_bpa.csv` via `repo.load_csv()` → verificar contagem de linhas
  - Verificar que colunas `CNPJ_CIA`, `DT_REFER`, `CD_CONTA`, `VL_CONTA` existem na tabela
  - Verificar que segunda execução de `load_csv` não duplica linhas (idempotência via count antes/depois)
- [ ] T016 [P] [US1] Criar `tests/fixtures/sample_bank_bpa.csv` com ~20 linhas extraídas de `data/raw/itr/2024/itr_cia_aberta_BPA_con_2024.csv` (BCO Brasil e BRB, múltiplos períodos e versões)

**Checkpoint US1**: `cvmdata download --year 2024 && cvmdata load --year 2024` funciona; `uv run pytest tests/test_loader.py` passa.

---

## Phase 2: US2 — Normalização e Deduplicação

**Goal**: Tabelas `*_clean` com dados deduplicados, tipos corretos, apenas `ORDEM_EXERC = 'ÚLTIMO'`.

**Independent Test**: Inserir fixture com 2 versões da mesma conta → após `cvmdata normalize`, verificar que existe apenas 1 registro com `VERSAO` maior.

### Implementação

- [ ] T017 [US2] Implementar `src/cvmdata/transform/normalize.py`:
  - Função `normalize_table(table: str, repo: BaseRepository) -> int` que cria `{table}_clean`
  - SQL de deduplicação: `ROW_NUMBER() OVER (PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC ORDER BY VERSAO DESC)` mantendo `rn = 1` e `ORDEM_EXERC = 'ÚLTIMO'`
  - Cast de tipos: `DT_REFER::DATE`, `DT_FIM_EXERC::DATE`, `VL_CONTA::DECIMAL(29,10)`
  - Padronização `CD_CVM`: `TRY_CAST(TRIM(CD_CVM) AS INTEGER)`
  - Retornar contagem de linhas na tabela limpa
  - Função `normalize_all(repo: BaseRepository) -> dict[str, int]` que itera sobre todas as tabelas raw existentes
- [ ] T018 [US2] Conectar `normalize.py` ao comando CLI `cvmdata normalize` em `cli.py`

### Testes US2

- [ ] T019 [P] [US2] Criar `tests/test_normalize.py`:
  - Fixture com 2 linhas idênticas em tudo exceto `VERSAO` (1 e 2) para o mesmo `(CNPJ_CIA, DT_REFER, CD_CONTA)` → verificar que `normalize_table` mantém apenas `VERSAO = 2`
  - Verificar que `ORDEM_EXERC = 'PENÚLTIMO'` é removido
  - Verificar que `DT_REFER` é tipo `DATE` após normalização
  - Verificar que `CD_CVM = '001023'` vira `1023` após normalização

**Checkpoint US2**: `cvmdata normalize` cria tabelas `*_clean`; `SELECT COUNT(*) FROM itr_bpa_con_clean WHERE ORDEM_EXERC != 'ÚLTIMO'` = 0; `uv run pytest tests/test_normalize.py` passa.

---

## Phase 3: US3 — Calculadora de Indicadores

**Goal**: 7 indicadores fundamentalistas calculados e persistidos em tabela `indicators` para todas as empresas/períodos.

**Independent Test**: `cvmdata indicators --cnpj "00.000.000/0001-91"` insere registros em `indicators` para BCO Brasil; ROE e ROA retornam valores plausíveis.

### Account Map

- [ ] T020 [US3] Criar `src/cvmdata/transform/account_map.py`:
  - Dicionário `ACCOUNT_MAP: dict[str, str]` com mapeamento inicial (BPA, BPP, DRE, DFC)
  - Função `get_component(cd_conta: str) -> str | None` com match exato primeiro, depois prefixo mais específico disponível
  - Logar `WARNING` para cada `cd_conta` não encontrado
  - Comentários `# TODO: sector_profile` nas entradas suspeitas de variação por setor

### Funções de Cálculo

- [ ] T021 [P] [US3] Implementar funções puras de rentabilidade em `src/cvmdata/transform/indicators.py`:
  - `roe(lucro_liquido, patrimonio_liquido) -> float | None`
  - `roa(lucro_liquido, ativo_total) -> float | None`
  - `margem_liquida(lucro_liquido, receita_liquida) -> float | None`
  - Retornar `None` se qualquer argumento for `None` ou denominador for `0`
- [ ] T022 [P] [US3] Implementar funções puras de liquidez em `src/cvmdata/transform/indicators.py`:
  - `liquidez_corrente(ativo_circulante, passivo_circulante) -> float | None`
  - `liquidez_geral(ativo_circulante, realizavel_lp, passivo_circulante, passivo_nao_circulante) -> float | None`
  - `liquidez_imediata(caixa_equivalentes, passivo_circulante) -> float | None`
- [ ] T023 [P] [US3] Implementar função pura de endividamento em `src/cvmdata/transform/indicators.py`:
  - `endividamento_geral(passivo_circulante, passivo_nao_circulante, ativo_total) -> float | None`

### Schema e Orquestrador

- [ ] T024 [US3] Criar tabela `indicators` no schema DuckDB via `repo.create_schema()` (depende de T021, T022, T023):
  ```sql
  CREATE TABLE IF NOT EXISTS indicators (
      cnpj_cia  VARCHAR NOT NULL,
      dt_refer  DATE    NOT NULL,
      indicador VARCHAR NOT NULL,
      valor     DOUBLE,
      PRIMARY KEY (cnpj_cia, dt_refer, indicador)
  )
  ```
- [ ] T025 [US3] Implementar orquestrador `calculate_all(cnpj: str | None, repo: BaseRepository)` em `indicators.py`:
  - Listar todos os `(cnpj_cia, dt_refer)` distintos nas tabelas `*_clean`
  - Filtrar por `cnpj` se fornecido
  - Para cada empresa/período: extrair componentes via `get_component` das tabelas `*_clean`
  - Calcular todos os 7 indicadores
  - `INSERT OR REPLACE INTO indicators` para cada resultado
  - Nunca interromper por empresa com dados incompletos — `try/except` por empresa, logar `ERROR` e continuar
- [ ] T026 [US3] Conectar orquestrador ao comando CLI `cvmdata indicators [--cnpj TEXT]` em `cli.py`

### Testes US3

- [ ] T027 [P] [US3] Criar `tests/test_indicators.py` — funções puras:
  - `roe(100, 500)` → `20.0`
  - `roe(100, 0)` → `None`
  - `roe(None, 500)` → `None`
  - `liquidez_corrente(200, 100)` → `2.0`
  - `endividamento_geral(100, 200, 1000)` → `30.0`
- [ ] T028 [P] [US3] Criar `tests/fixtures/sample_bank_bpp.csv` e `tests/fixtures/sample_bank_dre.csv` com linhas de BCO Brasil
- [ ] T029 [US3] Adicionar teste de integração em `tests/test_indicators.py` usando fixture in-memory:
  - Carregar `sample_bank_bpa.csv` + `sample_bank_bpp.csv` + `sample_bank_dre.csv` → normalizar → calcular indicadores
  - Verificar que `indicators` contém registros para BCO Brasil
  - Verificar que `ROE` não é `None` para empresa com todos os dados presentes

### Testes Multi-Setor (descoberta empírica de diferenças)

- [ ] T030 [P] [US3] Criar `tests/fixtures/sample_industrial_bpa.csv` e `tests/fixtures/sample_industrial_dre.csv` com linhas de VALE S.A. ou PETROBRAS extraídas dos CSVs reais
- [ ] T031 [US3] Adicionar testes em `tests/test_indicators.py` para empresas industriais:
  - Calcular indicadores para empresa industrial via fixture
  - Marcar com `@pytest.mark.xfail(reason="sector_profile pending")` os casos onde `CD_CONTA` difere do mapeamento atual
  - Documentar nos comentários do teste qual `CD_CONTA` foi encontrado e qual era o esperado

**Checkpoint US3**: `cvmdata indicators --cnpj "00.000.000/0001-91"` insere 7 indicadores por período disponível; `uv run pytest tests/test_indicators.py` passa (xfail marcados mas não bloqueantes).

---

## Phase 4: US4 — Consulta de Indicadores

**Goal**: Comando CLI para consultar e exibir indicadores calculados em tabela formatada.

**Independent Test**: `cvmdata query --cnpj "00.000.000/0001-91"` exibe tabela com colunas `dt_refer`, `indicador`, `valor` para todos os períodos de BCO Brasil.

### Implementação

- [ ] T032 [US4] Adicionar comando `cvmdata query --cnpj TEXT [--year INT]` em `cli.py`:
  - Executar `SELECT cnpj_cia, dt_refer, indicador, valor FROM indicators WHERE cnpj_cia = ? ORDER BY dt_refer, indicador`
  - Formatar saída como tabela ASCII via `typer.echo` ou `rich.table` (se `rich` já é dep transitiva do Typer)
  - Sem `--cnpj`: listar as 10 empresas com mais indicadores calculados como sumário

### Testes US4

- [ ] T033 [P] [US4] Adicionar teste em `tests/test_indicators.py`:
  - Popular `indicators` com dados conhecidos → verificar que query retorna os registros corretos ordenados por `dt_refer`

**Checkpoint US4**: `cvmdata query --cnpj "00.000.000/0001-91"` exibe indicadores em tabela.

---

## Phase 5: Documentação de Valuation (Trabalho Futuro)

**Goal**: Documentar P/L, P/VPA, DY para iteração futura sem bloquear o pipeline atual.

- [ ] T034 [P] Criar `docs/valuation_future.md` com:
  - Fórmulas de P/L, P/VPA, Dividend Yield (referenciando `docs/analise_fundamentalista.md`)
  - Dependência de preço histórico da ação (não disponível nos dados CVM)
  - Problema do mapeamento `CD_CVM → ticker B3` com exemplo (`1023 → BBAS3`)
  - Abordagem proposta: `config/tickers.yaml` + `yfinance`/`brapi.dev`
  - Estimativa de esforço e pré-requisitos para implementação futura

---

## Phase 6: Integração Final e Qualidade

**Goal**: Pipeline completo funcionando end-to-end; cobertura ≥ 80% em `transform/`.

- [ ] T035 Executar pipeline completo para 2024: `make all` — documentar quaisquer erros encontrados e corrigir
- [ ] T036 [P] Verificar cobertura de testes: `uv run pytest --cov=src/cvmdata/transform --cov-report=term-missing` — garantir ≥ 80%
- [ ] T037 [P] Executar `uv run ruff check src/ tests/` e corrigir todos os warnings
- [ ] T038 [P] Criar `README.md` com: pré-requisitos, instalação (`uv sync`), uso (`make all`), descrição dos comandos CLI e estrutura de pastas

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
