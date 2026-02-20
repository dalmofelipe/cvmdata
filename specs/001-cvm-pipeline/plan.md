# Implementation Plan: Pipeline CVM — Indicadores Fundamentalistas

**Branch**: `001-cvm-pipeline` | **Date**: 2026-02-20 | **Spec**: [spec.md](./spec.md)

## Summary

Pipeline Python que baixa os ZIPs da CVM (ITR trimestral + DFP anual, 2021–2025), ingere os 3 demonstrativos necessários (BPA, BPP, DRE) de todas as ~728 empresas abertas da B3 em DuckDB, normaliza e deduplica os dados e calcula os indicadores de análise fundamentalista (rentabilidade, liquidez, endividamento). Stack local-first: DuckDB como banco de dados de arquivo único sem servidor, com caminho de migração clara para PostgreSQL na Fase 2.

## Technical Context

**Language/Version**: Python 3.12+, gerenciado por `uv`
**Primary Dependencies**: `duckdb>=1.2`, `httpx>=0.27`, `typer>=0.12`, `pydantic-settings>=2.0`, `ruff>=0.9`, `pytest>=8`
**Storage**: DuckDB — arquivo único `data/db/cvmdata.duckdb`; migração futura para PostgreSQL via extensão `postgres` nativa do DuckDB
**Testing**: pytest com DuckDB in-memory (`duckdb.connect(':memory:')`)
**Target Platform**: Linux (desenvolvimento local); sem servidor necessário na Fase 1
**Project Type**: single — CLI Python com módulos de ingestão e transformação
**Performance Goals**: processar ~600 empresas × 5 anos × 8 demonstrativos sem timeout; DuckDB lê 60k+ linhas em milissegundos via `read_csv` nativo
**Constraints**: sem Pandas na ingestão (DuckDB nativo); sem PostgreSQL na Fase 1; todos os comandos CLI idempotentes; `None` em indicadores com dados ausentes, nunca exception
**Scale/Scope**: ~728 empresas confirmadas (2024), 5 anos, 3 tipos (BPA, BPP, DRE) × 2 variantes (con/ind) = ~12 CSVs por ano; tabela `indicators` com ~728 empresas × ~20 períodos × 15 indicadores ≈ 218k registros

## Constitution Check

- ✅ **Simplicidade**: DuckDB arquivo único, sem servidor, sem ORM, sem Pandas
- ✅ **Pipeline por etapas**: `download → load → normalize → indicators`, cada uma idempotente
- ✅ **Dados como fonte da verdade**: rastreabilidade `CNPJ_CIA + DT_REFER + CD_CONTA + VERSAO`
- ✅ **Tolerância a falhas**: `None` em conta ausente, processamento continua para outras empresas
- ✅ **Código testável**: funções puras em `transform/`, fixtures in-memory
- ✅ **Evolução incremental**: `account_map.py` com perfil único, `# TODO: sector_profile` para variações futuras

## Project Structure

### Documentation (this feature)

```text
specs/001-cvm-pipeline/
├── plan.md          # Este arquivo
├── spec.md          # Especificação funcional
└── tasks.md         # Gerado por /speckit.tasks (próximo passo)
```

### Source Code (repository root)

```text
cvmdata/
├── pyproject.toml          # deps, scripts, ruff config
├── uv.lock                 # lockfile — commitar no git
├── .python-version         # "3.12"
├── .env                    # não commitar
├── .gitignore
├── Makefile
│
├── data/
│   ├── raw/                # ZIPs + CSVs extraídos (.gitignore)
│   │   ├── itr/{year}/     # ex: itr_cia_aberta_BPA_con_2024.csv
│   │   └── dfp/{year}/
│   └── db/
│       └── cvmdata.duckdb  # (.gitignore)
│
├── docs/
│   ├── analise_fundamentalista.md
│   └── valuation_future.md
│
├── src/
│   └── cvmdata/
│       ├── __init__.py
│       ├── config.py           # pydantic-settings + .env
│       ├── db.py               # BaseRepository + DuckDBRepository
│       ├── cli.py              # Typer entrypoint
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── downloader.py   # download + extração ZIPs CVM
│       │   └── loader.py       # read_csv → DuckDB
│       └── transform/
│           ├── __init__.py
│           ├── normalize.py    # dedup, tipos, padronização
│           ├── account_map.py  # CD_CONTA → componente semântico
│           └── indicators.py   # funções puras de cálculo
│
└── tests/
    ├── conftest.py             # fixture duckdb_memory
    ├── fixtures/
    │   ├── sample_bank_bpa.csv       # BCO Brasil, BRB
    │   ├── sample_industrial_bpa.csv # VALE, PETROBRAS
    │   └── sample_industrial_dre.csv
    ├── test_loader.py
    ├── test_normalize.py
    └── test_indicators.py
```

