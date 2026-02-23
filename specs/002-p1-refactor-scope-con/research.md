# Research: Correções de Corretude do Pipeline CVM

**Branch**: `002-p1-refactor-scope-con` | **Date**: 2026-02-22

## 1. DRE — Duas linhas por conta a partir de Q2 (P2-2A)

**Decision**: Usar `ORDER BY DT_INI_EXERC ASC, VERSAO DESC` na janela de deduplicação
de `raw_dre` (diferente do `ORDER BY VERSAO DESC` usado em BPA/BPP).

**Rationale**: A CVM grava dois registros por `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)`
a partir do Q2: um acumulado YTD (`DT_INI` = início do exercício) e um trimestral
(`DT_INI` = início do trimestre). Ambos têm exatamente o mesmo `VERSAO`, portanto
`ORDER BY VERSAO DESC` é não-determinístico. O acumulado YTD tem sempre a `DT_INI_EXERC`
mais antiga para aquele `DT_REFER`, independentemente do mês de início do ano fiscal.

**Verified with**: Dados reais Petrobras Q3/2024, conta `3.01`

| DT_INI_EXERC | VL_CONTA | Tipo |
|---|---|---|
| 2024-01-01 | 369.561M | YTD 9m ← **manter** |
| 2024-07-01 | 129.582M | Q3 isolado ← descartar |

**Alternatives considered**:
- `MONTH(DT_INI_EXERC) = 1` → ❌ Rejeitado: falha para empresas com ano fiscal não-janeiro
- Filtrar `DT_INI_EXERC = DATE_TRUNC('year', DT_FIM_EXERC)` → mais preciso mas mais complexo; `ASC` é equivalente e mais simples (constituição: YAGNI)
- Adicionar coluna booleana `is_ytd` → complexidade desnecessária

---

## 2. PENÚLTIMO deve sobreviver à normalização DRE (P2-2B dependency)

**Decision**: O filtro `ORDEM_EXERC = 'ÚLTIMO'` deve ser removido de `raw_dre_clean`.
A tabela DRE clean precisa conter **ambos** `ÚLTIMO` e `PENÚLTIMO` porque o TTM
usa o `PENÚLTIMO` como `YTD_mesmo_periodo_ano_anterior`.

**Rationale**: Em BPA e BPP, `PENÚLTIMO` é genuinamente redundante (balanço é snapshot).
Em DRE, `PENÚLTIMO` é o único lugar onde `YTD_anterior_mesmo_periodo` reside sem
precisar de cross-year join. Remover o filtro `ORDEM_EXERC` da DRE não aumenta
volumetria significativamente (2× no pior caso) mas elimina um join extra.

**Alternatives considered**:
- Guardar `PENÚLTIMO` em tabela separada → complexidade desnecessária; uma tabela com ambos é mais simples
- Cross-year join via anos anteriores → requer dois arquivos distintos carregados; mais frágil

---

## 3. TTM — Fórmula e lookup do FY anterior (P2-2B)

**Decision**: Implementar `_get_ttm_value(conn, cnpj, cd_conta, dt_refer)` que:
1. Lê `YTD_atual` → `ÚLTIMO` com `DT_INI_EXERC` mínimo para o `DT_REFER` do ITR
2. Lê `YTD_anterior` → `PENÚLTIMO` com `DT_INI_EXERC` mínimo para o mesmo `DT_REFER`
3. Determina `DT_FIM_FY_anterior` → `MAX(DT_FIM_EXERC) FROM raw_dre_clean WHERE CNPJ_CIA = ? AND source = 'dfp' AND DT_FIM_EXERC < DT_REFER`
4. Lê `FY_anterior` → `ÚLTIMO` com `DT_FIM_EXERC = DT_FIM_FY_anterior`
5. Retorna `YTD_atual + (FY_anterior - YTD_anterior)` com fallback para `FY_anterior` se `YTD_anterior` ausente

**Rationale**: Não assume mês de encerramento fiscal — usa `MAX(DT_FIM_EXERC)` do DFP
para localizar o exercício completo anterior. Funciona para qualquer ano fiscal.

**Fallback chain**:
1. TTM completo (ITR recente + DFP anterior disponíveis) → aplica fórmula
2. Apenas DFP disponível (sem ITR) → usa `FY_anterior` direto (proxy do ano)
3. Nenhum dado → `None`

**Integration point**: `_extract_components` será dividido em dois caminhos:
- Contas de balanço (1.xx, 2.xx): snapshot `ÚLTIMO` no `DT_REFER` (atual — sem mudança)
- Contas de resultado (3.xx): chama `_get_ttm_value` por conta

**Alternatives considered**:
- TTM por período de 4 trimestres (`Q4 = anual - Q1 - Q2 - Q3`) → requer 4 ITRs presentes; mais frágil
- Alterar schema `indicators` para guardar metodologia usada → útil mas P4+ de escopo

---

## 4. Batch query para calculate_all (P3)

**Decision**: Substituir o loop `for (cnpj, dt_refer) in pairs: _extract_components(...)` por
uma única query que retorna todos os `(CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA)` de uma vez.
Agrupar em Python com `dict` indexado por `(cnpj, dt_refer)`.

**Rationale**: DuckDB é OLAP — scans completos com filtragem colunar são ordens de
magnitude mais rápidos do que 10.000 consultas pontuais. O resultado cabe em memória
(~600 empresas × 20 períodos × 20 contas = 240.000 linhas × ~50 bytes ≈ 12 MB).

**Query batch**:
```sql
SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, VL_CONTA
FROM (
    SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpa_clean WHERE ORDEM_EXERC = 'ÚLTIMO'
    UNION ALL
    SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpp_clean WHERE ORDEM_EXERC = 'ÚLTIMO'
    UNION ALL
    SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_dre_clean WHERE ORDEM_EXERC = 'ÚLTIMO'
      AND DT_INI_EXERC = (
          SELECT MIN(DT_INI_EXERC) FROM raw_dre_clean d2
          WHERE d2.CNPJ_CIA = raw_dre_clean.CNPJ_CIA
            AND d2.DT_REFER  = raw_dre_clean.DT_REFER
            AND d2.CD_CONTA  = raw_dre_clean.CD_CONTA
            AND d2.ORDEM_EXERC = 'ÚLTIMO'
      )
)
[WHERE CNPJ_CIA = ?]
ORDER BY CNPJ_CIA, DT_REFER
```

**Note**: Com normalização DRE corrigida (P2-2A), `raw_dre_clean` já terá apenas a linha
YTD por grupo — o subquery de `MIN(DT_INI_EXERC)` no batch se torna desnecessário.
A batch query se simplifica para um UNION ALL direto sem a correlação.

**Alternatives considered**:
- DuckDB Relation API → equivalente, sem vantagem aqui; SQL mais legível
- `pandas.read_sql` → proibido pela constituição na ingestão; igualmente desnecessário aqui

---

## 5. Sequência de implementação recomendada

```
1. P2-2A  normalize.py — DRE SQL diferente (DT_INI_EXERC ASC + manter PENÚLTIMO)
   ↓ (testes passando)
2. P2-2B  indicators.py — _get_ttm_value + integração em _extract_components
   ↓ (testes passando)
3. P3     indicators.py — substitui loop por batch query
           (P3 fica mais simples porque raw_dre_clean já é determinístico após P2-2A)
```

P2-2A e P3 são **independentes** — podem ser paralelizados se desejado, mas
P2-2B depende de P2-2A estar estável.
