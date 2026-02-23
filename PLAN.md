# PLAN — Correções e melhorias identificadas

> Registro das decisões técnicas e problemas analisados em 2026-02-21.
> Ordenado por prioridade de impacto na **corretude dos resultados**.

---

## P1 — [BUG CRÍTICO] Escopo consolidado ignorado + definição das fontes de dados

**Prioridade:** P1 — bloqueia corretude de todos os indicadores  
**Arquivos afetados:** `src/cvmdata/ingestion/db.py`, `src/cvmdata/transform/normalize.py`

### Sub-problema 1A — Escopo `ind` misturado com `con` na normalização

O SQL de normalização ([normalize.py](src/cvmdata/transform/normalize.py)) particiona por
`(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)` mas **não inclui a coluna `scope`**.
Isso significa que quando os arquivos `_con_` (consolidado) e `_ind_` (individual)
são carregados juntos, o `ROW_NUMBER() ORDER BY VERSAO DESC` elimina um deles de
forma arbitrária — podendo selecionar dados individuais no lugar dos consolidados.

A metodologia definida em `docs/analise_fundamentalista.md` é explícita:

> *"Todos dados financeiros são das demonstrações **consolidadas** e não individuais."*

### Sub-problema 1B — Quais fontes carregar: ITR e DFP

O código atual baixa e carrega **ITR e DFP juntos**. A questão é se isso é necessário.

**ITR (trimestral — Q1/Q2/Q3):**
- Cobre março (Q1), junho (Q2) e setembro (Q3)
- Não auditado
- Cada arquivo DRE contém 2 datas de referência por conta (ver P2)
- **Não inclui Q4** — dezembro nunca aparece no ITR

**DFP (anual):**
- Cobre o exercício completo (DT_FIM_EXERC = 31/dez)
- Auditado
- É a única fonte do valor acumulado do ano inteiro na DRE
- Necessário para derivar Q4 no cálculo TTM (ver P2)

**Conclusão: carregar AMBOS (ITR + DFP), mas somente `scope=con`.**

Razão: a metodologia TTM requer `YTD_atual + Q4_anterior`. O Q4 (outubro–dezembro)
só existe nos arquivos DFP. Usar apenas ITR impossibilita o TTM correto.

### Decisão de correção

- Remover `"fre"` de qualquer lista de fontes (não existe hoje, mas não adicionar)
- Alterar `SCOPES` de `["con", "ind"]` para `["con"]` — elimina ~50% do volume bruto
- Manter `sources = ["itr", "dfp"]` — ambos necessários para TTM
- A normalização passa a ter partição única por `scope` implicitamente (só `con` existe)

---

## P2 — [METODOLOGIA + BUG] DRE: estrutura real dos dados e TTM

**Prioridade:** P2 — explica divergência vs Status Invest / Investidor10, e contém bug oculto  
**Arquivos afetados:** `src/cvmdata/transform/normalize.py`, `src/cvmdata/transform/indicators.py`, `docs/analise_fundamentalista.md`

### Sub-problema 2A — Bug oculto: normalize escolhe arbitrariamente entre YTD e trimestral

Os arquivos DRE da CVM gravam **duas linhas para o mesmo `CD_CONTA` e `ORDEM_EXERC`**
a partir de Q2, diferenciadas pelo `DT_INI_EXERC`:

| DT_REFER | ORDEM_EXERC | DT_INI_EXERC | DT_FIM_EXERC | Tipo | VL_CONTA (Petrobras 3.01) |
|---|---|---|---|---|---|
| 2024-09-30 | ÚLTIMO | **2024-01-01** | 2024-09-30 | **Acumulado YTD (9m)** | 369.561M |
| 2024-09-30 | ÚLTIMO | **2024-07-01** | 2024-09-30 | **Trimestral (Q3 only)** | 129.582M |
| 2024-06-30 | ÚLTIMO | 2024-01-01 | 2024-06-30 | Acumulado YTD (6m) | 239.979M |
| 2024-06-30 | ÚLTIMO | 2024-04-01 | 2024-06-30 | Trimestral (Q2 only) | 122.258M |
| 2024-03-31 | ÚLTIMO | 2024-01-01 | 2024-03-31 | Q1 — único (acum = trim) | 117.721M |

O `_NORMALIZE_SQL` atual particiona por `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)` e
ordena por `VERSAO DESC`. Como as duas linhas têm a **mesma VERSAO**, o `ROW_NUMBER`
descarta uma delas de forma **não determinística** — pode estar usando o valor trimestral
onde o acumulado era esperado, ou vice-versa.

