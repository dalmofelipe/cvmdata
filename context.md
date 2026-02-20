# cvmdata

### Objetivo

Processar dados abertos da CVM, para gerar calculos de indicadores financeiros de análise fundamentalista.

Mais informações sobre analise fundamentalista no documento [analise_fundamentalista.md](./docs/analise_fundamentalista.md)

Tecnicamente, vamos focar na engenharia de dados/backend para o processamento desses dados. No futuro o objetivo em desenvolver uma webapp dashboard de apresentação dos indicadores da analise fundamentalista. Tenha como referencia os sites:

- http://www.investido10.com.br
- https://statusinvest.com.br


### Fonte de Dados

- Documentos ITRs: https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr 
- Documentos DFR: https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp

O conjunto de dados disponibiliza as seguintes demonstrações financeiras entregues nos **últimos cinco anos**:

- **Balanço Patrimonial Ativo (BPA)**
- **Balanço Patrimonial Passivo (BPP)**
- **Demonstração de Fluxo de Caixa - Método Direto (DFC-MD)**
- **Demonstração de Fluxo de Caixa - Método Indireto (DFC-MI)**
- **Demonstração das Mutações do Patrimônio Líquido (DMPL)**
- **Demonstração de Resultado Abrangente (DRA)**
- **Demonstração de Resultado (DRE)**
- **Demonstração de Valor Adicionado (DVA)**

Esses são links para download de cara conjunto disponível ITRs.

- **Descrição das colunas e dados:** https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/META/meta_itr_cia_aberta_txt.zip
- Companhias Abertas - Formulário de Informações Trimestrais (ITR) (2021): https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2021.zip
- Companhias Abertas - Formulário de Informações Trimestrais (ITR) (2022): https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2022.zip
- Companhias Abertas - Formulário de Informações Trimestrais (ITR) (2023): https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2023.zip
- Companhias Abertas - Formulário de Informações Trimestrais (ITR) (2024): https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2024.zip
- Companhias Abertas - Formulário de Informações Trimestrais (ITR) (2025): https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2025.zip


### Informações Financeiras Trimestrais de 2024

Escolhi 2024 pois os documentos devem estar mais completos e sem divulgações de novas versões, logo mais estáveis para analise e processamento

```
dalmofelipe@ryzen:~/dev/ws/cvmdata/itr_cia_aberta_2024$ tree .
.
├── itr_cia_aberta_2024.csv
├── itr_cia_aberta_BPA_con_2024.csv
├── itr_cia_aberta_BPA_ind_2024.csv
├── itr_cia_aberta_BPP_con_2024.csv
├── itr_cia_aberta_BPP_ind_2024.csv
├── itr_cia_aberta_composicao_capital_2024.csv
├── itr_cia_aberta_DFC_MD_con_2024.csv
├── itr_cia_aberta_DFC_MD_ind_2024.csv
├── itr_cia_aberta_DFC_MI_con_2024.csv
├── itr_cia_aberta_DFC_MI_ind_2024.csv
├── itr_cia_aberta_DMPL_con_2024.csv
├── itr_cia_aberta_DMPL_ind_2024.csv
├── itr_cia_aberta_DRA_con_2024.csv
├── itr_cia_aberta_DRA_ind_2024.csv
├── itr_cia_aberta_DRE_con_2024.csv
├── itr_cia_aberta_DRE_ind_2024.csv
├── itr_cia_aberta_DVA_con_2024.csv
├── itr_cia_aberta_DVA_ind_2024.csv
└── itr_cia_aberta_parecer_2024.csv
1 directory, 19 files
```

### Descrição das colunas e dados

Encontrei nesse conjunto, informações de cada coluna de cada arquivo.

https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr/resource/062b8f02-ca6b-424a-bf65-180ff2b69af2

```
dalmofelipe@ryzen:~/dev/ws/cvmdata/meta_itr_cia_aberta_txt$ tree .
.
├── meta_itr_cia_aberta_BPA.txt
├── meta_itr_cia_aberta_BPP.txt
├── meta_itr_cia_aberta_composicao_capital.txt
├── meta_itr_cia_aberta_DFC_MD.txt
├── meta_itr_cia_aberta_DFC_MI.txt
├── meta_itr_cia_aberta_DMPL.txt
├── meta_itr_cia_aberta_DRA.txt
├── meta_itr_cia_aberta_DRE.txt
├── meta_itr_cia_aberta_DVA.txt
├── meta_itr_cia_aberta_parecer.txt
└── meta_itr_cia_aberta.txt
1 directory, 11 files
```

