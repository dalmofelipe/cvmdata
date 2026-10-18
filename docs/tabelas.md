# Nomenclatura das tabelas

Este documento registra a convenção de nomes das tabelas DuckDB do `cvmdata` e o que fazer com bancos criados antes dela. Os nomes canônicos vivem em `src/cvmdata/ingestion/tables.py` — este doc explica o **porquê**; o código importa as constantes de lá.


## Convenção

| Família | Padrão | Exemplo | Significado |
|---|---|---|---|
| Brutas | `raw_*` | `raw_bpa` | Dados como publicados pela CVM, sem nenhum tratamento. |
| Normalizadas | `*_clean` | `bpa_clean` | Resultado do `normalize`: deduplicado, tipado e convertido para Reais. |
| Cadastrais | — | `cad_cia_aberta_raw` | Cadastro CVM e o perfil resolvido por empresa. |
| Derivadas | — | `indicators` | Saídas calculadas e dados de apoio. |

O prefixo `raw_` é **reservado ao dado bruto**. Uma tabela normalizada que carregasse esse prefixo seria autocontraditória — e era exatamente o caso: as tabelas limpas chamavam-se `raw_bpa_clean`, `raw_bpp_clean` e `raw_dre_clean`.


## Inventário

### Brutas (`raw_*`)
| Tabela | Origem |
|---|---|
| `raw_bpa` | Balanço Patrimonial Ativo (ITR/DFP) |
| `raw_bpp` | Balanço Patrimonial Passivo (ITR/DFP) |
| `raw_dre` | Demonstração do Resultado do Exercício (ITR/DFP) |

### Normalizadas (`*_clean`)
| Tabela | Derivada de |
|---|---|
| `bpa_clean` | `raw_bpa` |
| `bpp_clean` | `raw_bpp` |
| `dre_clean` | `raw_dre` |

### Cadastrais
| Tabela | Papel |
|---|---|
| `cad_cia_aberta_raw` | Cadastro bruto da CVM — único `raw_` que não é demonstrativo. |
| `company_classification` | Perfil resolvido por CNPJ, com `rule_applied` explicando a decisão. |

A classificação é estrutural (assinatura de layout nas tabelas `*_clean`), não setorial. Não há tabela de override por setor: corrigir uma classificação é editar `SIGNATURE_RULES` e reexecutar. Ver [classificacao.md](classificacao.md) para o percurso completo e [setor_profile.md](setor_profile.md) para a precedência.

### Derivadas

| Tabela | Papel |
|---|---|
| `indicators` | Indicadores fundamentalistas calculados. |
| `b3_tickers` | Cache de tickers da B3. |
| `composicao_capital` | Composição acionária. |


## Bancos criados antes da padronização

Bancos com as tabelas antigas (`raw_bpa_clean`, `raw_bpp_clean`, `raw_dre_clean`) **não** são migrados: não há aliases, nem views de compatibilidade, nem versão de schema. O banco aqui é descartável — vive em `data/db/cvmdata.duckdb`, está no `.gitignore` e é reconstruído integralmente a cada execução do pipeline.

O passo é remover o arquivo antes da primeira execução após a mudança:

```bash
rm -p data/db/cvmdata.duckdb    # feche o DbGate antes
uv run cvmdata
```

Sem essa remoção as três tabelas legadas **não quebram nada** e ficam órfãs: nenhum código as lê, e a descoberta de `normalize_all` as exclui (`table_name LIKE 'raw_%' AND table_name NOT LIKE '%_clean'`). Elas só ocupam espaço e confundem quem abre o banco no DbGate.

Se você mantém consultas ad-hoc (scripts, notebooks, BI) apontando direto para `raw_bpa_clean` e afins, atualize para `bpa_clean`, `bpp_clean` e `dre_clean`. O único consumidor do banco fora do pipeline no repositório é `scripts/indicators.py`, e ele lê apenas `indicators`, `company_classification` e `b3_tickers` — nenhum nome afetado.

## Bancos com classificação anterior

Não há migração. O pipeline cria o `cvmdata.duckdb` do zero a cada execução (pipeline semanal em CI, banco descartado depois do export), então um schema antigo não se encontra em produção.

`init_info_cad_schema` faz só `CREATE TABLE IF NOT EXISTS` — e isso não altera tabela que já existe. Se um arquivo de execução anterior for reaproveitado, `classify_info_cad` recusa com um erro de binder do DuckDB, porque a tabela antiga tem colunas que a versão atual não preenche. Apagar o arquivo resolve. Não há `ALTER TABLE` silencioso nem `DROP` das `*_clean`.


## Onde cada nome é declarado

| Família | Declaração | Constantes |
|---|---|---|
| `raw_*` | `ingestion/catalog.py` — `CvmDataset.table` | — |
| `*_clean` | derivado em runtime, por `clean_table_name()` | `BPA_CLEAN`, `BPP_CLEAN`, `DRE_CLEAN` |
| cadastrais e derivadas | `CREATE TABLE` em `ingestion/schema.py` | `TB_CAD_CIA_ABERTA_RAW`, `TB_COMPANY_CLASSIFICATION`, `TB_INDICATORS`, `TB_B3_TICKERS`, `TB_COMPOSICAO_CAPITAL` |

O campo `CvmDataset.table` do catálogo é a fonte da verdade do nome da tabela bruta: `init_schema` e o loader leem dele. Antes ele era declarado e nunca lido — o nome real vinha de `f"raw_{demo.lower()}"` em dois módulos, o que divergiria do catálogo em silêncio.

## Regras de aplicação

1. SQL e dados estruturados referenciam a constante, nunca o literal.
2. O literal permanece no **sítio de declaração**: o `CREATE TABLE` em `schema.py` e o `CvmDataset.table` do catálogo.
3. Docstrings e mensagens de log mantêm o nome por extenso — são prosa, não referência.
4. Em `tests/`, o literal é proposital: um fixture que declara `CREATE TABLE bpa_clean` com a constante passaria mesmo se o código de produção usasse outro nome. O literal **é** a asserção.
5. `tests/unit/test_tables.py` guarda as três regras acima: barra a volta dos nomes antigos, barra literal em SQL de produção e confere que toda constante tem onde ser declarada. Este arquivo é a única exceção a `src/` e `tests/`.
