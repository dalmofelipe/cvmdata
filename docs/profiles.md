# Perfil de Contas e Regras Estruturais


## Objetivo

Fornecer uma estrutura para mapear e ajustar particularidades observadas nos demonstrativos financeiros reportados à CVM, de forma a permitir o cálculo correto dos indicadores do `cvmdata` para empresas com layouts distintos.


## Problema

No início, todos os indicadores de todas empresas eram calculados a partir de `ACCOUNT_MAP`, com mapeamento direto por `CD_CONTA` fixo. Porem, ele não atende à maior parte das companhias abertas não-financeiras.

Em vez de assumir um único `ACCOUNT_MAP` válido para todo o universo CVM, agora cada empresa é classificada em um **profile** (`default` ou `banking`). Esse profile orienta a seleção de contas nos módulos de cálculo/transformação, evitando casar contas com semânticas diferentes entre layouts.

Instituições financeiras — principalmente bancos — reportam demonstrativos com quantidades e semânticas de contas distintas. 

Ao integrar esses demonstrativos aplicando o profile "padrão/default" a instituições financeiras, percebeu-se que há um deslocamento observado entre os valores calculados pelo `cvmdata` e os esperados para esse subconjunto, resultando em muitos indicadores nulos ou valores inconsistentes.

As evidências que motivaram essa separação estão detalhadas em [`banking_profile.md`](banking_profile.md).


## Conceitos

O conceito de **profile** conecta três peças do projeto:

- **`profile` (classificação)** — é o perfil atribuído à empresa, é o que determina qual conjunto de contas selecionado nos demonstrativos da CVM, que será utilizado para calcular os indicadores da empresa. Atualmente o projeto tem dois profiles (`default` | `banking`).

- **`account_map`** — Estrutura o mapeamento de contas por profile. Define, por profile (e por conceito semântico), quais `CD_CONTA` devem ser selecionados para compor cada indicador. É o mapeamento "por código" usado quando a posição por `CD_CONTA` é estável para aquele profile.

- **`text_map`** — Alternativa ao `account_map`. Seleciona a conta via texto normalizado (minúsculo, sem acento, sem espaço nas pontas) da coluna `DS_CONTA` dos demonstrativos, identificando a conta correta para os calculos. Principalmente quanto os  `CD_CONTA` fixo **não é estável entre perfis ou até entre empresas do mesmo perfil**. 

**Esses módulos não são mutuamente exclusivos**: o pipeline pode usar `account_map` para buscar códigos previstos e, quando necessário, `text_map` para escolher **qual** das linhas encontradas corresponde semanticamente ao conceito (ex.: distinguir `2.03` como PL no `default` vs. como provisão/passivo em parte do universo financeiro).

***No geral, a combinação dessas ferramentas servem para auxiliar na seleção de contas e definição de perfis, realizando os ajustes necessários para aplicação correta dos calculos dos indicadores de cada empresa.***

<br>

## Perfil de Conta

Atualmente, o `cvmdata` reconhece dois perfis de contas: `default` e `banking`. A classificação é feita em `transform/info_cad/`, veja mais detalhes em [classificacao.md](classificacao.md).

### Profile `default`

É o perfil **padrão**: toda empresa que **não casa nenhuma regra estrutural** é classificada como `default`.

Características:

- Usa o `ACCOUNT_MAP` default para seleção por `CD_CONTA` fixa.
- O Patrimônio Líquido é resolvido por texto normalizado (`resolve_pl`) sempre que aplicável, pois mesmo no `default` há casos em que a posição por código varia ao longo do histórico ou entre demonstrações.
- Quando não há casamento com nenhuma regra, o motivo é registrado em `rule_applied` com um dos fallbacks:
  - `default:sem_cadastro:sem_assinatura` — sem vínculo com `cad_cia_aberta_raw` (não existe linha correspondente após `LEFT JOIN cad`) **e** sem regra casada
  - `default:setor_vazio` — existe cadastro, mas `setor_ativ` é nulo/vazio
  - `default:setor:<setor>` — existe cadastro e setor conhecido, mas nenhuma regra casou

O universo continua sendo `bpa_clean UNION bpp_clean UNION dre_clean`. Empresas que reportam **somente DRE** entram no universo e, caso não casem nenhuma regra definida, recebem `default` com o fallback correspondente.

### Profile `banking`

Os resultados incorretos de indicadores para bancos motivaram a criação do mecanismo de profiles, que busca extrair e separa subconjuntos de contas do universo CVM.

O profile `banking` busca identificar o layout COSIF/bancário por **Regra Estrutural (StructuralRule)**, onde ocorre quando todas **Condições de Regra (RuleCondition)** forem satisfeitas. Atualmente estão mapeados as duas condições:

- **BPA (`bpa_clean`)**: `CD_CONTA = '1.01'` com `DS_CONTA` normalizado igual a `"caixa e equivalentes de caixa"`
- **BPP (`bpp_clean`)**: `CD_CONTA = '2.01'` com `DS_CONTA` normalizado **começando com (prefixo)** `"passivos financeiros"`

