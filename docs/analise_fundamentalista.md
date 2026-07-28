
### Análise Fundamentalista

A análise fundamentalista utiliza indicadores extraídos de demonstrativos contábeis (Balanço Patrimonial, DRE, DFC) para avaliar a saúde e o valor real de uma empresa.

Os indicadores abaixo são todos **computáveis a partir dos arquivos CVM** (BPA + BPP + DRE + DFC).

#### 1. Rentabilidade

Avaliam a eficiência da empresa em gerar lucro a partir de seus recursos.

| Indicador | Fórmula | Contas CVM |
|---|---|---|
| **ROE** (Return on Equity) | `Lucro Líquido / Patrimônio Líquido × 100` | `3.11` / `2.03` |
| **ROA** (Return on Assets) | `Lucro Líquido / Ativo Total × 100` | `3.11` / `1` |
| **Margem Bruta** | `Resultado Bruto / Receita Líquida × 100` | `3.03` / `3.01` |
| **Margem Operacional** (EBIT) | `EBIT / Receita Líquida × 100` | `3.05` / `3.01` |
| **Margem Líquida** | `Lucro Líquido / Receita Líquida × 100` | `3.11` / `3.01` |
| **Giro do Ativo** | `Receita Líquida / Ativo Total` | `3.01` / `1` |

> **Decomposição DuPont:** ROE = Margem Líquida × Giro do Ativo × (Ativo Total / PL)

---

#### 2. Liquidez

Medem a capacidade da empresa de honrar suas obrigações financeiras.

| Indicador | Fórmula | Contas CVM |
|---|---|---|
| **Liquidez Corrente** | `Ativo Circulante / Passivo Circulante` | `1.01` / `2.01` |
| **Liquidez Seca** | `(Ativo Circulante − Estoques) / Passivo Circulante` | `(1.01 − 1.01.04)` / `2.01` |
| **Liquidez Imediata** | `Caixa e Equivalentes / Passivo Circulante` | `1.01.01` / `2.01` |
| **Liquidez Geral** | `(AC + Realizável LP) / (PC + Passivo Não Circ.)` | `(1.01 + 1.02.01)` / `(2.01 + 2.02)` |

---

#### 3. Endividamento

Analisa o nível de exposição financeira e dependência de capital de terceiros.

| Indicador | Fórmula | Contas CVM |
|---|---|---|
| **Endividamento Geral** | `(PC + PNC) / Ativo Total × 100` | `(2.01 + 2.02)` / `1` |
| **Dívida Bruta** | `Empréstimos CP + Empréstimos LP` | `2.01.04 + 2.02.01` |
| **Dívida Líquida** | `Dívida Bruta − Caixa − Aplicações Financeiras` | `(2.01.04 + 2.02.01) − 1.01.01 − 1.01.02` |
| **Dívida Líquida / PL** | `Dívida Líquida / Patrimônio Líquido` | derivado / `2.03` |
| **Cobertura de Juros** | `EBIT / Despesas Financeiras` | `3.05` / `3.06.02` |

---

#### 4. Indicadores fora do escopo atual

Documentados em [`docs/valuation_future.md`](./valuation_future.md).

| Indicador | Motivo |
|---|---|
| **P/L**, **P/VPA**, **Dividend Yield** | Requerem preço de ação (B3) |
| **EBITDA**, **Dívida Líquida / EBITDA**, **Margem EBITDA** | Requerem D&A do DFC — CD_CONTA não é padronizado entre empresas |

---

### Fontes de dados CVM utilizadas

| Arquivo | Frequência | Escopo | Uso |
|---|---|---|---|
| `ITR` — BPA/BPP/DRE `_con_` | Trimestral (Q1/Q2/Q3) | Consolidado | Balanço recente + YTD para TTM |
| `DFP` — BPA/BPP/DRE `_con_` | Anual (Q4 / exercício completo) | Consolidado | FY anterior para fórmula TTM e fallback |
| `DFP` — DFC-MI `_con_` | Anual | Consolidado | D&A para EBITDA (escopo futuro) |
| Qualquer arquivo `_ind_` | — | Individual | **Descartado** — metodologia usa apenas consolidado |