**Structure Decision**: single project, src-layout Python. Sem separação frontend/backend nesta fase. API futura entra em `src/cvmdata/api/` sem alterar estrutura existente.

---

## Implementation Phases

### Phase 0 — Ambiente e Configuração

**Objetivo**: projeto Python funcional, instalável, com linter e testes rodando.

**Arquivos a criar**:
- `pyproject.toml` com todas as dependências e `[project.scripts] cvmdata = "cvmdata.cli:app"`
- `.python-version` com `3.12`
- `.gitignore` cobrindo `data/`, `*.duckdb`, `.env`, `__pycache__`, `.venv`
- `Makefile` com targets: `install`, `download`, `load`, `normalize`, `indicators`, `all`, `test`, `lint`
- `src/cvmdata/__init__.py`, `src/cvmdata/config.py`
- `src/cvmdata/ingestion/__init__.py`, `src/cvmdata/transform/__init__.py`

**`config.py`** — via `pydantic-settings`:
```python
class Settings(BaseSettings):
    data_dir: Path = Path("data")
    db_path: Path = Path("data/db/cvmdata.duckdb")
    years: list[int] = [2021, 2022, 2023, 2024, 2025]
    itr_url: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
    dfp_url: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
    model_config = SettingsConfigDict(env_file=".env")
```

**Critério de conclusão**: `uv run cvmdata --help` exibe os comandos; `uv run pytest` passa sem erros.

---

### Phase 1 — Downloader

**Objetivo**: baixar e extrair os ZIPs da CVM com redownload incremental.

**Arquivo**: `src/cvmdata/ingestion/downloader.py`

**Lógica**:
1. Para cada `doc_type` em `["itr", "dfp"]` e cada `year` nos anos configurados:
   - Construir URL via `settings.itr_url.format(year=year)` ou `settings.dfp_url.format(year=year)`
   - Verificar se `data/raw/{doc_type}/{year}/{zip_name}.md5` existe e checksum confere → pular
   - Baixar com `httpx.stream("GET", url)` gravando em chunks para `data/raw/{doc_type}/{year}/`
   - Calcular MD5 do arquivo baixado e salvar em `.md5` ao lado
   - Extrair ZIP para o mesmo diretório
2. Logar `INFO` para cada arquivo baixado/pulado com tamanho

**CLI**: `cvmdata download [--year INT]` — sem `--year` processa todos os anos em `settings.years`

**Critério de conclusão**: executar `cvmdata download --year 2024` cria `data/raw/itr/2024/` e `data/raw/dfp/2024/` com os CSVs extraídos; segunda execução pula o download.

---

### Phase 2 — Loader (Ingestão DuckDB)

**Objetivo**: carregar todos os CSVs no DuckDB, acumulando anos sem duplicar.

**Arquivos**: `src/cvmdata/db.py`, `src/cvmdata/ingestion/loader.py`

**`db.py`**:
```python
from abc import ABC, abstractmethod
import duckdb

class BaseRepository(ABC):
    @abstractmethod
    def create_schema(self) -> None: ...
    @abstractmethod
    def load_csv(self, path: str, table: str) -> int: ...  # retorna linhas inseridas
    @abstractmethod
    def query(self, sql: str) -> list[dict]: ...

class DuckDBRepository(BaseRepository):
    def __init__(self, path: str = ":memory:"):
        self.con = duckdb.connect(path)

    def load_csv(self, path: str, table: str) -> int:
        self.con.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} AS
            SELECT * FROM read_csv('{path}', delim=';', header=true,
                                   encoding='latin1', auto_detect=true)
            WHERE 1=0
        """)
        return self.con.execute(f"""
            INSERT INTO {table}
            SELECT * FROM read_csv('{path}', delim=';', header=true,
                                   encoding='latin1', auto_detect=true)
        """).rowcount
```