**Correção necessária:** adicionar `DT_INI_EXERC` como campo de seleção explícita no
normalize para DRE, ou filtrar por `MONTH(DT_INI_EXERC) = 1` para garantir que apenas
linhas acumuladas YTD sobrevivam (estratégia do TTM — ver 2B).

### Sub-problema 2B — Metodologia TTM requer DFP para Q4

O código atual extrai `VL_CONTA` da DRE filtrando por um único `DT_REFER`. Isso usa o
valor acumulado YTD do ITR (ex: 9 meses), não o ano completo. Sem anualização, as contas
de resultado (`3.xx`) ficam sub-representadas distorcendo:

- ROE, ROA, Margem Bruta, Margem Operacional, Margem Líquida, Giro do Ativo, Cobertura de Juros

**Fórmula TTM correta usando dados acumulados CVM:**

```
TTM = YTD_atual + (FY_ano_anterior - YTD_mesmo_periodo_ano_anterior)
```

**Exemplo com Petrobras, referência set/2024 (`3.01`):**
```
YTD_atual         = 369.561M  (ÚLTIMO, 2024-01-01 → 2024-09-30)
FY_2023           = ???M      (DFP 2023, ÚLTIMO, 2023-01-01 → 2023-12-31)   ← precisa DFP
YTD_2023_9m       = 377.736M  (PENÚLTIMO, 2023-01-01 → 2023-09-30)

TTM = 369.561 + (FY_2023 - 377.736)
```

> **Isso confirma que DFP é indispensável** (reforça decisão do P1B).

### Padrão de datas de referência CVM

> ⚠️ **Premissa anterior estava errada — revisada com base nos dados reais.**

A análise do arquivo `itr_cia_aberta_BPA_con_2025.csv` revelou os seguintes valores
únicos de `DT_REFER`: `2025-03-31`, `2025-05-31`, `2025-06-30`, `2025-08-31`,
`2025-09-30`, `2025-11-30`, `2025-12-31`.

**O `DT_REFER` do ITR NÃO é fixo em março/junho/setembro.** Ele reflete o fim do
trimestre relativo ao **ano fiscal de cada empresa**. Empresas brasileiras podem encerrar
o ano fiscal em qualquer mês. Exemplos:

| Encerramento do ano fiscal | Q1 (ITR) | Q2 (ITR) | Q3 (ITR) | Q4 (DFP apenas) |
|---|---|---|---|---|
| Dezembro (maioria) | 31/mar | 30/jun | 30/set | 31/dez |
| Março | 30/jun | 30/set | 31/dez | 31/mar |
| Junho | 30/set | 31/dez | 31/mar | 30/jun |
| Agosto | 30/nov | 28/fev | 31/mai | 31/ago |

A regra que se mantém válida: **Q4 (último trimestre do exercício) nunca aparece em
ITR** — é sempre o ano completo reportado no DFP. Mas o mês desse Q4 varia por empresa.

O `PENÚLTIMO` dentro do mesmo arquivo ITR ainda fornece o YTD do mesmo período do
ano anterior (ex: linha `PENÚLTIMO` do ITR set/2024 de uma empresa dez-fiscal tem
`DT_INI=2023-01-01, DT_FIM=2023-09-30`).

### Metodologia a formalizar

| Contas | Regra |
|---|---|
| **Balanço (1.xx, 2.xx)** | Snapshot do `DT_REFER` mais recente disponível (ITR ou DFP) |
| **Resultado (3.xx)** | TTM = `YTD_atual + (FY_anterior − YTD_anterior_mesmo_periodo)` |
| **Fallback (sem ITR recente)** | Usar DFP diretamente como proxy do ano |

### Decisão de correção

> ⚠️ **Correção proposta anteriormente (`MONTH(DT_INI_EXERC) = 1`) está errada.**
> Empresas com ano fiscal não-janeiro têm `DT_INI_EXERC` em meses diferentes (abril,
> julho, etc.). Filtrar pelo mês 1 descartaria silenciosamente todos os trimestres
> dessas empresas.

**Correção correta para o bug 2A:** na deduplicação da DRE, quando existem duas linhas
para o mesmo `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)`, manter a que tem o
**`DT_INI_EXERC` mais antigo** — que é sempre a linha acumulada YTD (período mais
longo), independentemente do mês do ano fiscal da empresa:

```sql
ROW_NUMBER() OVER (
    PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
    ORDER BY DT_INI_EXERC ASC, VERSAO DESC   -- ← YTD sempre tem DT_INI anterior
) AS rn
```

- Criar `extract_ttm_components(conn, cnpj)` que localiza o ITR mais recente,
  busca o DFP do ano anterior com base no encerramento do ano fiscal da empresa
  (não assume dezembro fixo — usa `MAX(DT_FIM_EXERC)` do DFP para aquela empresa),
  e aplica a fórmula TTM nas contas `3.xx`
