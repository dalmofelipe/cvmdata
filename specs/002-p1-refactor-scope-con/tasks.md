# Tasks: Correções de Corretude do Pipeline CVM

**Branch**: `002-p1-refactor-scope-con`
**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [quickstart.md](quickstart.md)
**Status**: P1 + P4 já implementados neste branch. Tarefas abaixo cobrem os itens pendentes.

---

## Phase 1: Setup

**Purpose**: Verificar que a base dos itens já feitos está sólida antes de avançar.

- [X] T001 Executar `uv run pytest tests/ -v` e confirmar suite verde (base para novos testes)

---

## Phase 2: Fundacional (pré-requisito bloqueante para US2 e US3)

**Purpose**: Separar os dois templates SQL de normalização — BPA/BPP (atual) e DRE (novo).
Esta separação é pré-requisito para US1 (deduplicação correta), que por sua vez bloqueia
US2 (TTM) e simplifica US3 (batch).

**⚠️ CRÍTICO**: US2 não pode ser implementado sem este passo — `PENÚLTIMO` precisa sobreviver
à normalização DRE para que a fórmula TTM acesse `YTD_anterior_mesmo_periodo`.

- [X] T002 Renomear `_NORMALIZE_SQL` para `_NORMALIZE_BALANCE_SQL` em `src/cvmdata/transform/normalize.py` (sem mudança de lógica — apenas renomeação)
- [X] T003 Adicionar `_NORMALIZE_FLOW_SQL` em `src/cvmdata/transform/normalize.py` com `ORDER BY DT_INI_EXERC ASC, VERSAO DESC` e sem filtro `ORDEM_EXERC`
- [X] T004 Atualizar `normalize_table` em `src/cvmdata/transform/normalize.py` para selecionar o SQL correto baseado em `table.endswith('dre')`; atualizar docstring do módulo para indicar que o filtro `ORDEM_EXERC = 'ÚLTIMO'` se aplica apenas a BPA/BPP (DRE preserva ambos `ÚLTIMO` e `PENÚLTIMO`)

**Checkpoint**: `normalize_table('raw_dre', conn)` usa o novo SQL; `raw_bpa`/`raw_bpp` continuam com o SQL original.

---

## Phase 3: User Story 1 — DRE deduplicação determinística (P2-2A) 🎯 MVP

**Goal**: `raw_dre_clean` sempre retém a linha YTD (DT_INI_EXERC mais antigo) e preserva
`PENÚLTIMO` para uso no TTM. Sem este fix, indicadores de resultado podem divergir ~3× do valor correto.

**Independent Test**: Criar fixture DRE com duas linhas para mesmo grupo (`DT_INI_EXERC = 2024-01-01`
e `2024-07-01`) → após `normalize_table('raw_dre', ...)` → `raw_dre_clean` deve ter apenas a
linha com `DT_INI_EXERC = 2024-01-01` e valor 369.561M.

- [X] T005 [US1] Adicionar helper `_make_dre_csv` em `tests/test_normalize.py` com fixture que produz duas linhas por conta para o mesmo `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)` diferindo em `DT_INI_EXERC` (ex: Q2 com YTD e trimestral)
- [X] T006 [US1] Adicionar teste `test_normalize_dre_retains_ytd` em `tests/test_normalize.py`: fixture com YTD (369M) e trimestral (129M) → `raw_dre_clean` retém apenas YTD
- [X] T007 [P] [US1] Adicionar teste `test_normalize_dre_preserves_penultimo` em `tests/test_normalize.py`: `PENÚLTIMO` deve estar presente em `raw_dre_clean` após normalização
- [X] T008 [P] [US1] Adicionar teste `test_normalize_dre_non_january_fiscal_year` em `tests/test_normalize.py`: empresa com `DT_INI_EXERC = 2024-04-01` (fiscal abril) → linha com `2024-04-01` ganha sobre `2024-07-01`
- [X] T009 [P] [US1] Adicionar teste `test_normalize_balance_still_filters_penultimo` em `tests/test_normalize.py`: confirmar que BPA/BPP continuam descartando `PENÚLTIMO` (regressão)
- [X] T010 [US1] Adicionar teste `test_normalize_dre_q1_single_line` em `tests/test_normalize.py`: DRE Q1 com uma única linha por conta não causa erro (YTD = trimestral neste caso)
- [X] T011 [US1] Confirmar todos os testes de `tests/test_normalize.py` passando com `uv run pytest tests/test_normalize.py -v`

