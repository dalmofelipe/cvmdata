# Classificação Cadastral e Resolução de Perfil de Contas

Como o projeto consolida as informações de todas empresas que reportaram resultados a CVM, incluindo definição de perfil em uma única tabela, `company_classification`.

#### Template do SQL_CLASSIFY

```sql
WITH universo AS (
    SELECT
        CNPJ_CIA,
        first(CD_CVM    ORDER BY DT_REFER DESC NULLS LAST, CD_CVM    ASC NULLS LAST) AS cd_cvm,
        first(DENOM_CIA ORDER BY DT_REFER DESC NULLS LAST, DENOM_CIA ASC NULLS LAST) AS denom_social
    FROM (
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_BPA_CLEAN}
            UNION
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_BPP_CLEAN}
            UNION
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_DRE_CLEAN}
    )
    GROUP BY CNPJ_CIA
),
cad AS (
    SELECT
        CNPJ_CIA,
        CD_CVM,
        DENOM_SOCIAL,
        DENOM_COMERC,
        NULLIF(trim(CAST(SETOR_ATIV AS VARCHAR)), '') AS setor_ativ,
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA
            ORDER BY
                TRY_CAST(DT_INI_SIT AS DATE) DESC NULLS LAST,
                CD_CVM ASC NULLS LAST,
                DENOM_SOCIAL ASC NULLS LAST
        ) AS rn
    FROM {TB_CAD_CIA_ABERTA_RAW}
),
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
FROM universo u
LEFT JOIN cad c
    ON c.CNPJ_CIA = u.CNPJ_CIA
    AND c.rn = 1
LEFT JOIN rule_matches rm
    ON rm.cnpj_cia = u.CNPJ_CIA
```

<br>

### CTE universo u

```sql
WITH universo AS (
    SELECT
        CNPJ_CIA,
        first(CD_CVM    ORDER BY DT_REFER DESC NULLS LAST, CD_CVM    ASC NULLS LAST) AS cd_cvm,
        first(DENOM_CIA ORDER BY DT_REFER DESC NULLS LAST, DENOM_CIA ASC NULLS LAST) AS denom_social
    FROM (
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_BPA_CLEAN}
            UNION
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_BPP_CLEAN}
            UNION
        SELECT CNPJ_CIA, DT_REFER, CD_CVM, DENOM_CIA FROM {TB_DRE_CLEAN}
    )
    GROUP BY CNPJ_CIA
),
``` 

O `cvmdata` processa todas empresas que reportaram resultados no periodo informado na run do pipeline. A fonte verdade são os proprios demonstrativos BPA, BPP e DRE.

Logo o primeiro passo da classificação é o Universo, formado pela `UNION` das tabelas *_clean: `bpa_clean`, `bpp_clean` e `dre_clean`. As três precisam existir. Se faltar uma, `classify_info_cad` lança `MissingCleanTablesError`.

A CTE universo é uma tabela que contém dados de todas empresas que terão indicadores calculados.

<br>

### CTE cad c (Cadastro)

```sql
cad AS (
    SELECT
        CNPJ_CIA,
        CD_CVM,
        DENOM_SOCIAL,
        DENOM_COMERC,
        NULLIF(trim(CAST(SETOR_ATIV AS VARCHAR)), '') AS setor_ativ,
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA
            ORDER BY
                TRY_CAST(DT_INI_SIT AS DATE) DESC NULLS LAST,
                CD_CVM ASC NULLS LAST,
                DENOM_SOCIAL ASC NULLS LAST
        ) AS rn
    FROM {TB_CAD_CIA_ABERTA_RAW}
),
``` 

Simplesmente é uma consulta na tabela `cad_cia_aberta_raw`, com a linha mais recente por CNPJ. A coluna `setor_ativ` é normalizada para `NULL` se estiver em branco.

Ela é necessária para complementar informações das empresas, uma vez que na tabela universo, temos somente CNPJ, CD_CVM e DENOM_SOCIAL. As demais colunas são complementadas pelo cadastro.

> Na tabela de `cad_cia_aberta_raw`, pode ter multiplas linhas para o mesmo CNPJ/empresa, diferenciando somente os valores da coluna `TP_MERC`. A linha mais recente é escolhida pelo select `AND c.rn = 1`.

> `IMPORTANTE`: Pode ocorrer de uma empresa reportar demonstrativo, estar no universo, mas não estar no cadastro.

<br>

### CTE rule_matches rm (Regras de Estruturais, STRUCTURAL_RULES)

```sql
rule_matches AS (
    SELECT
        u.CNPJ_CIA AS cnpj_cia,
        {{rule_matches_sql}}
    FROM universo u
)
```

Objetivo final da CTE `rule_matches` é gerar um booleano por Regra Estrutural (StructuralRule), que indica se os dados da empresa analisada, casa/combina com todas as condições da regra para determinar o perfil da empresa. No final, gera uma tabela com o CNPJ e os booleanos de cada regra, que será usada no `CASE` para determinar o perfil da empresa.