**`loader.py`**:
- Tipos de demonstrativo: `BPA`, `BPP`, `DRE`, `DFC_MD`, `DFC_MI`, `DRA`, `DMPL`, `DVA`
- Escopos: `con`, `ind`
- Nomear tabelas como `itr_bpa_con`, `itr_bpa_ind`, `dfp_bpa_con`, etc.
- Para cada CSV em `data/raw/{doc_type}/{year}/`, inserir na tabela correspondente
- `auto_detect=true` resolve schemas diferentes por tipo — **nunca assumir colunas iguais entre tipos**
- Logar contagem de linhas inseridas por arquivo

**⚠️ Atenção — Schemas heterogêneos por tipo de demonstrativo**

A referência completa de colunas está em `meta_itr_cia_aberta_*.txt`. Resumo das diferenças conhecidas:

| Tipo | Colunas padrão (14) | Colunas extras |
|---|---|---|
| BPA, BPP, DRE, DRA, DVA | ✅ sim | nenhuma |
| DFC_MD, DFC_MI | ✅ sim | nenhuma (mas estrutura hierárquica diferente entre MD e MI) |
| DMPL | ✅ sim + **extras** | Colunas adicionais por componente do PL: `CD_CONTA_PAI`, e valores por coluna do patrimônio (Capital Social, Reservas, etc.) — verificar `meta_itr_cia_aberta_DMPL.txt` |

Regra de implementação: o loader **nunca deve fazer `UNION` ou `INSERT` entre tabelas de tipos diferentes**. Cada tabela é independente e seu schema é definido na primeira carga via `CREATE TABLE IF NOT EXISTS … AS SELECT * FROM read_csv(…) WHERE 1=0`.

**CLI**: `cvmdata load [--year INT]`

**Critério de conclusão**: após `cvmdata load --year 2024`, `SELECT COUNT(*) FROM itr_bpa_con` retorna > 0; segunda execução não duplica linhas (verificar via count).

---

### Phase 3 — Normalize

**Objetivo**: deduplicar, padronizar tipos e preparar tabelas `*_clean` para cálculo.

**Arquivo**: `src/cvmdata/transform/normalize.py`

**Transformações**:
1. **Deduplicação** — para cada tabela `{prefix}_{type}_{scope}`:
   ```sql
   CREATE OR REPLACE TABLE {table}_clean AS
   SELECT * EXCLUDE (rn) FROM (
       SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
               ORDER BY VERSAO DESC
           ) AS rn
       FROM {table}
   ) WHERE rn = 1 AND ORDEM_EXERC = 'ÚLTIMO'
   ```
2. **Tipos**: `DT_REFER::DATE`, `DT_FIM_EXERC::DATE`, `VL_CONTA::DECIMAL(29,10)`
3. **CD_CVM**: `TRY_CAST(TRIM(CD_CVM) AS INTEGER)` — remove zeros à esquerda
4. **ESCALA_MOEDA**: registrar escala — não converter valores (manter tudo em R$ mil consistentemente; documentar no schema)

**CLI**: `cvmdata normalize`

**Critério de conclusão**: tabelas `*_clean` existem; `SELECT COUNT(*) FROM itr_bpa_con_clean WHERE ORDEM_EXERC != 'ÚLTIMO'` retorna 0.

---

### Phase 4 — Account Map

**Objetivo**: mapeamento `CD_CONTA → componente semântico` para extrair valores dos indicadores.

**Arquivo**: `src/cvmdata/transform/account_map.py`

```python
ACCOUNT_MAP: dict[str, str] = {
    # BPA — Balanço Patrimonial Ativo (confirmado nos dados CVM 2024)
    "1":        "ativo_total",
    "1.01":     "ativo_circulante",
    "1.01.01":  "caixa_equivalentes",
    "1.01.02":  "aplicacoes_financeiras",
    "1.01.04":  "estoques",
    "1.02":     "ativo_nao_circulante",
    "1.02.01":  "realizavel_longo_prazo",
    # BPP — Balanço Patrimonial Passivo (confirmado nos dados CVM 2024)
    "2":        "passivo_total",
    "2.01":     "passivo_circulante",
    "2.01.04":  "emprestimos_cp",
    "2.02":     "passivo_nao_circulante",
    "2.02.01":  "emprestimos_lp",
    "2.03":     "patrimonio_liquido",
    # DRE — Demonstração de Resultado (confirmado nos dados CVM 2024)
    "3.01":     "receita_liquida",
    "3.03":     "resultado_bruto",
    "3.05":     "ebit",
    "3.06.02":  "despesas_financeiras",
    "3.11":     "lucro_liquido",
    # TODO: sector_profile — verificar se bancos usam CD_CONTA diferente para empréstimos
    # Evidência necessária: testes com fixtures de bancos (BCO Brasil, BRB)
}

def get_component(cd_conta: str) -> str | None:
    """Retorna o nome do componente para um CD_CONTA.
    Tenta match exato; se não encontrar, tenta prefixo mais específico disponível.
    Retorna None se nenhum match for encontrado — logar como WARNING.
    """
```

