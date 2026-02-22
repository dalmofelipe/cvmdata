# Indicadores de Valuation — Trabalho Futuro

> **Status**: fora do escopo do pipeline atual (`001-cvm-pipeline`).
> Os indicadores abaixo requerem dados de mercado (preço da ação, proventos distribuídos) que **não estão presentes nos arquivos CVM**. Este documento serve como referência de design para a iteração seguinte.

---

## 1. Indicadores e Fórmulas

Os três indicadores de valuation mais utilizados dependem do preço corrente (ou histórico) da ação na B3. Consulte também [`docs/analise_fundamentalista.md`](./analise_fundamentalista.md) — seção *"4. Indicadores fora do escopo atual"*.

| Indicador | Fórmula | Componentes CVM | Componente externo |
|---|---|---|---|
| **P/L** (Preço / Lucro) | `Preço / LPA` | `LPA = Lucro Líquido (3.11) / nº ações` | Preço da ação (B3) |
| **P/VPA** (Preço / Valor Patrimonial) | `Preço / VPA` | `VPA = PL (2.03) / nº ações` | Preço da ação (B3) |
| **Dividend Yield** | `(Dividendos por ação / Preço) × 100` | Dividendos pagos (não consta nas demonstrações CVM baixadas) | Preço + proventos (B3) |

> **Nota sobre nº de ações**: o arquivo `cad_cia_aberta.csv` da CVM contém `QT_AÇO_ORDI` e `QT_AÇO_PREF`, mas não é baixado neste pipeline. É um prerequisito adicional.

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

1. **Dados de mercado não disponíveis nos ZIPs CVM**: os arquivos `dfp_cia_aberta_*.csv` e `itr_cia_aberta_*.csv` contêm apenas demonstrações contábeis. Preço de ação, market cap e proventos são dados de bolsa (B3).
2. **Frequência incompatível**: demonstrações CVM são trimestrais/anuais; o preço da ação varia diariamente. Seria necessária uma estratégia de alinhamento temporal (ex: preço de fechamento da data de referência `DT_REFER`).
3. **Aumento de complexidade**: incorporar dados de mercado exige novo módulo de coleta, armazenamento de séries históricas de preços e reconciliação de datas.

---

## 4. Problema do mapeamento `CD_CVM → ticker B3`

O identificador `CD_CVM` nos arquivos CVM (ex: `1023` para Banco do Brasil) **não tem relação direta** com o ticker negociado na B3 (ex: `BBAS3`). É necessário um mapeamento manual ou enriquecimento via API.

### Exemplos de mapeamento

| CD_CVM | CNPJ_CIA | Razão Social | Ticker B3 |
|---|---|---|---|
| `1023` | `00.000.000/0001-91` | BCO BRASIL S.A. | `BBAS3` |
| `9512` | `33.000.167/0001-01` | PETROBRAS | `PETR3` / `PETR4` |
| `4170` | `33.592.510/0001-54` | VALE S.A. | `VALE3` |
| `19615` | `60.746.948/0001-12` | ITAÚ UNIBANCO | `ITUB3` / `ITUB4` |

> Empresas com ações ON e PN emitem dois tickers (ex: PETR3/PETR4). O pipeline precisaria decidir qual usar (convenção comum: PN para liquidez).

---

## 5. Abordagem Proposta

### 4.1 Arquivo `config/tickers.yaml`

Mapeamento estático mantido manualmente para as empresas mais relevantes:

```yaml
# config/tickers.yaml
# Formato: cd_cvm: ticker_b3
# Preferir ações PN (maior liquidez) quando disponível

"1023": "BBAS3"    # BCO BRASIL S.A.
"9512": "PETR4"    # PETROBRAS PN
"4170": "VALE3"    # VALE S.A.
"19615": "ITUB4"   # ITAÚ UNIBANCO PN
"14320": "BBDC4"   # BRADESCO PN
"906": "ABEV3"     # AMBEV
"22187": "WEGE3"   # WEG
```

Schema sugerido para a tabela DuckDB:

```sql
CREATE TABLE tickers (
    cd_cvm    INTEGER PRIMARY KEY,
    cnpj_cia  VARCHAR,
    razao_social VARCHAR,
    ticker    VARCHAR NOT NULL,
    fonte     VARCHAR DEFAULT 'manual'  -- 'manual' | 'brapi' | 'yfinance'
);
```

### 4.2 Fonte de preços: `yfinance`

Biblioteca Python para histórico OHLCV via Yahoo Finance. Ações B3 usam sufixo `.SA`:

```python
import yfinance as yf

ticker = yf.Ticker("BBAS3.SA")
hist = ticker.history(start="2024-01-01", end="2024-12-31")
# hist é um DataFrame com colunas: Open, High, Low, Close, Volume, Dividends, Stock Splits
price_at_date = hist.loc["2024-03-31", "Close"]  # preço de fechamento na DT_REFER
```

### 4.3 Fonte de preços e proventos: `brapi.dev`

API REST brasileira com endpoint para preços em tempo real e histórico de dividendos:

```bash
# Preço atual
GET https://brapi.dev/api/quote/BBAS3

# Histórico de dividendos
GET https://brapi.dev/api/quote/BBAS3?modules=dividendsData

# Histórico de preços (com autenticação via token gratuito)
GET https://brapi.dev/api/quote/BBAS3?range=1y&interval=1d
```

Vantagem sobre `yfinance`: dados de dividendos em BRL sem conversão cambial; suporte a proventos JCP (Juros sobre Capital Próprio), comuns no Brasil.

### 4.4 Novo comando CLI proposto

```bash
cvmdata enrich-tickers        # carrega config/tickers.yaml → tabela tickers
cvmdata fetch-prices --year 2024  # baixa preços históricos B3 via brapi.dev/yfinance
cvmdata valuation --cnpj "00.000.000/0001-91"  # calcula P/L, P/VPA, DY
```

---

## 6. Estimativa de Esforço

| Tarefa | Estimativa | Prerequisitos |
|---|---|---|
| `config/tickers.yaml` com top-50 empresas | 1–2h | — |
| Módulo `ingestion/prices.py` (fetch + armazenamento) | 4–8h | `brapi.dev` token ou `yfinance` instalado |
| Schema DuckDB para preços históricos (`prices` table) | 1h | — |
| Calcular LPA e VPA (requer `cad_cia_aberta.csv` para nº ações) | 4–6h | Download adicional do cadastro CVM |
| Funções puras `pl()`, `pvpa()`, `dividend_yield()` | 2h | LPA, VPA, preço |
| Orquestrador e CLI `cvmdata valuation` | 3–4h | Todos acima |
| Testes unitários e integração | 4–6h | Fixtures de preços mockados |
| **Total estimado** | **19–29h** | — |

### Prerequisitos técnicos

1. **Número de ações emitidas**: baixar `cad_cia_aberta.csv` da CVM (URL: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`) e persistir colunas `CD_CVM`, `QT_AÇO_ORDI`, `QT_AÇO_PREF`.
2. **Mapeamento CD_CVM → ticker**: popular `config/tickers.yaml` para as empresas de interesse.
3. **Dependências adicionais**: adicionar `yfinance` e/ou `httpx` (já presente) + `pyyaml` ao `pyproject.toml`.
4. **Decisão de design**: usar preço de fechamento na `DT_REFER` ou preço médio do trimestre.

---

## 7. Referências

- [analise_fundamentalista.md](./analise_fundamentalista.md) — fórmulas completas e mapeamento de contas CVM
- [CVM — Cadastro de Companhias Abertas](https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/) — fonte de nº de ações
- [brapi.dev](https://brapi.dev) — API REST para cotações e dividendos B3
- [yfinance](https://github.com/ranaroussi/yfinance) — histórico OHLCV via Yahoo Finance (sufixo `.SA` para B3)
- [B3 — Listagem de Empresas](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/empresas-listadas.htm) — referência para mapeamento CD_CVM → ticker