| cnpj_cia | rule_0_match (banking) | rule_n_match |
|:---|:---|:---|
| empresa A | true | ... |
| empresa B | false | ... |

`rule_0_match` é o booleano que indica se a **empresa A** casa com a regra de perfil `banking`. O `index 0` é a primeira regra da lista `STRUCTURAL_RULES`. A ordem das regras é importante, pois a primeira que casar, vence.

> `IMPORTANTE`: Sempre lembrar que o profile `default` é o perfil padrão, que é atribuído a todas empresas que não casarem com nenhuma regra estrutural.

O detalhamente extremo de como funciona as regras estruturais, e como o SQL é gerado a partir das regras, está em [`profiles.md`](profiles.md).

<br>

### INSERT-SELECT Template: `{{profile_sql}}`

O template `{{profile_sql}}` é substituido pelo código SQL do `CASE-WHEN` que decide o perfil da empresa, baseado nos booleanos das regras estruturais, em  `rule_matches rm`. A primeira regra que casar, vence.

```sql
-- "if true" then "banking" else "default"
CASE WHEN rm.rule_0_match 
    THEN 'banking' ELSE 'default' END AS profile_id,
```

<br>

### INSERT-SELECT Template: `{{rule_applied_sql}}`

Também é um template para aplicar um feedback da regra aplicada a empresa, ajuda a identificar como foi classificado. O template `{{rule_applied_sql}}` é substituido pela SQL: 

```sql
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

#### Regras de preenchimento de `rule_applied`

O `CASE` é avaliado de cima para baixo. A primeira condição verdadeira define o valor gravado em `rule_applied`; por isso, a ordem das linhas é parte da regra de classificação.

| Ordem | Condição | Valor de `rule_applied` | Interpretação |
| --- | --- | --- | --- |
| 1 | `rm.rule_0_match` | `structure:banking:bpa.1.01+bpp.2.01` | Empresa identificada pela assinatura estrutural do perfil `banking` |
| 2 | `c.CNPJ_CIA IS NULL` | `default:sem_cadastro:sem_assinatura` | Empresa presente nos demonstrativos, mas sem cadastro correspondente |
| 3 | `c.setor_ativ IS NULL OR trim(c.setor_ativ) = ''` | `default:setor_vazio` | Empresa cadastrada, mas sem setor de atividade preenchido |
| 4 | `ELSE` | `default:setor:<setor>` | Empresa sem assinatura estrutural, com o setor de atividade informado; `<setor>` recebe `trim(c.setor_ativ)` |

Assim, empresas que não atendem à regra estrutural de `banking` são classificadas como `default`, e o valor registrado informa se isso ocorreu por falta de cadastro, setor vazio ou setor preenchido.

<br>

### INSERT-SELECT

```sql
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
FROM universo u
LEFT JOIN cad c
    ON c.CNPJ_CIA = u.CNPJ_CIA
    AND c.rn = 1
LEFT JOIN rule_matches rm
    ON rm.cnpj_cia = u.CNPJ_CIA
```

O `INSERT-SELECT` final materializa o resultado da classificação na tabela `company_classification`. A consulta usa `universo` como fonte principal, pois essa CTE contém uma linha por empresa que reportou pelo menos um dos demonstrativos `BPA`, `BPP` ou `DRE`.

| Coluna de destino | Expressão selecionada | Finalidade |
| --- | --- | --- |
| `cnpj_cia` | `u.CNPJ_CIA` | Identificador da empresa no universo dos demonstrativos |
| `cd_cvm` | `COALESCE(CAST(c.CD_CVM AS VARCHAR), CAST(u.cd_cvm AS VARCHAR))` | Usa o código do cadastro; se não houver cadastro, mantém o código mais recente do universo |
| `denom_social` | `COALESCE(c.DENOM_SOCIAL, u.denom_social)` | Usa a denominação social do cadastro ou, na ausência, a denominação do demonstrativo |
| `denom_comerc` | `c.DENOM_COMERC` | Denominação comercial disponível no cadastro; não é inferida do demonstrativo |
| `setor_ativ` | `c.setor_ativ` | Setor de atividade normalizado pela CTE `cad` |
| `profile_id` | `{{profile_sql}}` | Perfil definido pela assinatura estrutural das contas reportadas |
| `rule_applied` | `{{rule_applied_sql}}` | Regra, ausência cadastral ou setor que explica a classificação |
| `updated_at` | `current_timestamp` | Data e hora da gravação ou atualização da classificação |

Como os dois relacionamentos são `LEFT JOIN`, a empresa permanece no resultado mesmo quando não existe registro correspondente no cadastro ou em `rule_matches`. Isso permite que empresas sem cadastro sejam gravadas e identificadas por `default:sem_cadastro:sem_assinatura`, em vez de serem removidas silenciosamente da classificação.