**Critério de conclusão**: `get_component("1")` retorna `"ativo_total"`; `get_component("9.99.99")` retorna `None` sem exception.

---

### Phase 5 — Indicators Calculator

**Objetivo**: funções puras de cálculo + orquestrador que lê do DuckDB e salva resultados.

**Arquivo**: `src/cvmdata/transform/indicators.py`

**Funções puras** (todas retornam `float | None`):
```python
# ── Rentabilidade ─────────────────────────────────────────────────────────────
def roe(lucro_liquido, patrimonio_liquido) -> float | None:
    # Lucro Líquido / Patrimônio Líquido × 100  |  conta: 3.11 / 2.03

def roa(lucro_liquido, ativo_total) -> float | None:
    # Lucro Líquido / Ativo Total × 100  |  conta: 3.11 / 1

def margem_bruta(resultado_bruto, receita_liquida) -> float | None:
    # Resultado Bruto / Receita Líquida × 100  |  conta: 3.03 / 3.01

def margem_operacional(ebit, receita_liquida) -> float | None:
    # EBIT / Receita Líquida × 100  |  conta: 3.05 / 3.01

def margem_liquida(lucro_liquido, receita_liquida) -> float | None:
    # Lucro Líquido / Receita Líquida × 100  |  conta: 3.11 / 3.01

def giro_ativo(receita_liquida, ativo_total) -> float | None:
    # Receita Líquida / Ativo Total  |  conta: 3.01 / 1

# ── Liquidez ──────────────────────────────────────────────────────────────────
def liquidez_corrente(ativo_circulante, passivo_circulante) -> float | None:
    # AC / PC  |  conta: 1.01 / 2.01

def liquidez_seca(ativo_circulante, estoques, passivo_circulante) -> float | None:
    # (AC - Estoques) / PC  |  conta: (1.01 - 1.01.04) / 2.01

def liquidez_imediata(caixa_equivalentes, passivo_circulante) -> float | None:
    # Caixa / PC  |  conta: 1.01.01 / 2.01

def liquidez_geral(ativo_circulante, realizavel_lp, passivo_circulante, passivo_nao_circulante) -> float | None:
    # (AC + RLP) / (PC + PNC)  |  conta: (1.01 + 1.02.01) / (2.01 + 2.02)

# ── Endividamento ─────────────────────────────────────────────────────────────
def endividamento_geral(passivo_circulante, passivo_nao_circulante, ativo_total) -> float | None:
    # (PC + PNC) / AT × 100  |  conta: (2.01 + 2.02) / 1

def divida_bruta(emprestimos_cp, emprestimos_lp) -> float | None:
    # Emprést. CP + LP  |  conta: 2.01.04 + 2.02.01

def divida_liquida(emprestimos_cp, emprestimos_lp, caixa_equivalentes, aplicacoes_financeiras) -> float | None:
    # Dívida Bruta - Caixa - Aplicações  |  conta: (2.01.04+2.02.01) - 1.01.01 - 1.01.02

def divida_liquida_pl(divida_liq, patrimonio_liquido) -> float | None:
    # Dívida Líquida / PL  |  derivado / 2.03

def cobertura_juros(ebit, despesas_financeiras) -> float | None:
    # EBIT / Despesas Financeiras  |  conta: 3.05 / 3.06.02
```

**Schema da tabela `indicators`**:
```sql
CREATE TABLE IF NOT EXISTS indicators (
    cnpj_cia  VARCHAR NOT NULL,
    dt_refer  DATE    NOT NULL,
    indicador VARCHAR NOT NULL,
    valor     DOUBLE,
    PRIMARY KEY (cnpj_cia, dt_refer, indicador)
)
```

**Orquestrador** `calculate_all(cnpj: str | None, repo: BaseRepository)`:
- Se `cnpj` fornecido: processar apenas aquela empresa
- Se `cnpj = None`: processar todas as empresas distintas nas tabelas `*_clean`
- Para cada `(cnpj_cia, dt_refer)`: extrair componentes via `account_map`, calcular todos os 15 indicadores, fazer `INSERT OR REPLACE INTO indicators`
- Logar `WARNING` para cada componente não encontrado no `account_map`
- Nunca parar por empresa com dados incompletos — continuar para a próxima

