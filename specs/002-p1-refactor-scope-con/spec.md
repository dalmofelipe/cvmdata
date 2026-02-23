# Feature Specification: Correções de Corretude do Pipeline CVM

**Feature Branch**: `002-p1-refactor-scope-con`
**Created**: 2026-02-22
**Status**: In Progress — P1/P4 implementados; P2-2A, P2-2B, P3 pendentes

## Context

Análise dos dados reais CVM (documentada em `PLAN.md`) identificou quatro problemas
no pipeline, ordenados por impacto na corretude dos resultados.

**Status de implementação:**

| Item | Problema | Status |
|------|----------|--------|
| P1   | `_ind_` misturado com `_con_` no load/normalização | ✅ DONE |
| P4   | Load persistia todas as contas — ~80% irrelevantes | ✅ DONE |
| P2-2A | DRE: `ROW_NUMBER` não-determinístico entre YTD e trimestral | ⏳ pendente |
| P2-2B | Indicadores de resultado usam YTD parcial em vez de TTM anualizado | ⏳ pendente |
| P3   | N×3 queries DuckDB→Python (10.000 round-trips para 500 empresas) | ⏳ pendente |

## User Scenarios — Itens Pendentes

### User Story 1 — DRE deduplicação determinística (P2-2A)

Como pipeline, quero que cada conta DRE tenha exatamente um valor por
`(CNPJ_CIA, DT_REFER, ORDEM_EXERC)` e que esse valor seja sempre o acumulado YTD
(não o trimestral isolado), para que os indicadores de resultado sejam calculados
sobre o período certo.

**Acceptance Scenarios:**

1. **Given** um arquivo DRE com duas linhas para o mesmo `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC='ÚLTIMO')`
   diferindo apenas em `DT_INI_EXERC` (ex: `2024-01-01` e `2024-07-01`),
   **When** `normalize_table('raw_dre', conn)` é executado,
   **Then** apenas a linha com `DT_INI_EXERC = 2024-01-01` (a mais antiga) sobra em `raw_dre_clean`

2. **Given** a mesma situação,
   **Then** o valor YTD (369.561M) é preservado — não o trimestral (129.582M)

3. **Given** empresa com ano fiscal não-janeiro (ex: início em abril),
   **When** normalização é executada,
   **Then** a linha com `DT_INI_EXERC` mais antigo para aquele `DT_REFER` é preservada
   (e.g.: `2024-04-01` ganha sobre `2024-07-01`)

### User Story 2 — TTM para contas de resultado (P2-2B)

Como analista, quero que ROE, ROA, margens e demais indicadores de resultado (3.xx)
sejam calculados sobre 12 meses completos (TTM), independentemente de o dado mais
recente ser um ITR trimestral, para comparar empresas com anos fiscais diferentes
sem distorção por sub-anualização.

**Fórmula:**
```
TTM = YTD_atual + (FY_ano_anterior − YTD_mesmo_periodo_ano_anterior)
```

**Acceptance Scenarios:**

1. **Given** Petrobras com ITR Q3/2024 no banco e DFP 2023 disponível,
   **When** `calculate_all` é executado,
   **Then** `receita_liquida` usada nos indicadores é o valor TTM = **486.468M**
   (= 369.561 + 494.643 − 377.736; não os 369.561M do YTD 9m de 2024)

2. **Given** empresa com somente DFP disponível (sem ITR recente),
   **When** `calculate_all` é executado,
   **Then** o FY anual do DFP é usado diretamente como proxy do ano (fallback)

3. **Given** empresa com ano fiscal encerrado em março (não dezembro),
   **When** TTM é calculado,
   **Then** `FY_ano_anterior` é localizado pelo `MAX(DT_FIM_EXERC)` do DFP daquela empresa
   (não assume `DT_FIM_EXERC = 31/dez`)

4. **Given** `PENÚLTIMO` ausente na tabela `raw_dre_clean` (empresa está no primeiro ano de dados carregados — sem exercício anterior disponível),
   **Then** TTM retorna `None` e fallback para FY direto é aplicado

### User Story 3 — Performance: batch query nos indicadores (P3)

Como operador do pipeline, quero que `calculate_all` para 500 empresas × 20 períodos
complete em segundos, não minutos, para que o pipeline seja executável diariamente.

**Acceptance Scenarios:**

1. **Given** base com 500 empresas × 20 períodos,
   **When** `calculate_all()` é executado,
   **Then** no máximo **2 queries SQL** são disparadas contra o DuckDB (não 10.000): uma para contas de balanço (BPA/BPP) e outra para contas de resultado (DRE)

2. **Given** flag `--cnpj` fornecida,
   **Then** cada query adiciona `WHERE CNPJ_CIA = ?` antes de trazer os dados

## Edge Cases

- Empresa que publicou apenas DFP (sem nenhum ITR no banco) → fallback para FY direto
- `PENÚLTIMO` ausente porque a empresa está no primeiro ano de dados carregados → TTM = None, FY fallback
- Empresa com dois DFPs distintos em anos diferentes — usar o de `MAX(DT_FIM_EXERC)` relativo ao ITR corrente
- DRE de Q1 tem uma única linha por `CD_CONTA` (YTD = trimestral) — deduplicação deve funcionar sem errar