**Checkpoint**: `raw_dre_clean` é determinístico e contém `PENÚLTIMO`. US1 independentemente testável.

---

## Phase 4: User Story 2 — TTM para contas de resultado (P2-2B)

**Goal**: ROE, ROA, margens e Cobertura de Juros passam a usar 12 meses completos (TTM)
em vez do YTD parcial do ITR. Eliminação da divergência ~2-3× vs Status Invest / Investidor10.

**Depends on**: Phase 3 completo (`PENÚLTIMO` disponível em `raw_dre_clean`).

**Independent Test**: Fixture com Petrobras Q3/2024 (YTD=369M, PENÚLTIMO=377M, FY_2023=494M) →
`_get_ttm_value(..., '3.01', '2024-09-30')` retorna `486M` (TTM = 369 + 494 − 377).

- [X] T012 [US2] Adicionar constante `DRE_ACCOUNTS: frozenset[str]` em `src/cvmdata/transform/indicators.py` com os nomes semânticos das contas 3.xx do `ACCOUNT_MAP` (`receita_liquida`, `resultado_bruto`, `ebit`, `despesas_financeiras`, `lucro_liquido`)
- [X] T013 [US2] Implementar `_get_ttm_value(conn, cnpj, dt_refer, cd_conta) -> float | None` em `src/cvmdata/transform/indicators.py` com fórmula TTM completa e fallback chain (TTM → FY → YTD parcial → None)
- [X] T014 [US2] Atualizar `_extract_components` em `src/cvmdata/transform/indicators.py` para chamar `_get_ttm_value` para contas em `DRE_ACCOUNTS` em vez de ler diretamente de `raw_dre_clean`
- [X] T015 [P] [US2] Adicionar teste `test_ttm_full` em `tests/test_indicators.py`: YTD=369, FY=494, YTD_ant=377 → `_get_ttm_value` retorna 486 (valores Petrobras Q3/2024, conta 3.01)
- [X] T016 [P] [US2] Adicionar teste `test_ttm_fallback_no_penultimo` em `tests/test_indicators.py`: sem `PENÚLTIMO` → retorna FY direto (494)
- [X] T017 [P] [US2] Adicionar teste `test_ttm_fallback_no_dfp` em `tests/test_indicators.py`: sem DFP anterior → retorna YTD parcial (369)
- [X] T018 [P] [US2] Adicionar teste `test_ttm_fallback_no_itr` em `tests/test_indicators.py`: sem ITR (só DFP) → retorna FY direto
- [X] T019 [P] [US2] Adicionar teste `test_ttm_non_december_fiscal_year` em `tests/test_indicators.py`: empresa com `MAX(DT_FIM_EXERC)` em março → localiza corretamente FY anterior
- [X] T019b [P] [US2] Adicionar teste `test_ttm_two_dfps_selects_correct_fy` em `tests/test_indicators.py`: banco com dois DFPs em anos distintos (ex: FY 2022 e FY 2023) → `_get_ttm_value` seleciona o `MAX(DT_FIM_EXERC) < DT_REFER` correto (FY 2023 para ITR Q3/2024)
- [X] T020 [US2] Confirmar testes de `tests/test_indicators.py` passando com `uv run pytest tests/test_indicators.py -v`

**Checkpoint**: Indicadores de resultado calculados com TTM. US2 independentemente verificável.

---

## Phase 5: User Story 3 — Batch query em `calculate_all` (P3)

**Goal**: Substituir N×3 round-trips DuckDB→Python por uma única query batch.
Ganho esperado: 100–1000× em tempo de execução para base completa.

**Depends on**: Phase 4 completo (P3 é mais simples após `raw_dre_clean` estar determinístico).

**Independent Test**: Monkeypatch `conn.execute` para contar chamadas → `calculate_all()` deve
disparar no máximo 2 queries de data fetch — uma batch para BPA/BPP e uma para DRE (independente do número de empresas/períodos).