- A tabela `indicators` não precisa mudar de schema
- Atualizar `docs/analise_fundamentalista.md` com a metodologia TTM formalizada

---

## P3 — [PERFORMANCE] Loop Python com N×3 queries no cálculo de indicadores

**Prioridade:** P3 — impacto operacional (lentidão)  
**Arquivos afetados:** `src/cvmdata/transform/indicators.py`

### Problema

`calculate_all` ([indicators.py](src/cvmdata/transform/indicators.py)) itera em loop
Python sobre cada par `(cnpj, dt_refer)` e, para cada um, dispara 3 queries SQL
separadas via UNION ALL (uma por tabela clean). Para uma base com 500 empresas × 20
períodos = **10.000 round-trips DuckDB→Python**.

DuckDB é um motor OLAP otimizado para scans completos — o padrão atual inverte o
ganho fazendo consultas pontuais repetidas.

### Decisão de correção

Reescrever `_extract_components` como **uma única query SQL em batch**:

```sql
-- Retorna todas as (empresa, período, conta, valor) de uma vez
SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA
FROM (
    SELECT ... FROM raw_bpa_clean
    UNION ALL
    SELECT ... FROM raw_bpp_clean
    UNION ALL
    SELECT ... FROM raw_dre_clean
)
WHERE CD_CONTA IN (<ACCOUNT_MAP keys>)
  [AND CNPJ_CIA = ? -- se filtro por empresa]
ORDER BY CNPJ_CIA, DT_REFER
```

O resultado é trazido de uma vez para Python, agrupado em memória via `itertools.groupby`
ou `dict`, e os indicadores calculados sem novo acesso ao banco. Ganho esperado: **100–1000×**.

---

## P4 — [OTIMIZAÇÃO] DB armazena contas irrelevantes para os indicadores

**Prioridade:** P4 — qualidade / manutenção  
**Arquivos afetados:** `src/cvmdata/ingestion/loader.py`, `src/cvmdata/transform/normalize.py`

### Problema

O loader persiste **todas as linhas** dos CSVs CVM no DuckDB. Uma empresa típica tem
~50–100 contas por período por demonstrativo. O `ACCOUNT_MAP` usa apenas **14 contas**.
Isso significa que ~70–85% das linhas armazenadas nas tabelas `raw_*` nunca são
consultadas para nenhum cálculo.

### Análise da proposta alternativa (blob CSV em TEXT)

Foi cogitada a abordagem de armazenar os dados de uma empresa/período como uma única
linha com conteúdo CSV em coluna TEXT, reduzindo o número de linhas físicas no banco.

**Conclusão: não recomendado para DuckDB.** Razões:

| Critério | Tabela colunar (atual) | Blob TEXT |
|---|---|---|
| Compressão | automática (RLE + dictionary encoding por coluna) | perde benefício colunar |
| Filtragem por CD_CONTA | `WHERE CD_CONTA = '3.11'` (microsegundos) | parse Python O(n) de cada blob |
| Manutenção | SQL padrão | deserialização manual frágil |
| Compatibilidade TTM (P2) | nativa | requer parse antes de qualquer cálculo |

### Decisão de correção

Filtrar apenas as contas do `ACCOUNT_MAP` **na etapa de normalização** (ou no load),
descartando o restante antes de gravar nas tabelas `*_clean`. As tabelas `raw_*` brutas
podem continuar completas (servem de auditoria) ou também ser filtradas se o espaço
for uma restrição.

---

## Resumo de dependências

```
P1  (scope=con, fontes=itr+dfp, sem fre)
 ├─ P2-2A  (normalize DRE: filtrar DT_INI_EXERC para YTD acumulado)  ← pode ser feito junto com P1
 │     └─ P2-2B  (TTM: YTD_atual + FY_anterior − YTD_anterior)       ← depende de P1 + P2-2A
 └─ P4  (filtrar somente ACCOUNT_MAP no normalize)                    ← independente, pode ser feito junto
       └─ P3  (batch query única no calculate_all)                    ← mais simples com raw_*_clean menor
```

**Ordem recomendada de implementação:**

1. **P1 + P2-2A + P4** juntos — todos são mudanças no ingestion/normalize, baixo risco, ganho imediato de corretude e volume
2. **P2-2B** (TTM) — lógica nova, requer P1 estável para não somar dados `ind` inadvertidamente
3. **P3** (batch query) — refatoração de performance, pode ser feita após os dados estarem corretos

P2-2A é o bug mais silencioso: não gera erro, mas pode estar usando valores trimestrais (ex: R$ 129B) onde se espera YTD acumulado (R$ 369B) — diferença de ~3x nos indicadores de resultado.
