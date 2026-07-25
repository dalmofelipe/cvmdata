# Indicadores de Valuation — Trabalho Futuro

> **Status**: fora do escopo do pipeline atual (`001-cvm-pipeline`).
> Os indicadores abaixo requerem dados de mercado (preço da ação, proventos distribuídos) que **não estão presentes nos arquivos CVM**. Este documento serve como referência de design para a iteração seguinte.

---

## 1. Indicadores e Fórmulas

Os três indicadores de valuation mais utilizados dependem do preço corrente (ou histórico) da ação na B3.

| Indicador | Fórmula | Componentes CVM | Componente externo |
|---|---|---|---|
| **P/L** (Preço / Lucro) | `Preço / LPA` | `LPA = Lucro Líquido (3.11) / nº ações` | Preço da ação (B3) |
| **P/VPA** (Preço / Valor Patrimonial) | `Preço / VPA` | `VPA = PL (2.03) / nº ações` | Preço da ação (B3) |
| **Dividend Yield** | `(Dividendos por ação / Preço) × 100` | Dividendos pagos (não consta nas demonstrações CVM baixadas) | Preço + proventos (B3) |

> **Nota sobre nº de ações**: O arquivo de **composição de capital** foi integrado ao pipeline, processando quantidades total de ações Ordinárias e Preferências, tanto de capital integrado quanto tesouraria.

> **Tickers das ações**: A integração de tickers da B3 esta implementada ao `cvmdata`. Mais detalhes na sessão 4 desde documento.

### Limitações adicionais

- **DL/EBITDA**: EBITDA = EBIT + D&A; análise completa do DFC e estratégia de extração de D&A documentadas na seção 2 deste arquivo.
- **EV/EBITDA**: requer Enterprise Value = market cap + dívida líquida. Depende de preço de ação.

---

## 2. DFC — Demonstração de Fluxos de Caixa (prerequisito para EBITDA)

O DFC é necessário para extrair **D&A** (Depreciação e Amortização), que compõe o EBITDA.

### Disponibilidade

| Fonte | DFC existe? | Observação |
|---|---|---|
| **ITR** (Q1/Q2/Q3) | **Não** | ITR não publica DFC |
| **DFP** (anual) | Sim | Único ponto de coleta — EBITDA só pode ser calculado com base anual |

### Métodos (mutuamente exclusivos por empresa)

| Método | Arquivo | Empresas (DFP 2024) | Detalha D&A? |
|---|---|---|---|
| **DFC-MI** — Método Indireto | `DFC_MI_con` | **449 (96%)** | Sim, em subcontas de `6.01.01` |
| **DFC-MD** — Método Direto | `DFC_MD_con` | 16 (4%) | **Não** — só top-level |

### Contas padronizadas (válidas para ambos os métodos)

| CD_CONTA | Descrição |
|---|---|
| `6.01` | Caixa Líquido Atividades Operacionais |
| `6.02` | Caixa Líquido Atividades de Investimento |
| `6.03` | Caixa Líquido Atividades de Financiamento |
| `6.05.01` | Saldo Inicial de Caixa e Equivalentes |
| `6.05.02` | Saldo Final de Caixa e Equivalentes |

### D&A — CD_CONTA NÃO padronizado

O `CD_CONTA` para Depreciação e Amortização varia por empresa dentro do bloco `6.01.01`.
Dados reais do DFP 2024 (449 empresas com DFC-MI):

| CD_CONTA mais frequente | Ocorrências | Exemplo DS_CONTA |
|---|---|---|
| `6.01.01.02` | ~420 empresas | "Depreciação e amortização" |
| `6.01.01.03` | ~126 empresas | "Depreciação e amortização" |
| `6.01.01.04` | ~38 empresas | "Depreciação, depleção e amortização" (ex: Petrobras) |
| outros (`.01`, `.05`, `.06`) | < 10 cada | variações menores |

**584 variações distintas** de (CD_CONTA, DS_CONTA) identificadas. Mapeamento por CD_CONTA fixo não é viável.

**Estratégia necessária:** filtrar `CD_CONTA LIKE '6.01.01.%'` + keyword em `DS_CONTA`
(termos: `deprecia`, `amortiza`, `deplec`, `exaust`) com lógica de fallback por empresa.

### Fórmulas dependentes de DFC

| Indicador | Fórmula | Contas CVM |
|---|---|---|
| **EBITDA** | `EBIT + D&A` | `3.05` + `6.01.01.xx` (via DS_CONTA) |
| **Dívida Líquida / EBITDA** | `Dívida Líquida / EBITDA` | derivado / derivado |
| **Margem EBITDA** | `EBITDA / Receita Líquida × 100` | derivado / `3.01` |

---

## 3. Por que esses indicadores estão fora do escopo

**Frequência incompatível**: demonstrações CVM são trimestrais/anuais; o preço da ação varia diariamente. Seria necessária uma estratégia de alinhamento temporal (ex: preço de fechamento da data de referência `DT_REFER`).


## 4. Problema do mapeamento `CD_CVM → ticker B3`

O identificador `CD_CVM` nos arquivos CVM (ex: `1023` para Banco do Brasil) **não tem relação direta** com o ticker negociado na B3 (ex: `BBAS3`). 

Foi implementado solução propria, num projeto a parte: [b3-tickers](https://github.com/dalmofelipe/b3-tickers)

Mais informações em [docs/b3_tickers.md](./b3_tickers.md).