- [X] T021 [US3] Implementar `_fetch_all_components(conn, cnpj=None) -> dict[tuple[str,str], dict[str,float|None]]` em `src/cvmdata/transform/indicators.py`: query batch única com UNION ALL de `raw_bpa_clean` + `raw_bpp_clean` retornando `{(cnpj, dt_refer): {componente: valor}}`
- [X] T022 [US3] Implementar `_fetch_all_dre_components(conn, cnpj=None) -> dict[tuple[str,str], dict[str, float|None]]` em `src/cvmdata/transform/indicators.py`: query batch para contas DRE usando `ORDEM_EXERC IN ('ÚLTIMO', 'PENÚLTIMO')`, agrupando por `(cnpj, dt_refer, ordem_exerc)` para TTM em memória
- [X] T023 [US3] Refatorar `calculate_all` em `src/cvmdata/transform/indicators.py` para usar `_fetch_all_components` + `_fetch_all_dre_components` em vez do loop com `_extract_components` por par `(cnpj, dt_refer)`
- [X] T024 [US3] Remover `_extract_components` de `src/cvmdata/transform/indicators.py` (substituído pelo batch) e atualizar todos os call-sites em `tests/test_indicators.py` que invocam `_extract_components` diretamente
- [X] T025 [P] [US3] Adicionar teste `test_calculate_all_regression` em `tests/test_indicators.py`: verificar que `calculate_all` com 3 empresas × 2 períodos dispara no máximo 2 queries DuckDB (monkeypatch `conn.execute`) E produz os mesmos valores de indicadores que a implementação anterior
- [X] T026 [US3] Confirmar suite completa passando com `uv run pytest tests/ -v`

**Checkpoint**: `calculate_all` completa em < 10s para base completa. US3 verificável por tempo de execução.

---

## Phase Final: Polish & Validação Cruzada

- [X] T027 [P] Executar `uv run ruff check src/ tests/` e corrigir warnings restantes
- [X] T028 [P] Executar `uv run cvmdata load --year 2024 && uv run cvmdata normalize && uv run cvmdata indicators` com dados reais para confirmar pipeline end-to-end
- [X] T029 Consultar `uv run cvmdata query --cnpj "33.000.167/0001-01"` (Petrobras) e comparar `margem_liquida` Q3/2024 com Status Invest — divergência esperada < 5% após TTM
- [X] T030 [P] Executar `uv run pytest tests/ --cov=src/cvmdata/transform --cov-fail-under=80` e confirmar cobertura ≥ 80% em `transform/` (gate da Constituição V)

---

## Dependências entre histórias

```
Phase 2 (Fundacional — separar SQLs)
  └─ US1 (P2-2A — DRE deduplicação YTD + PENÚLTIMO)
        └─ US2 (P2-2B — TTM nos indicadores)
              └─ US3 (P3 — batch query, mais simples após clean DRE determinístico)
```

**Paralelismo disponível dentro de cada fase**: T005–T010 (testes US1), T015–T019 (testes US2), T021–T022 (batch queries US3) podem ser escritos em paralelo entre si.

## Exemplos de execução paralela

**Dentro de US1** (após T005 helper criado):
```
T006 ──┐
T007 ──┤── podem ser escritos simultaneamente (arquivos de teste diferentes seria ideal,
T008 ──┤    mas são funções independentes no mesmo arquivo test_normalize.py)
T009 ──┤
T010 ──┘
T011 (bloqueia — roda todos)
```

**Dentro de US2** (após T012–T014 implementados):
```
T015 ──┐
T016 ──┤── testes independentes (dados de fixture distintos)
T017 ──┤
T018 ──┘
T019 (ano fiscal não-dezembro — dado diferente, paralelo)
T020 (bloqueia — roda todos)
```

## Contagem de tarefas

| Fase | Tarefas | Paralelas |
|------|---------|-----------|
| Setup | 1 | 0 |
| Fundacional | 3 | 0 |
| US1 (P2-2A) | 7 | 5 |
| US2 (P2-2B) | 10 | 6 |
| US3 (P3) | 6 | 2 |
| Polish | 4 | 3 |
| **Total** | **31** | **16** |

## MVP sugerido

**US1 completo** (T001–T011): corrige o bug mais silencioso e crítico — deduplicação DRE não-determinística que pode divergir 3× nos indicadores de resultado. Entregável independente e verificável sem US2/US3.
