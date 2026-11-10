# Dados Cadastrais CVM

## Objetivo

Documentar observações feitas no arquivo `cad_cia_aberta.csv`, além decisões sobre as tabelas `cia_cad_aberta_raw` e `company_classification`.

## Fontes oficiais

- Meta (descricao das colunas): `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/META/meta_cad_cia_aberta.txt`
- CSV cadastral: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`

## Escopo de armazenamento

O arquivo `cad_cia_aberta.csv` é completamente carregada se transoformando na tabela `cia_cad_aberta_raw`. Qualquer reprocessamento, pode ser utilizada de imediato, sem novo loader. Custo de carga baixissimo para duckdb, possui menos de 3000 linhas.

Tanto `cia_cad_aberta_raw` quanto o **universo de empresas** detectado pela classificação (tabelas *_clean), formam a tabela `company_classification`

Assim que classificado, `company_classification` representa o universo de empresa/cnpj que terão indicadores calculados, além de armazenar associação de um CNPJ a um `profile` de contas.

## Observações

- Empresas hoje canceladas podem ter divulgacoes validas em anos anteriores. Esta diretamente relacionado a configuração do período executado pelo pipeline, ex: desde 2011.
- `company_classification` é um espelho do universo detectado das tabelas *_clean, é obrigatória apenas para complementar dados que faltam entre os arquivos reportados a CVM (BPA, BPP e DRE) e `cad_cia_aberta.csv`. Ela não tem influência sob qual empresa terá indicadores calculados, quem decide isso é a classificação do universo.
- **IMPORTANTE**: podem existir empresas nos resultados da CVM que não aparecem em dados cadastrais `cad_cia_aberta.csv`.
- `cad_cia_aberta.csv` uma empresa pode ter multiplos registros variando `TP_MERC`. Atualmente, a regra de seleção é pegar a linha mais recente de `DT_INI_SIT` para cada CNPJ durante a classificação.


## Colunas

Descrição e tipagem completa é formalizada em `meta_cad_cia_aberta.txt`


### Coluna `DT_INI_SIT`

Data de início da situação da empresa. Representa a data em que a empresa entrou em uma determinada situação (ex: ATIVO, CANCELADO, etc.). Não possui valor nulo.

Atualmente é a unica coluna usada para determinar a o registro mais recente de cada empresa/CNPJ, quando existem múltiplos registros para o mesmo CNPJ.


### Coluna `SIT`

Situação cadastral da empresa. Possíveis valores: `ATIVO`, `CANCELADO` e `SUSPENSO(A) - DECISÃO ADM`. Não possui valor nulo.

Não tem influência sobre a classificação de setor ou calculos de indicadores. Todas empresas registradas nas tabelas *_clean são elegíveis para calculos, em qualquer situação.


### Coluna `TP_MERC`

Tipo de mercado da empresa. Possíveis valores: `BOLSA`, `BALCAO ORGANIZADO`, `BALCAO NÃO ORGANIZADO` e `NULL`.

- `BOLSA (Bolsa de Valores)`: Sistema centralizado e multilateral de negociação operado por uma entidade administradora autorizada (no Brasil, a B3).

Exige regras rígidas de governança e transparência, livro de ofertas público e aberto em tempo real (Home Broker), formação de preços por leilão/ofertas e atuação obrigatória de uma contraparte central (clearing house) que garante a liquidação das operações.

***Exemplo***: Ações de grandes empresas como Vale (VALE3), Petrobras (PETR4) e Itaú (ITUB4).

- `BALCÃO ORGANIZADO (Over-The-Counter Organizado - OTC)`: Sistema eletrônico de negociação ou registro mantido por uma entidade administradora autorizada pela CVM (como o segmento de Balcão Organizado da B3, o antigo SOMA FIX ou a BEE4).

Regras de admissão e governança mais flexíveis e menos burocráticas do que a bolsa tradicional. Ideal para negociação de títulos de dívida corporativa (como debêntures e notas comerciais) e ações de pequenas e médias empresas (PMEs). As negociações podem ocorrer de forma bilateral entre instituições financeiras credenciadas ou por leilões específicos, sem a necessidade de exibição pública contínua de livros de ofertas.

***Exemplo***: Debêntures corporativas de empresas de capital aberto (como a Unidas/OVSA), emissões privadas e notas comerciais.


- `BALCÃO NÃO ORGANIZADO`: Negociações realizadas diretamente entre as partes (comprador e vendedor), podendo ter a intermediação de uma corretora ou distribuidora, sem a intermediação de um sistema ou entidade administradora de mercado.

Não possui livro de ofertas, ambiente eletrônico centralizado nem garantias da bolsa. As condições da operação (preço, quantidade e liquidação) são livremente pactuadas entre as partes. A CVM exige apenas que os intermediários registrem a operação posteriormente em um depositário central autorizado para fins de controle e transparência regulatória.


### Coluna `CATEG_REG`

Categoria regulatória da empresa. Possíveis valores: `Categoria A`, `Categoria B` e `NULL`.

- `Categoria A`: Autoriza a negociação de QUALQUER valor mobiliário, incluindo Ações, BDRs, Debêntures e Notas Comerciais. (Ex: Vale, Petrobras, Itaú).

- `Categoria B`: Autoriza a negociação APENAS de títulos de dívida/renda fixa (Debêntures, Notas Comerciais, CRIs/CRAs). Empresas Categoria B NÃO PODEM ter Ações ou BDRs negociados em bolsa/balcão. 


### Coluna `SETOR_ATIV`

Levantamento completo no arquivo atual `data/cad_cia_aberta.csv` (inclui vazio). Total identificado: `71` valores distintos. Ultima atualização: `14/07/2026`.

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