Quando casados as condições, `rule_applied` registra a decisão, por exemplo: `structure:banking:bpa.1.01+bpp.2.01`.

A **interseção** dessas regras é o que separa, de forma consistente, o subconjunto bancário/financeiro do restante. Essa decisão está fundamentada na análise de dados reais (ITR 2025) e nos fixtures bancários, ver [banking_profile.md](banking_profile.md).

<br>

## Regras Estruturais - `STRUCTURAL_RULES`

O modulo `src/cvmdata/transform/profile/rules.py` forneçe uma estrutura base `STRUCTURAL_RULES`, para mapeamento e ajustes de caracteristicas observadas nos demonstrativos financeiros. 

Cada caracteristica estrutural observada nos desmonstrativos, deve virar uma **Condição de Regra (RuleCondition)**. Essas condições são agrupadas formando uma **Regra Estrutural (StructuralRule)**, assim definindo novo perfil/profile com base nessas observações.

**Por exemplo no setor de `Bancário`**: 

- Foi observado que "Caixa e Equivalentes" sobe para um valor agregado com código de conta, `CD_CONTA: 1.01`. Enquando no profile `default` era uma subdivisão de "Ativo Total" com `CD_CONTA: 1.01.01`.

- O mesmo para variações de "Passivos Financeiros...". Empresas que  reportam variações do termo "passivos financeiros" em `CD_CONTA 2.01 e 2.02`, pode indicar, que se trata de uma instituição financeira. No profile `default` essas contas seriam "Passivo Circulante e não Circulante".

Todas essas condições observadas, devem ser satisfeitas para definir corretamente o `profile_id` da empresa e assim aplicar o conjunto contas correto, para calculo dos indicadores.

`STRUCTURAL_RULES` é processada durante a classificação cadastral, cada regra estrural será convertida em uma expressão SQL que compõe a consulta de classificação: `SQL_CLASSFY`, gerando a tabela `company_classification` consolidando o universo de empresas e seus respectivos profiles de contas.

**Importante**: A ordem da lista `STRUCTURAL_RULES` é o que define a precedência. O SQL é um ``CASE WHEN`` sequencial e a primeira regra que casar vence.

Logo, se uma regra tiver mais especificidade/condições precisa vir antes da geral, ou nunca vai disparar. O contador por ``rule_applied`` denuncia isso: uma regra que nunca casa aparece com 0, mesmo que a regra geral produza os mesmos números.

Mais detalhes em [classificacao.md](classificacao.md).

<br>

## Classificando perfis pela query `SQL_CLASSIFY`

A classificação é inteiramente renderizada em SQL por `src/cvmdata/transform/info_cad/sql.py`. `SQL_CLASSIFY` é um template único com **3 placeholders**: `rule_matches_sql`, `profile_sql`, `rule_applied_sql`.

```sql
    --...
    rule_matches AS (
        SELECT
            u.CNPJ_CIA AS cnpj_cia,
            {{rule_matches_sql}}
        FROM universo u
    )
    INSERT INTO {TB_COMPANY_CLASSIFICATION}
        (cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ,
        profile_id, rule_applied, updated_at)
    SELECT
        u.CNPJ_CIA                        AS cnpj_cia,
        COALESCE(CAST(c.CD_CVM AS VARCHAR), CAST(u.cd_cvm AS VARCHAR)) AS cd_cvm,
        COALESCE(c.DENOM_SOCIAL, u.denom_social) AS denom_social,
        c.DENOM_COMERC                    AS denom_comerc,
        c.setor_ativ                      AS setor_ativ,
        {{profile_sql}}                   AS profile_id,
        {{rule_applied_sql}}              AS rule_applied,
        current_timestamp                 AS updated_at
    --...
```

Considerando atualmente o unico perfil `banking` definido em `STRUCTURAL_RULES`:

```py
STRUCTURAL_RULES: list[StructuralRule] = [
    StructuralRule(
        profile_id="banking",
        conditions=(
            RuleCondition(
                clean_table=TB_BPA_CLEAN,
                cd_conta="1.01",
                ds_conta_normalized="caixa e equivalentes de caixa",
            ),
            RuleCondition(
                clean_table=TB_BPP_CLEAN,
                cd_conta="2.01",
                ds_conta_normalized="passivos financeiros",
                starts_with=True,
            ),
        ),
        description=("..."),
    ),
]
```

<br>

### CTE rule_matches

A CTE ``rule_matches`` é a tabela intermediária que armazena os resultados das condições de cada regra estrutural, para cada empresa do universo.

```sql
    --...
    rule_matches AS (
        SELECT
            u.CNPJ_CIA AS cnpj_cia,
            {{rule_matches_sql}}
        FROM universo u
    )
    --...
```

O metodo `rule_matches_sql` prepara a expressão SQL que define se cada regra estrutural é satisfeita para cada empresa. Cada **RuleCondition** de uma **StructuralRule**, vira um ``EXISTS`` correlacionado pelo CNPJ. O resultado só é verdadeiro quando todos os ``EXISTS`` de uma StructuralRule (rule_{n}_match) encontram correspondência.