### Calendário fiscal

A `DT_REFER` do ITR não é fixo em março/junho/setembro

Valores observados no arquivo `itr_cia_aberta_BPA_con_2025.csv`:
`2025-03-31`, `2025-05-31`, `2025-06-30`, `2025-08-31`, `2025-09-30`, `2025-11-30`, `2025-12-31`.

> O ITR do 1º trimestre tem prazo legal de 45 dias após 31/03 (~15/05). Isso pode ajudar a explicar resultados nos meses 05, 08 e 11.

A regra invariante: **Q4 pode aparecer em ITR** — porem sempre o exercício completo no DFP, qualquer que seja o mês de encerramento.


## Metodologias implementadas

### Point-in-Time (PiT) — padrão atual

Calcula cada indicador usando exclusivamente os valores do `DT_REFER` solicitado.
Não há lookback — é uma foto dos fundamentos naquele momento.

- **Balanço (1.xx/2.xx):** snapshot do `DT_REFER`
- **Resultado (3.xx):** valor acumulado YTD do `DT_REFER` (pode ser sub-anual em ITRs)

Uso: backtesting, auditoria histórica, modelos quantitativos.

### Trailing Twelve Months (TTM)

Acumula os resultados dos últimos 12 meses encerrados, independentemente do ano fiscal.
Bancos as contas de fluxo ficam anualizadas. Balanço continua em snapshot.

- **Balanço (1.xx/2.xx):** snapshot do `DT_REFER` mais recente — **idêntico ao PiT**
- **Resultado (3.xx):** calculado pela fórmula abaixo

**Fórmula TTM para contas de resultado:**
```
TTM = YTD_atual + (FY_ano_anterior − YTD_mesmo_periodo_ano_anterior)
```

| Variável | Significado | Origem no banco |
|---|---|---|
| **YTD atual** | Valor acumulado do ano corrente até o período mais recente disponível (ex: jan–set) | `ORDEM_EXERC = 'ÚLTIMO'`, mesmo `DT_REFER` do período sendo calculado |
| **YTD anterior** (penúltimo) | Valor acumulado do mesmo intervalo (jan–set), mas do ano anterior — serve pra "descontar" a sobreposição | `ORDEM_EXERC = 'PENÚLTIMO'`, mesmo `DT_REFER` |
| **FY anterior** | Valor do ano fiscal completo anterior (jan–dez) | `ORDEM_EXERC = 'ÚLTIMO'` da linha DFP (`source = 'dfp'`) mais recente com `DT_FIM_EXERC` < `DT_REFER` do período atual |


**Exemplo — Petrobras Q3/2024 (`3.01` Receita Líquida):**
```
YTD_atual          = 369.561M  (ÚLTIMO,    DT_INI=2024-01-01, DT_FIM=2024-09-30)
FY_2023            = 511.994M  (DFP 2023,  DT_INI=2023-01-01, DT_FIM=2023-12-31)
YTD_2023_9m        = 377.736M  (PENÚLTIMO, DT_INI=2023-01-01, DT_FIM=2023-09-30)

TTM = 369.561 + (511.994 − 377.736) = 503.819M
```

_A lógica: pega o ano fiscal fechado anterior inteiro, tira o pedaço equivalente ao trecho já coberto pelo YTD atual (pra não contar duas vezes), e soma o que já foi realizado no ano corrente. Resultado: uma janela móvel de 12 meses._

**Fallback (quando faltam dados)**

```
sem YTD_atual            → retorna FY_anterior (se existir), senão None
sem FY_anterior          → retorna YTD_atual (proxy parcial)
sem YTD_anterior         → retorna FY_anterior (proxy sem ajuste)
todos presentes          → aplica a fórmula completa
```
