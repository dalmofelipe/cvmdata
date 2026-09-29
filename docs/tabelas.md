# Nomenclatura das tabelas

Este documento registra a convenção de nomes das tabelas DuckDB do `cvmdata` e
o que fazer com bancos criados antes dela. A lista de nomes canônicos vive em
`src/cvmdata/ingestion/tables.py` — este doc explica o **porquê**; o código
importa as constantes de lá.


## Convenção

| Família | Padrão | Exemplo | Significado |
|---|---|---|---|
| Brutas | `raw_*` | `raw_bpa` | Dados como publicados pela CVM, sem nenhum tratamento. |
| Normalizadas | `*_clean` | `bpa_clean` | Resultado do `normalize`: deduplicado, tipado e convertido para Reais. |
| Cadastrais | — | `cad_cia_aberta_raw` | Cadastro CVM e sua curadoria. |
| Derivadas | — | `indicators` | Saídas calculadas e dados de apoio. |

O prefixo `raw_` é **reservado ao dado bruto**. Uma tabela normalizada que
carregasse esse prefixo seria autocontraditória — e era exatamente o caso: as
tabelas limpas chamavam-se `raw_bpa_clean`, `raw_bpp_clean` e `raw_dre_clean`.


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
| `company_classification` | Perfil resolvido por CNPJ. |
| `classification_curation_events` | Trilha de curadoria da classificação. |
| `setor_profile_map` | Setor → perfil. |

### Derivadas
| Tabela | Papel |
|---|---|
| `indicators` | Indicadores fundamentalistas calculados. |
| `b3_tickers` | Cache de tickers da B3. |
| `composicao_capital` | Composição acionária. |


## Bancos criados antes da padronização

Bancos com as tabelas antigas (`raw_bpa_clean`, `raw_bpp_clean`,
`raw_dre_clean`) **não** são migrados: não há aliases, nem views de
compatibilidade, nem versão de schema. O banco aqui é descartável — vive em
`data/db/cvmdata.duckdb`, está no `.gitignore` e é reconstruído integralmente a
cada execução do pipeline.

O passo é remover o arquivo antes da primeira execução após a mudança:

```bash
rm -p data/db/cvmdata.duckdb    # feche o DbGate antes
uv run cvmdata
```

Sem essa remoção as três tabelas legadas **não quebram nada** e ficam órfãs:
nenhum código as lê, e a descoberta de `normalize_all` as exclui
(`table_name LIKE 'raw_%' AND table_name NOT LIKE '%_clean'`). Elas só ocupam
disco e confundem quem abre o banco no DbGate.

Se você mantém consultas ad-hoc (scripts, notebooks, BI) apontando direto para
`raw_bpa_clean` e afins, atualize para `bpa_clean`, `bpp_clean` e `dre_clean`.
O único consumidor do banco fora do pipeline no repositório é
`scripts/indicators.py`, e ele lê apenas `indicators`, `company_classification` e
`b3_tickers` — nenhum nome afetado.


## Regras de aplicação

1. Tabela nova entra em `src/cvmdata/ingestion/tables.py` antes de aparecer em
   qualquer SQL.
2. SQL referencia a constante, não o literal — exceto nos testes que criam
   tabelas à mão, onde o literal é proposital: é o que faz o teste falhar se o
   código divergir.
3. `tests/unit/test_tables.py` barra a volta dos nomes antigos: ele varre
   `src/` e `tests/` e falha se encontrar o padrão `raw_*_clean`. Este arquivo é
   a única exceção permitida fora de `src/` e `tests/`.