**meta_itr_cia_aberta_BPA.txt**

```
-----------------------
Campo: CD_CONTA
-----------------------
   Descrição : Código da conta
   Domínio   : Numérico
   Tipo Dados: varchar
   Tamanho   : 18

-----------------------
Campo: CD_CVM
-----------------------
   Descrição : Código CVM
   Domínio   : Numérico
   Tipo Dados: char
   Tamanho   : 6

-----------------------
Campo: CNPJ_CIA
-----------------------
   Descrição : CNPJ da companhia
   Domínio   : Alfanumérico
   Tipo Dados: varchar
   Tamanho   : 20

-----------------------
Campo: DENOM_CIA
-----------------------
   Descrição : Nome empresarial da companhia
   Domínio   : Alfanumérico
   Tipo Dados: varchar
   Tamanho   : 100

-----------------------
Campo: DS_CONTA
-----------------------
   Descrição : Descrição da conta
   Domínio   : Alfanumérico
   Tipo Dados: varchar
   Tamanho   : 100

-----------------------
Campo: DT_FIM_EXERC
-----------------------
   Descrição : Data fim do exercício social
   Domínio   : AAAA-MM-DD
   Tipo Dados: date
   Tamanho   : 10

-----------------------
Campo: DT_REFER
-----------------------
   Descrição : Data de referência do documento
   Domínio   : AAAA-MM-DD
   Tipo Dados: date
   Tamanho   : 10

-----------------------
Campo: ESCALA_MOEDA
-----------------------
   Descrição : Escala monetária
   Domínio   : Alfanumérico
   Tipo Dados: varchar
   Tamanho   : 100

-----------------------
Campo: GRUPO_DFP
-----------------------
   Descrição : Nome e nível de agregação da demonstração
   Domínio   : Alfanumérico
   Tipo Dados: varchar
   Tamanho   : 206

-----------------------
Campo: MOEDA
-----------------------
   Descrição : Moeda
   Domínio   : Alfanumérico
   Tipo Dados: varchar
   Tamanho   : 100

-----------------------
Campo: ORDEM_EXERC
-----------------------
   Descrição : Ordem do exercício social
   Domínio   : Alfanumérico
   Tipo Dados: varchar
   Tamanho   : 9

-----------------------
Campo: ST_CONTA_FIXA
-----------------------
   Descrição : Indica se é conta fixa ou não
   Domínio   : S/N
   Tipo Dados: varchar
   Tamanho   : 1

-----------------------
Campo: VERSAO
-----------------------
   Descrição : Versão do documento
   Domínio   : Numérico
   Tipo Dados: smallint
   Precisão  : 5
   Scale     : 0

-----------------------
Campo: VL_CONTA
-----------------------
   Descrição : Valor da conta
   Domínio   : Numérico
   Tipo Dados: decimal
   Precisão  : 29
   Scale     : 10
```

### Sample do arquivo Balanço Patrimonial Ativo (BPA)

Segue o sample [sample_itr_bpa_con_2024.csv](./docs/sample_itr_bpa_2024.csv) para ter o contexto do arquivo.

A versão completa tem mais de 60 mil linhas.



## Implementação e refinamento do PLANO DE IMPLEMENTAÇÃO

- Quero que faça um brainstorm de ideias para o processamento desses dados para atingir o objetivo da analise fundamentalista. 

- Vamos fazendo iterações e consolidando a arquitetura do projeto no arquivo [plan.md](./plan.md)
    - Esse plano será utilizado como prompt para IA auxiliar na construção.
    - Por isso, deve ser extremamente otimizado para implementação

- Temos que definir toda stack tecnologica para cumprir com objetivo

- Tenho pouca experiencia em desenvolvimento, porem tenho facilidade com divesas tecnologias, já fui estagiario fullstack por 9 meses, tenho experiencia java e react, além de conhecimento em python, linux, ruby, banco de dados, geralmente não tenho difilculdade em aprender ferramental. 

### FASE 1

Bom quero nessa primeira iteração, definir stack, ferramentas, o fluxo necessário para atingir o objetivo.

Principalmente, ter um plan para IA auxiliar na implementação.