## Análise Fundamentalista

A análise fundamentalista utiliza indicadores extraídos de demonstrativos contábeis para avaliar a saúde e o valor real de uma empresa.

Os indicadores abaixo são todos **computáveis a partir dos arquivos CVM** (BPA + BPP + DRE + DFC).

<br>

### 1. Rentabilidade

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

<br>

### 2. Liquidez

Medem a capacidade da empresa de honrar suas obrigações financeiras.

| Indicador | Fórmula | Contas CVM |
|---|---|---|
| **Capital de Giro** | `Ativo Circulante − Passivo Circulante` | `1.01 − 2.01` |
| **Liquidez Corrente** | `Ativo Circulante / Passivo Circulante` | `1.01` / `2.01` |
| **Liquidez Seca** | `(Ativo Circulante − Estoques) / Passivo Circulante` | `(1.01 − 1.01.04)` / `2.01` |
| **Liquidez Imediata** | `Caixa e Equivalentes / Passivo Circulante` | `1.01.01` / `2.01` |
| **Liquidez Geral** | `(AC + Realizável LP) / (PC + Passivo Não Circ.)` | `(1.01 + 1.02.01)` / `(2.01 + 2.02)` |

<br>

### 3. Endividamento

Analisa o nível de exposição financeira e dependência de capital de terceiros.

| Indicador | Fórmula | Contas CVM |
|---|---|---|
| **Endividamento Geral** | `(PC + PNC) / Ativo Total × 100` | `(2.01 + 2.02)` / `1` |
| **Endividamento / PL** | `(PC + PNC) / Patrimônio Líquido × 100` | `(2.01 + 2.02)` / `2.03` |
| **Dívida Bruta** | `Empréstimos CP + Empréstimos LP` | `2.01.04 + 2.02.01` |
| **Dívida Líquida** | `Dívida Bruta − Caixa − Aplicações Financeiras` | `(2.01.04 + 2.02.01) − 1.01.01 − 1.01.02` |
| **Dívida Líquida / PL** | `Dívida Líquida / Patrimônio Líquido` | derivado / `2.03` |
| **Cobertura de Juros** | `EBIT / Despesas Financeiras` | `3.05` / `3.06.02` |

<br>

### 4. Retorno sobre o capital investido

O **ROIC** (Return on Invested Capital) mede o retorno operacional depois dos
impostos sobre o capital investido. No código, ele é calculado em duas etapas:

1. A taxa efetiva de IR/CSLL é `−Imposto de Renda e CSLL / Resultado Antes dos Tributos`.
   Quando o resultado antes dos tributos é menor ou igual a zero, a taxa não é
   considerada válida e o ROIC não é calculado.
2. O NOPAT (Net Operating Profit After Taxes) é `EBIT × (1 − taxa efetiva)`.

Com isso:

| Indicador | Fórmula | Contas CVM |
|---|---|---|
| **ROIC** | `NOPAT / Capital Investido × 100` | `EBIT`, `IR/CSLL`, `resultado antes dos tributos`, `PL`, `empréstimos CP`, `empréstimos LP` |

O capital investido usado pelo cálculo é:

```text
Capital Investido = Patrimônio Líquido + Empréstimos CP + Empréstimos LP
```

`EBIT`, `IR/CSLL` e `resultado antes dos tributos` são componentes da DRE. Os
dois últimos são localizados pela descrição normalizada da conta, pois não há
um código único confiável entre os layouts. Esses componentes são
intermediários: não são gravados como indicadores separados.

<br>

### 5. Indicadores fora do escopo atual

Documentados em [`docs/valuation_future.md`](./valuation_future.md).

| Indicador | Motivo |
|---|---|
| **P/L**, **P/VPA**, **Dividend Yield** | Requerem preço de ação (B3) |
| **EBITDA**, **Dívida Líquida / EBITDA**, **Margem EBITDA** | Requerem D&A do DFC — CD_CONTA não é padronizado entre empresas |

<br>
