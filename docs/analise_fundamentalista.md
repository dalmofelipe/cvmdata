
### Análise Fundamentalista

A análise fundamentalista utiliza indicadores extraídos de demonstrativos contábeis (Balanço Patrimonial, DRE) para avaliar a saúde e o valor real de uma empresa.

Os indicadores abaixo são todos **computáveis a partir dos arquivos CVM** (BPA + BPP + DRE), sem necessidade de dados externos de mercado.

---

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

#### 4. Indicadores de Valuation — fora do escopo (requerem preço de ação)

Os indicadores abaixo dependem de dados de mercado não presentes nos arquivos CVM. Estão documentados em `docs/valuation_future.md`.

| Indicador | Dependência externa |
|---|---|
| **P/L** — `Preço / LPA` | Preço da ação (B3) |
| **P/VPA** — `Preço / VPA` | Preço da ação (B3) |
| **Dividend Yield** — `Div/Ação / Preço × 100` | Preço da ação + proventos (B3) |
| **Dívida Líquida / EBITDA** | EBITDA requer D&A da DFC (não baixamos) |

---

### Referências

- https://www.infomoney.com.br/guias/indicadores-fundamentalistas/