```sql
    EXISTS (
        SELECT 1 
        FROM bpa_clean condition_0
        WHERE condition_0.CNPJ_CIA = u.CNPJ_CIA
            AND condition_0.CD_CONTA = ? -- param '1.01'
            -- param 'caixa e equivalentes de caixa'
            AND lower(strip_accents(trim(condition_0.DS_CONTA))) = ?
    )
    AND EXISTS (
        SELECT 1 
        FROM bpp_clean condition_1
        WHERE condition_1.CNPJ_CIA = u.CNPJ_CIA
            AND condition_1.CD_CONTA = ? -- param '2.01'
            -- param 'passivos financeiros'
            AND starts_with(lower(strip_accents(trim(condition_1.DS_CONTA))), ?)
    ) 
    AS rule_0_match -- regra de banking na posição 0 da lista STRUCTURAL_RULES
    --...
    AS rule_1_match -- para uma possivel segunda regra, etc.
```

A execução da query produzirá uma tabela intermediária com uma coluna booleana por regra, na ordem de `STRUCTURAL_RULES`:

| cnpj_cia | rule_0_match (banking) | rule_1_match | rule_2_match | rule_n_match |
|:---|:---|:---|:---|:---|
| empresa A | true | false | false | ... |
| empresa B | false | true | false | ... |

Com essa estrutura é possível identificar quais empresas casaram com qual regra, e assim definir o `profile_id` e `rule_applied` na consulta principal.

<br>

### Perfil e Regra Aplicada

O metodo `classification_sql` renderiza as expressões SQL que finalmente definem o perfil da empresa ``profile_id`` e a qual regra foi aplicada ``rule_applied`` para cada empresa na consulta de classificação `SQL_CLASSIFY`.

Recebe a lista de regras estruturais `STRUCTURAL_RULES` na ordem de precedência, e gera dois ``CASE WHEN``: 

- `profile_sql`: um que define o profile ``profile_id``
- `rule_applied_sql`: e outro para regra aplicada ``rule_applied``

```sql
    -- para definição do perfil de conta da empresa
    CASE WHEN rm.rule_0_match 
        THEN 'banking' ELSE 'default' END       AS profile_id,

    -- um "switch-case" para definição da regra aplicada
    CASE 
        WHEN rm.rule_0_match 
            THEN 'structure:banking:bpa.1.01+bpp.2.01'
        WHEN c.CNPJ_CIA IS NULL 
            THEN 'default:sem_cadastro:sem_assinatura'
        WHEN c.setor_ativ IS NULL OR trim(c.setor_ativ) = '' 
            THEN 'default:setor_vazio'
        ELSE 
            'default:setor:' || trim(c.setor_ativ)
    END                                     
    AS rule_applied,
```

<br>

### Exemplo de `SQL_CLASSIFY` renderizado

```sql
    --...
    rule_matches AS (
        SELECT
            u.CNPJ_CIA AS cnpj_cia,
            EXISTS (
                SELECT 1 
                FROM bpa_clean condition_0
                WHERE condition_0.CNPJ_CIA = u.CNPJ_CIA
                    AND condition_0.CD_CONTA = ?
                    AND lower(strip_accents(trim(condition_0.DS_CONTA))) = ?
            )
            AND EXISTS (
                SELECT 1 
                FROM bpp_clean condition_1
                WHERE condition_1.CNPJ_CIA = u.CNPJ_CIA
                    AND condition_1.CD_CONTA = ?
                    AND starts_with(lower(strip_accents(trim(condition_1.DS_CONTA))), ?)
            )
            AS rule_0_match
        FROM universo u
    )
    INSERT INTO {TB_COMPANY_CLASSIFICATION}
        (cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ,
        profile_id, rule_applied, updated_at)
    SELECT
        u.CNPJ_CIA                                  AS cnpj_cia,
        COALESCE(
            CAST(c.CD_CVM AS VARCHAR),
            CAST(u.cd_cvm AS VARCHAR)
        )                                           AS cd_cvm,
        COALESCE(c.DENOM_SOCIAL, u.denom_social)    AS denom_social,
        c.DENOM_COMERC                              AS denom_comerc,
        c.setor_ativ                                AS setor_ativ,
        CASE WHEN rm.rule_0_match 
            THEN 'banking' ELSE 'default' END       AS profile_id,
        CASE 
            WHEN rm.rule_0_match 
                THEN 'structure:banking:bpa.1.01+bpp.2.01'
            WHEN c.CNPJ_CIA IS NULL 
                THEN 'default:sem_cadastro:sem_assinatura'
            WHEN c.setor_ativ IS NULL OR trim(c.setor_ativ) = '' 
                THEN 'default:setor_vazio'
            ELSE 
                'default:setor:' || trim(c.setor_ativ)
            END                                     AS rule_applied,
        current_timestamp                           AS updated_at
    FROM universo u
    LEFT JOIN cad c
        ON c.CNPJ_CIA = u.CNPJ_CIA
        AND c.rn = 1
    LEFT JOIN rule_matches rm
        ON rm.cnpj_cia = u.CNPJ_CIA
    --...
```