**CLI**: `cvmdata indicators [--cnpj TEXT]`

**Critério de conclusão**: `cvmdata indicators --cnpj 00.000.000/0001-91` insere registros em `indicators` para BCO Brasil; valores de ROE e ROA são plausíveis (positivos para banco lucrativo).

---

### Phase 6 — Testes e Fixtures Multi-Setor

**Objetivo**: cobertura de testes ≥ 80% em `transform/`; descoberta empírica de diferenças de setor.

**Arquivos**: `tests/conftest.py`, `tests/fixtures/`, `tests/test_*.py`

**`conftest.py`**:
```python
import pytest, duckdb

@pytest.fixture
def repo():
    from cvmdata.db import DuckDBRepository
    return DuckDBRepository(":memory:")
```

**Fixtures CSV** — extrair linhas reais dos CSVs da CVM para:
- `tests/fixtures/sample_bank_bpa.csv` — BCO Brasil + BRB (bancos)
- `tests/fixtures/sample_bank_bpp.csv`
- `tests/fixtures/sample_bank_dre.csv`
- `tests/fixtures/sample_industrial_bpa.csv` — VALE ou PETROBRAS
- `tests/fixtures/sample_industrial_dre.csv`

**Testes**:
- `test_loader.py`: carregar fixture → verificar contagem de linhas e tipos de colunas
- `test_normalize.py`: inserir 2 versões da mesma conta → verificar que só a maior `VERSAO` persiste
- `test_indicators.py`:
  - Calcular ROE com valores conhecidos → verificar resultado matemático
  - Calcular com `patrimonio_liquido = 0` → verificar `None`
  - Calcular com conta ausente → verificar `None` sem exception
  - `@pytest.mark.xfail(reason="sector_profile pending")` para contas que diferem entre bancos e industriais

**Critério de conclusão**: `uv run pytest --tb=short` passa com ≥ 80% cobertura em `src/cvmdata/transform/`; testes `xfail` documentam diferenças de setor encontradas.

---

### Phase 7 — Documentação de Valuation (Trabalho Futuro)

**Objetivo**: documentar os indicadores de Valuation fora do escopo atual para referência futura.

**Arquivo**: `docs/valuation_future.md`

**Conteúdo**:
- Indicadores: P/L (`Preço / LPA`), P/VPA (`Preço / VPA`), Dividend Yield (`Div/Ação / Preço × 100`)
- Por que estão fora do escopo: requerem preço histórico da ação, não disponível nos dados CVM
- Dependência: mapeamento `CD_CVM → ticker B3` (ex: `1023` → `BBAS3`)
- Abordagem proposta: arquivo `config/tickers.yaml` com mapeamento manual + enriquecimento via `brapi.dev`
- Bibliotecas: `yfinance` (histórico OHLCV, sufixo `.SA`) e/ou `brapi.dev` (real-time, dividendos)
- Fórmulas completas: referência a `docs/analise_fundamentalista.md`

---

## CLI Reference (entregável final)

```bash
cvmdata download            # baixa ZIPs de 2021-2025 (ITR + DFP)
cvmdata download --year 2024  # baixa apenas 2024
cvmdata load                # ingere todos os CSVs em data/raw/
cvmdata load --year 2024    # ingere apenas 2024
cvmdata normalize           # dedup + limpeza de tipos
cvmdata indicators          # calcula indicadores para todas as empresas
cvmdata indicators --cnpj "00.000.000/0001-91"  # apenas BCO Brasil
```

```makefile
make install     # uv sync
make download    # uv run cvmdata download
make load        # uv run cvmdata load
make normalize   # uv run cvmdata normalize
make indicators  # uv run cvmdata indicators
make all         # download + load + normalize + indicators
make test        # uv run pytest --tb=short
make lint        # uv run ruff check src/ tests/
```

## Evolução Futura (fora do escopo da Fase 1)

| Fase | Entregável |
|---|---|
| 1.1 | Perfis de setor em `account_map.py` baseados nos `xfail` dos testes |
| 2 | Migração DuckDB → PostgreSQL via extensão `postgres`, Docker Compose, FastAPI REST |
| 3 | Dashboard React com séries históricas de indicadores |
| 4 | Indicadores de Valuation — ver `docs/valuation_future.md` |
