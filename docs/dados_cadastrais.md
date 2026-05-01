# Dados Cadastrais CVM

## Objetivo
Este documento define como os dados cadastrais da CVM devem entrar no projeto para suportar classificacao de empresas, rastreabilidade historica e calculo de indicadores por perfil setorial.

## Fontes oficiais
- Meta (descricao das colunas): `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/META/meta_cad_cia_aberta.txt`
- CSV cadastral: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`

## Por que isso e necessario
- O projeto hoje calcula indicadores com um mapa de contas unico, adequado para empresas industriais.
- Instituicoes financeiras (ex.: bancos) usam estrutura contabil diferente.
- Sem cadastro, a classificacao setorial fica fragil e dificulta evolucao para novos perfis.
- Com cadastro historico no DuckDB, a decisao de perfil fica auditavel e reprodutivel.

## Escopo de armazenamento
Armazenar o arquivo completo no DuckDB, sem filtrar apenas empresas ativas.

Motivo:
- Empresas hoje canceladas podem ter divulgacoes validas em anos anteriores.
- A analise historica (2021-2025 e futuros anos) precisa preservar contexto regulatorio do periodo.

## Modelo de dados proposto
### 1 - Tabela bruta
`cad_cia_aberta_raw`
- Espelho do CSV oficial (sem perda de colunas).
- Carregamento por recarga total (drop/truncate + insert do zero em cada execucao completa do pipeline).
- Sem merge incremental nesta fase, para evitar comportamento fora do dominio conhecido.

### 2 - Tabela de classificacao
`company_classification`
- Uma linha por empresa (CNPJ) com classificacao efetiva para uso no calculo.
- Colunas recomendadas:
  - `cnpj_cia`
  - `cd_cvm`
  - `denom_social`
  - `denom_comerc`
  - `setor_ativ`
  - `profile_id`
  - `confidence` (opcional; usar quando houver ambiguidade)
  - `updated_at`

### 3 - Tabela de regras
`setor_profile_map`
- Mapeamento direto de `SETOR_ATIV` para `profile_id`.
- Colunas recomendadas:
  - `setor_ativ`
  - `profile_id`
  - `active`

## Regras de elegibilidade temporal
Para armazenamento historico em `cad_cia_aberta_raw`, manter todas as linhas (ativas e canceladas).

Para classificacao setorial operacional (definir `profile_id` para calculo), usar somente linhas com:
- `SIT = 'ATIVO'`

Observacao:
- O historico continua preservado na camada bruta.
- A camada de classificacao de setor foca no estado atual ativo da empresa.

## Consideracoes de ingestao
- Encoding esperado: `latin-1`.
- O CSV pode ter duplicidade por CNPJ.
- Para determinacao de setor, usar somente `SETOR_ATIV` em linhas ativas.
- `TP_MERC` e `CATEG_REG` nao entram na regra de setor nesta fase.
- Validar campos-chave: CNPJ, CD_CVM, datas e status.

## Duplicidade por CNPJ
Na pratica, ha CNPJs com mais de uma linha no cadastro.

Validacao no `data/cad_cia_aberta.csv` (linhas ativas):
- `cnpjs_ativos_com_multiplos_setores = 0`
- `ativos_setor_vazio = 0` (em `772` linhas ativas)
- `cnpjs_ativos_duplicados_mesmo_setor_por_tpmerc_cat = 90`

Diretriz adotada para setor:
- manter 100% das linhas na camada bruta.
- para classificacao setorial, filtrar `SIT = 'ATIVO'`.
- entre linhas ativas duplicadas do mesmo CNPJ, considerar apenas `SETOR_ATIV`.

Racional:
- `TP_MERC` varia para empresa ativa (ex.: `BOLSA` e `BALCAO ORGANIZADO`) e nao muda o setor economico.
- `CATEG_REG` (A/B/vazio) representa categoria regulatoria, nao setor.

## Valores possiveis de `SETOR_ATIV`
Levantamento completo no arquivo atual `data/cad_cia_aberta.csv` (inclui vazio).
Total identificado: `71` valores distintos.

| SETOR_ATIV | Ocorrencias |
| --- | ---: |
| (vazio) | 6 |
| Agricultura (Acucar, Alcool e Cana) | 50 |
| Alimentos | 111 |
| Arrendamento Mercantil | 73 |
| Bancos | 115 |
| Bebidas e Fumo | 25 |
| Bolsas de Valores/Mercadorias e Futuros | 4 |
| Brinquedos e Lazer | 11 |
| Comercio (Atacado e Varejo) | 113 |
| Comercio Exterior | 4 |
| Comunicacao e Informatica | 40 |
| Construcao Civil, Mat. Constr. e Decoracao | 171 |
| Credito Imobiliario | 6 |
| Educacao | 10 |
| Embalagens | 8 |
| Emp. Adm. Part. - Agricultura (Acucar, Alcool e Cana) | 3 |
| Emp. Adm. Part. - Alimentos | 6 |
| Emp. Adm. Part. - Arrendamento Mercantil | 2 |
| Emp. Adm. Part. - Bancos | 1 |
| Emp. Adm. Part. - Brinquedos e Lazer | 4 |
| Emp. Adm. Part. - Comercio (Atacado e Varejo) | 22 |
| Emp. Adm. Part. - Comunicacao e Informatica | 6 |
| Emp. Adm. Part. - Const. Civil, Mat. Const. e Decoracao | 26 |
| Emp. Adm. Part. - Credito Imobiliario | 5 |
| Emp. Adm. Part. - Educacao | 9 |
| Emp. Adm. Part. - Embalagens | 2 |
| Emp. Adm. Part. - Energia Eletrica | 53 |
| Emp. Adm. Part. - Extracao Mineral | 11 |
| Emp. Adm. Part. - Farmaceutico e Higiene | 2 |
| Emp. Adm. Part. - Graficas e Editoras | 1 |
| Emp. Adm. Part. - Hospedagem e Turismo | 5 |
| Emp. Adm. Part. - Intermediacao Financeira | 16 |
| Emp. Adm. Part. - Maqs., Equip., Veic. e Pecas | 8 |
| Emp. Adm. Part. - Metalurgia e Siderurgia | 8 |
| Emp. Adm. Part. - Papel e Celulose | 1 |
| Emp. Adm. Part. - Petroleo e Gas | 12 |
| Emp. Adm. Part. - Petroquimicos e Borracha | 4 |
| Emp. Adm. Part. - Saneamento, Serv. Agua e Gas | 9 |
| Emp. Adm. Part. - Securitizacao de Recebiveis | 4 |
| Emp. Adm. Part. - Seguradoras e Corretoras | 6 |
| Emp. Adm. Part. - Sem Setor Principal | 109 |
| Emp. Adm. Part. - Servicos medicos | 7 |
| Emp. Adm. Part. - Servicos Transporte e Logistica | 38 |
| Emp. Adm. Part. - Telecomunicacoes | 38 |
| Emp. Adm. Part. - Textil e Vestuario | 5 |
| Emp. Adm. Part.-Bolsas de Valores/Mercadorias e Futuros | 1 |
| Emp. Adm. Participacoes | 156 |
| Energia Eletrica | 116 |
| Extracao Mineral | 53 |
| Factoring | 1 |
| Farmaceutico e Higiene | 25 |
| Graficas e Editoras | 12 |
| Hospedagem e Turismo | 29 |
| Intermediacao Financeira | 10 |
| Maquinas, Equipamentos, Veiculos e Pecas | 181 |
| Metalurgia e Siderurgia | 139 |
| Outras Atividades Industriais | 18 |
| Papel e Celulose | 21 |
| Pesca | 4 |
| Petroleo e Gas | 26 |
| Petroquimicos e Borracha | 99 |
| Reflorestamento | 6 |
| Saneamento, Serv. Agua e Gas | 41 |
| Securitizacao de Recebiveis | 141 |
| Seguradoras e Corretoras | 24 |
| Servicos Diversos | 18 |
| Servicos em Geral | 1 |
| Servicos Medicos | 25 |
| Servicos Transporte e Logistica | 151 |
| Telecomunicacoes | 80 |
| Textil e Vestuario | 122 |

## Regras operacionais recomendadas

### 1 - Regra de selecao por CNPJ
Para classificar setor por CNPJ:
1. Filtrar apenas `SIT = 'ATIVO'`.
2. Se existir um unico `SETOR_ATIV` entre as linhas ativas, usar esse valor.
3. Se existirem multiplos `SETOR_ATIV` ativos para o mesmo CNPJ, marcar `confidence = low` e enviar para curadoria.

Observacao:
- Na validacao atual, esse caso nao ocorreu (`0` CNPJs).

### 2 - Relevancia de `TP_MERC` e `CATEG_REG`
- `TP_MERC` nao sera usado para definir setor.
- `CATEG_REG` nao sera usado para definir setor.
- Ambos permanecem armazenados na camada bruta para auditoria e uso futuro.

### 3 - Matriz inicial `SETOR_ATIV -> profile_id`
Criar uma tabela de governanca (`setor_profile_map`) com mapeamento explicito.

Sugestao inicial de profiles:
- `Bancos`, `Arrendamento Mercantil`, `Intermediacao Financeira` -> `banking` (prioridade)
- `Seguradoras e Corretoras` -> `insurance` (futuro)
- `Securitizacao de Recebiveis` -> `securitization` (futuro)
- Demais setores -> `industrial_default` (default)

### 4 - Politica para vazios e desconhecidos
Se `SETOR_ATIV` vier vazio ou nao mapeado:
- aplicar `profile_id = industrial_default`
- gravar `confidence = low`
- registrar evento para revisao manual (fila de curadoria)

## Uso no pipeline
Fluxo alvo (conceitual):
1. Download de ITR/DFP e cadastro.
2. Carga de demonstrativos e carga do cadastro.
3. Resolucao de perfil por empresa.
4. Calculo de indicadores respeitando profile.

## Comandos CLI implementados

> Nota (atualização): os comandos antigos `download-cad`, `load-cad` e `classify-cad` foram removidos.
> Para preparar os dados, use `cvmdata pipeline run`. Para consultar o cadastro/classificação, use `cvmdata info-cad`.

### Download
```sh
uv run cvmdata download-cad [--force]
```
Baixa `meta_cad_cia_aberta.txt` e `cad_cia_aberta.csv` para `data/raw/cad/`.
Ignora se ja existir (use `--force` para forcar re-download).

### Carga
```sh
uv run cvmdata load-cad
```
Faz recarga total de `cad_cia_aberta.csv` na tabela `cad_cia_aberta_raw` do DuckDB.
Usa `auto_detect=true` para preservar todas as colunas (FR-014).
Valida paridade de linhas CSV vs tabela (SC-001).

### Classificacao
```sh
uv run cvmdata classify-cad
```
Classifica todos os CNPJs com `SIT='ATIVO'` por `SETOR_ATIV`.
Persiste resultado em `company_classification`.
Registra baixa confianca em `classification_curation_events`.

### Consulta
```sh
# Resumo das 20 classificacoes mais recentes
uv run cvmdata info-cad

# Detalhe de uma empresa
uv run cvmdata info-cad --cnpj 00.000.000/0001-91
```

## Validacao manual (SQL DuckDB)
```sql
-- SC-001: Comparar linhas CSV vs raw (via Python print de inserted/csv_count)
SELECT COUNT(*) FROM cad_cia_aberta_raw;

-- Distribuicao de confidence
SELECT confidence, COUNT(*) AS n
FROM company_classification
GROUP BY confidence;

-- Setores sem mapeamento (candidates para setor_profile_map)
SELECT DISTINCT setor_ativ, COUNT(*) AS n
FROM company_classification
WHERE confidence = 'low'
  AND rule_applied LIKE 'unmapped_setor%'
GROUP BY setor_ativ
ORDER BY n DESC;

-- Exemplos banking
SELECT cnpj_cia, denom_social, setor_ativ, profile_id, confidence
FROM company_classification
WHERE profile_id = 'banking'
LIMIT 10;
```

## Criterios de aceite (planejamento)
- Cadastro completo disponivel no DuckDB.
- Consulta historica por CNPJ funcionando.
- Classificacao de empresa reprodutivel (`rule_version`) e auditavel (`confidence`).
- Sem regressao para empresas industriais.
