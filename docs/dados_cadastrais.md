# Dados Cadastrais CVM

## Objetivo
Este documento define como os dados cadastrais da CVM devem entrar no projeto para suportar classificacao de empresas, rastreabilidade historica e calculo de indicadores por perfil setorial.

## Fontes oficiais
- Meta (descricao das colunas): `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/META/meta_cad_cia_aberta.txt`
- CSV cadastral: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`

## Como o cadastro e usado hoje
O perfil **nao** vem do setor. A classificacao e estrutural: a assinatura de
layout e lida das tabelas `*_clean`, e o cadastro entra como Cadastro (descritores
e `setor_ativ`) e como override manual em `setor_profile_map`. Ver
[setor_profile.md](setor_profile.md).

O que o cadastro ainda garante:
- uma empresa ausente do cadastro e mesmo assim classificada, pela assinatura;
- uma empresa com `SIT = 'CANCELADA'` que ainda reporta demonstrativo continua
  classificada (o filtro `SIT` foi removido: e um estado regulatorio, nao um fato
  sobre quem reportou);
- `denom_social` como fallback de `denom_comerc`, que vem vazio para as
  estrangeiras (Nu, Inter & Co, XP, ...).

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
  - `rule_applied` (ex.: `structure:banking:bpa.1.01+bpp.2.01`)
  - `updated_at`

Nao ha `confidence`: o perfil e uma asercao estrutural, e `rule_applied` diz
qual regra decidiu.

### 3 - Tabela de regras
`setor_profile_map`
- Mapeamento direto de `SETOR_ATIV` para `profile_id`.
- Colunas recomendadas:
  - `setor_ativ`
  - `profile_id`
  - `active`

## Regras de elegibilidade temporal
Manter todas as linhas em `cad_cia_aberta_raw`, ativas e canceladas.

Para a classificacao (definir `profile_id` para calculo), **nao** ha filtro por
`SIT`: a elegibilidade vem da existencia de demonstrativo nas `*_clean`. Uma
empresa cancelada que ainda reporta continua classificada — o oposto do filtro
anterior, que descartava bancos que reportam.

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
- a classificacao nao filtra `SIT`: o que decide e o layout reportado nas `*_clean`.
- entre linhas duplicadas do mesmo CNPJ, vale a de `DT_INI_SIT` mais recente.

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
Para descrever setor por CNPJ:
1. Entre as linhas do CNPJ, usar a de `DT_INI_SIT` mais recente (descritor
   vigente).
2. O `SETOR_ATIV` resultante e um descritor e um override — nao a fonte da
   classificacao.

Observacao:
- CNPJs com multiplos `SETOR_ATIV` ativos existem (`90` no arquivo validado),
  porem a linha mais recente resolve o descritor vigente.

### 2 - Relevancia de `TP_MERC` e `CATEG_REG`
- `TP_MERC` nao sera usado para definir setor.
- `CATEG_REG` nao sera usado para definir setor.
- Ambos permanecem armazenados na camada bruta para auditoria e uso futuro.

### 3 - Governanca `SETOR_ATIV -> profile_id`
`setor_profile_map` e o ponto de override manual. A tabela **nasce vazia** — o
seed antigo (`Bancos`, `Arrendamento Mercantil`, `Intermediacao Financeira` ->
`banking`) foi removido porque mapeava por setor o que a estrutura resolve melhor.
O seed e legivel por hook `init_info_cad_schema`, que o apaga de bancos antigos.

### 4 - Politica para vazios e desconhecidos
Se `SETOR_ATIV` vier vazio, nao mapeado, ou a assinatura nao casar, o perfil e
`default` e `rule_applied` registra `default:setor_vazio` (ou o setor). Nao ha
fila de curadoria: a decisao e reproduzivel a partir do layout reportado.

## Uso no pipeline
Fluxo alvo (conceitual):
1. Download de ITR/DFP e cadastro.
2. Carga de demonstrativos e carga do cadastro.
3. Resolucao de perfil por empresa.
4. Calculo de indicadores respeitando profile.

## Criterios de aceite (implementados)
- Cadastro completo disponivel no DuckDB (universo sem filtro `SIT`).
- Consulta historica por CNPJ funcionando.
- Classificacao reproduzivel e auditavel (`rule_applied` por CNPJ).
- Sem regressao para empresas industriais (perfil `default` inalterado).
