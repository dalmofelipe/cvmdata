## Demonstrativos CVM

## Fontes de dados CVM utilizadas

| Arquivo | Frequência | Escopo | Uso |
|---|---|---|---|
| `ITR` — BPA/BPP/DRE `_con_` | Trimestral (Q1/Q2/Q3) | Consolidado | Balanço recente + YTD para TTM |
| `DFP` — BPA/BPP/DRE `_con_` | Anual (Q4 / exercício completo) | Consolidado | FY anterior para fórmula TTM e fallback |
| `DFP` — DFC-MI `_con_` | Anual | Consolidado | D&A para EBITDA (escopo futuro) |
| Qualquer arquivo `_ind_` | — | Individual | **Descartado** — metodologia usa apenas consolidado |


## Calendário fiscal

A `DT_REFER` dos demonstrativos não é fixo em março/junho/setembro

Valores observados no arquivo `itr_cia_aberta_BPA_con_2025.csv`:
`2025-03-31`, `2025-05-31`, `2025-06-30`, `2025-08-31`, `2025-09-30`, `2025-11-30`, `2025-12-31`.

> O ITR do 1º trimestre tem prazo legal de 45 dias após 31/03 (~15/05). Isso pode ajudar a explicar resultados nos meses 05, 08 e 11.

A regra invariante: **Q4 pode aparecer em ITR** — porem sempre o exercício completo no DFP, qualquer que seja o mês de encerramento.
