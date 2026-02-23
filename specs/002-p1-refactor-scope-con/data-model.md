# Data Model: Correções de Corretude do Pipeline CVM

**Branch**: `002-p1-refactor-scope-con` | **Date**: 2026-02-22

## Schema changes

Nenhuma tabela nova é criada. As mudanças são comportamentais nas tabelas existentes.

---

## `raw_dre_clean` — comportamento alterado

Esta é a única tabela _clean cujo conteúdo muda.

### Antes (buggy)

```
raw_dre_clean
─────────────────────────────────────────────────────────────────────
CNPJ_CIA | DT_REFER   | CD_CONTA | ORDEM_EXERC | DT_INI_EXERC | VL_CONTA
─────────────────────────────────────────────────────────────────────
PETR4    | 2024-09-30 | 3.01     | ÚLTIMO      | ???          | 129.582M  ← pode ser o trimestral!
PETR4    | 2024-06-30 | 3.01     | ÚLTIMO      | ???          | 239.979M  ← pode ser o semestral ✓ ou o trimestral ✗
─────────────────────────────────────────────────────────────────────
Sem PENÚLTIMO — filtrado por ORDEM_EXERC = 'ÚLTIMO'
```

Problemas:
- `ROW_NUMBER` não-determinístico → pode selecionar valor trimestral (129M) em vez de YTD (369M)
- `PENÚLTIMO` descartado → impossibilita TTM (YTD ano anterior é inacessível)

### Depois (correto)

```
raw_dre_clean
─────────────────────────────────────────────────────────────────────
CNPJ_CIA | DT_REFER   | CD_CONTA | ORDEM_EXERC | DT_INI_EXERC | VL_CONTA
─────────────────────────────────────────────────────────────────────
PETR4    | 2024-09-30 | 3.01     | ÚLTIMO      | 2024-01-01   | 369.561M  ← YTD garantido
PETR4    | 2024-09-30 | 3.01     | PENÚLTIMO   | 2023-01-01   | 377.736M  ← YTD ano anterior (TTM)
PETR4    | 2024-06-30 | 3.01     | ÚLTIMO      | 2024-01-01   | 239.979M  ← YTD garantido
PETR4    | 2024-06-30 | 3.01     | PENÚLTIMO   | 2023-01-01   | 216.341M  ← YTD ano anterior (TTM)
─────────────────────────────────────────────────────────────────────
DFP rows (source='dfp'):
PETR4    | 2023-12-31 | 3.01     | ÚLTIMO      | 2023-01-01   | 494.643M  ← FY 2023 completo
```

### SQL de normalização DRE (novo)

```sql
-- Deduplicação específica para DRE: DT_INI_EXERC ASC garante YTD sobre trimestral
-- Sem filtro ORDEM_EXERC — PENÚLTIMO é preservado para TTM
CREATE OR REPLACE TABLE raw_dre_clean AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT
        * REPLACE (
            VL_CONTA::DECIMAL(29, 10)         AS VL_CONTA,
            TRY_CAST(TRIM(CD_CVM) AS INTEGER) AS CD_CVM
        ),
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
            ORDER BY DT_INI_EXERC ASC, VERSAO DESC  -- ← YTD tem DT_INI mais antigo
        ) AS rn
    FROM raw_dre
)
WHERE rn = 1
-- SEM filtro ORDEM_EXERC — preserva PENÚLTIMO para TTM
```

---

## `raw_bpa_clean` / `raw_bpp_clean` — sem mudança de comportamento

O SQL de normalização de BPA e BPP permanece igual:
```sql
ROW_NUMBER() OVER (
    PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
    ORDER BY VERSAO DESC     -- ← deduplicação por versão apenas (ok: sem ambiguidade YTD/trim)
) AS rn
WHERE rn = 1 AND ORDEM_EXERC = 'ÚLTIMO'
```

---

## `indicators` — sem mudança de schema

```sql
-- Schema atual — mantido
CREATE TABLE IF NOT EXISTS indicators (
    cnpj_cia  VARCHAR NOT NULL,
    dt_refer  DATE    NOT NULL,
    indicador VARCHAR NOT NULL,
    valor     DOUBLE,
    PRIMARY KEY (cnpj_cia, dt_refer, indicador)
);
```

O `valor` de indicadores de resultado (3.xx) passará a ser o TTM em vez do YTD parcial.
Não há mudança de schema — apenas mudança dos valores calculados.

---

## Impacto em volumetria

| Tabela | Antes | Depois | Delta |
|--------|-------|--------|-------|
| `raw_dre_clean` | apenas `ÚLTIMO` (1 linha/conta/período) | `ÚLTIMO` + `PENÚLTIMO` | ~2× linhas |
| `raw_bpa_clean` | sem mudança | sem mudança | = |
| `raw_bpp_clean` | sem mudança | sem mudança | = |
| `indicators` | valores YTD parciais | valores TTM | = linhas, valores corretos |

O aumento de `raw_dre_clean` é aceitável. DRE tem apenas 5 contas no ACCOUNT_MAP;
2× de 5 contas por empresa/período é insignificante comparado ao custo de um join
cross-year alternativo.

---

## Entidades envolvidas nos novos cálculos TTM

```
raw_dre_clean
├── ÚLTIMO   (DT_INI_EXERC mínimo para o DT_REFER)  → YTD_atual
├── PENÚLTIMO (DT_INI_EXERC mínimo para o DT_REFER)  → YTD_anterior_mesmo_periodo
└── ÚLTIMO   (DT_FIM_EXERC = MAX DFP para a empresa) → FY_ano_anterior
         ↑ source='dfp' + ORDEM_EXERC='ÚLTIMO'

TTM = YTD_atual + (FY_ano_anterior - YTD_anterior_mesmo_periodo)
```

Todos os dados já existem em `raw_dre_clean` após a correção de normalização —
não é necessário consultar `raw_dre` (tabela bruta) nos cálculos de indicadores.
