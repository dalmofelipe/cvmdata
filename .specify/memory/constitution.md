# cvmdata Constitution

## Core Principles

### I. Simplicidade Antes de Abstração (NON-NEGOTIABLE)
Implementar a solução mais simples que funcione; abstrações só são introduzidas quando há necessidade real e demonstrada — não antecipada; YAGNI (You Aren't Gonna Need It) como regra padrão; toda complexidade adicionada deve ser justificada por um requisito concreto.

### II. Pipeline por Etapas Isoladas
Cada etapa do pipeline (`download → load → normalize → indicators`) é um módulo independente com entrada/saída bem definida; etapas não chamam umas às outras diretamente — comunicam via DuckDB; cada etapa deve ser reexecutável (idempotente) sem efeitos colaterais.

### III. Dados como Fonte da Verdade
Os CSVs da CVM são a fonte primária e autoritativa; nenhum valor de indicador é calculado sem rastreabilidade ao `CNPJ_CIA + DT_REFER + CD_CONTA + VERSAO` de origem; deduplicação sempre mantém a versão mais recente (`ORDER BY VERSAO DESC`); nunca modificar os arquivos `data/raw/` após extração.

**Exceção DRE (ratificada 2026-02-22 — branch 002-p1-refactor-scope-con)**: A tabela `raw_dre` publica dois registros por `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)` a partir do Q2 — valor YTD e valor trimestral isolado — ambos com o **mesmo** `VERSAO`. O critério `ORDER BY VERSAO DESC` é portanto não-determinístico para DRE nesses casos. A deduplicação de `raw_dre` usa `ORDER BY DT_INI_EXERC ASC, VERSAO DESC`, selecionando sempre o acumulado YTD (início do exercício = `DT_INI_EXERC` mais antiga). Esta regra é determinística, rastreável ao dado CVM e mais fiel ao significado econômico do período. O princípio `ORDER BY VERSAO DESC` permanece inalterado para BPA e BPP.

### IV. Tolerância a Falhas e Dados Incompletos
Indicadores retornam `None` quando qualquer componente estiver ausente — nunca lançar exceção por conta ausente; logar contas não mapeadas em `account_map.py` com nível `WARNING` para descoberta incremental; o pipeline deve processar ~600 empresas sem parar em um erro isolado.

### V. Código Pythônico e Testável
Funções de cálculo são puras (sem side effects, sem I/O); tipos anotados em toda função pública; módulos importáveis sem executar I/O no nível de módulo; cobertura mínima de 80% para funções em `transform/`; linter `ruff` sem warnings antes de qualquer commit.

### VI. Evolução Incremental de Mapeamentos
`account_map.py` começa com um perfil único; diferenças de setor (bancos vs industriais) são descobertas empiricamente via testes com fixtures reais e marcadas com `# TODO: sector_profile`; nunca adicionar perfis de setor sem evidência em dados reais; a constituição é atualizada a cada perfil confirmado.

### VII. Schemas Heterogêneos entre Tipos de Demonstrativo (NON-NEGOTIABLE)
Cada tipo de demonstrativo tem seu próprio conjunto de colunas — **nunca assumir schema uniforme entre tipos**. O loader deve criar uma tabela separada por tipo (`itr_bpa_con`, `itr_dre_con`, `itr_dmpl_con`, etc.) e deixar o DuckDB inferir o schema via `auto_detect=true` por arquivo. A referência autoritativa de colunas por tipo está em `meta_itr_cia_aberta_*.txt` (disponível em `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/META/meta_itr_cia_aberta_txt.zip`). Diferenças conhecidas: DMPL possui colunas adicionais para cada componente do patrimônio líquido; DFC_MD e DFC_MI têm estruturas distintas entre si; as 14 colunas padrão (`CNPJ_CIA`, `DT_REFER`, `VERSAO`, `DENOM_CIA`, `CD_CVM`, `GRUPO_DFP`, `MOEDA`, `ESCALA_MOEDA`, `ORDEM_EXERC`, `DT_FIM_EXERC`, `CD_CONTA`, `DS_CONTA`, `VL_CONTA`, `ST_CONTA_FIXA`) são comuns a BPA, BPP, DRE, DRA, DVA — mas não garantidas para DMPL, DFC_MD e DFC_MI.

## Stack Tecnológica (NON-NEGOTIABLE)

- **Runtime**: Python 3.12+, gerenciado por `uv`
- **Banco de dados (Fase 1)**: DuckDB — arquivo único `data/db/cvmdata.duckdb`; migração futura via extensão `postgres` nativa
- **Leitura CSV**: DuckDB nativo `read_csv(delim=';', encoding='latin1')` — Pandas proibido na ingestão
- **CLI**: Typer com flags `--year` (padrão: todos os anos disponíveis), `--cnpj` (opcional para filtro)
- **HTTP**: httpx para download dos ZIPs da CVM
- **Config**: pydantic-settings lendo `.env`; nunca hardcodar paths ou URLs
- **Qualidade**: ruff (linter + formatter), pytest (testes)
- **API futura**: FastAPI + uvicorn (Fase 2 — fora do escopo atual)

## Padrões de Desenvolvimento

- **Estrutura de pastas**: `src/cvmdata/{ingestion/, transform/, api/}`, `data/{raw/, db/}`, `tests/fixtures/`
- **Nomenclatura**: snake_case para arquivos e funções; nomes descritivos em português para variáveis de domínio (`cnpj_cia`, `dt_refer`, `vl_conta`)
- **Erros**: usar exceções específicas (`ValueError`, `FileNotFoundError`); nunca `except Exception` sem re-raise ou log
- **Logging**: usar `logging` padrão do Python; nível `INFO` para progresso, `WARNING` para dados inesperados, `ERROR` para falhas recuperáveis
- **Testes**: DuckDB in-memory nas fixtures (`duckdb.connect(':memory:')`); fixtures de CSV em `tests/fixtures/` com samples reais de bancos e industriais
- **Git**: commits atômicos por etapa do pipeline; nunca commitar `data/`, `*.duckdb`, `.env`

## Governance

Esta constituição é o documento de maior autoridade no projeto — supera preferências pessoais, convenções genéricas e sugestões de ferramentas externas. Toda decisão técnica que conflitar com estes princípios requer atualização explícita da constituição com justificativa documentada. A complexidade deve sempre ser justificada; em caso de dúvida, escolher a opção mais simples.

**Version**: 1.1.0 | **Ratified**: 2026-02-20 | **Last Amended**: 2026-02-20
