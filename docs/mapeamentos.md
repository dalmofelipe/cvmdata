# Mapeamento de contas da CVM por código e texto da descrição

## Código de conta (CD_CONTA) e ACCOUNT_MAP

É o mapeamento direto de cada código de conta dos demonstrativos (BPA, BPP, DRE) agrupados por perfil. Cada perfil `default/banking`, busca selecionar as linhas nos demonstrativos CVM pelo CD_CONTA (1.01, 2.02, 3.01, ...), que serão aplicados nas formulas do plano de calculo `src/cvmdata/transform/calc_plan.py` e assim calcular os indicadores de cada empresa por período. O mapeamento é feito em `src/cvmdata/transform/account_map.py`.

```python
ACCOUNT_MAP: dict[str, dict[str, str]] = {
    "default": {
        # BPA — Balanço Patrimonial Ativo
        "1": "ativo_total",
        ...,
        # BPP — Balanço Patrimonial Passivo
        "2": "passivo_total",
        ...,
        # DRE — Demonstração de Resultado
        "3.01": "receita_liquida",
        ...,
    },
    "banking": {
        # BPA — Balanço Patrimonial Ativo
        "1": "ativo_total",
        ...,
        # BPP - Balanço Patrimonial Passivo
        "2": "passivo_total",
        ...,
        # DRE — Demonstração de Resultado
        ...,
        "3.11": "lucro_liquido",
    },
}
```

O mapeamento direto é utilizado quando a posição do código de conta é estável/fixo entre empresas em todo período processado. Por exemplo, o "Ativo Total" é sempre `1` no BPA, independente do perfil. Quando o codigo não for sulficiente para identificar o componente, o mapeamento por texto `TEXT_MAP` é utilizado.

<br>

## Resolução por texto (TEXT_MAP) de descrição de contas da CVM (DS_CONTA)

Ao analisar os demonstrativos da CVM, percebe-se que alguns componentes não possuem posição fixa entre perfis. Sendo assim, foi necessário criar um mapeamento por texto (TEXT_MAP) aplicado na descrição das contas (DS_CONTA), para identificar corretamente o componente e realizar os ajustes necessários para calcular os indicadores corretamente. 

O mapeamento por texto da descrição de conta é feito em `src/cvmdata/transform/text_map.py`. Tambem possui metodos de apoio para resolver o patrimônio líquido (PL) e a DRE, que são os casos mais comuns de deslocamento de posição entre perfis.

```python
DRE_TAIL_TEXT_MAP: dict[str, str] = {
    "resultado antes dos tributos sobre o lucro": "resultado_antes_tributos",
    "imposto de renda e contribuicao social sobre o lucro": "imposto_renda_csll",
    "resultado liquido das operacoes continuadas": "resultado_liquido_continuadas",
    "lucro/prejuizo liquido das operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido de operacoes descontinuadas": "ajuste_descontinuadas",
    "resultado liquido das operacoes descontinuadas": "ajuste_descontinuadas",
}

BPP_PL_TEXT_MAP: dict[str, str] = {
    "patrimonio liquido": "patrimonio_liquido",
}
```

> `IMPORTANTE`: A resolução por texto é combinada com mapeamentos por código. É importante manter os codigos `CD_CONTA` encontrados para cada descrição de texto `DS_CONTA`, como em `BPP_PL_CODES` e `DRE_TAIL_CODES` de `account_map.py`. O que define quais linhas dos demonstrativos que serão salvos no banco de dados são os codigos `CD_CONTA`, e o resolvedor textual `TEXT_MAP` confirma se a linha é realmente o componente esperado.

É muito importante analisar corretamente os demonstrativos da CVM, para identificar os componentes que não possuem posição fixa entre perfis, seus codigos e descrições. Dicas para explorar os desmonstrativos da CVM via DuckDB e SQL, estão em [`analise_demonstrativos_cvm.md`](analise_demonstrativos.md).

<br>

## Descrições de Contas Mapeadas (DS_CONTA)

Analise realizada principalmente nos demonstrativos DFPs, que devem refletir nos ITRs.

Veja mais em [`analise_demonstrativos_cvm.md`](analise_demonstrativos.md).

### BPP — Balanço Patrimonial Passivo (Códigos iniciados em 2.x)

#### Resolução do `Patrimônio Líquido`

```python
# account_map.py
BPP_PL_CODES: list[str] = [
    "2.03",
    "2.07",
    "2.08",
]

# text_map.py
BPP_PL_TEXT_MAP: dict[str, str] = {
    "patrimonio liquido": "patrimonio_liquido",
}
```

Ao buscar o termo **"patrimonio liquido consolidado"** normalizado, na coluna `DS_CONTA` em todos os desmonstrativos BPP consolidado, período 2020-2026, retorna um conjunto de códigos de conta `CD_CONTA` diferentes: `2.03, 2.07 e 2.08`. 

- `2.03`: grande maioria das empresas não-financeiras (`default`)
- `2.07 e 2.08`: varia entre bancos (`banking`)

Esses codigos encontrados, foram registrados em `BPP_PL_CODES` de `account_map.py`.

Para resolução por texto, `resolve_pl` em `text_map.py` aceita apenas os códigos candidatos de `BPP_PL_CODES` e confirma o PL pelo **prefixo normalizado** (`startswith("patrimonio liquido")`). Assim, resulta o valor correto do PL de acordo com cada perfil.


### DRE — Demonstração de Resultado (Códigos iniciados em 3.x)

As buscas foram realizadas com `lower(strip_accents(trim(DS_CONTA)))` nos demonstrativos DRE consolidados, período 2020-2026, e os resultados foram agrupados por perfil (default, banking, seguradoras) e por código de conta `CD_CONTA`:

| Texto normalizado analisado | Distribuição por perfil/observação |
| --- | --- |
| `resultado antes dos tributos sobre o lucro` | `3.05` Banking; `3.07` Default; `3.09` Seguradoras |
| `imposto de renda e contribuicao social sobre o lucro` | `3.06` Banking; `3.08` Default; `3.10` Seguradoras |
| `resultado liquido das operacoes continuadas` | `3.07` Banking; `3.09` Default; `3.10` Seguradoras |
| `lucro/prejuizo liquido das operacoes descontinuadas` | `3.08.01` Banking; `3.10.01` Default; `3.12.01` Seguradoras |
| `resultado liquido de operacoes descontinuadas` | `3.10` Default; `3.12` Seguradoras; Banking sem registros |
| `resultado liquido das operacoes descontinuadas` | `3.08` Banking; `3.10.01.01` outlier; Default sem registros |

Exemplo de consulta SQL para validação do texto normalizado em [`docs/DFP_DRE.sql`](DFP_DRE.sql).

O perfil para "Seguradoras" ainda não foi consolidado, mas já é possível identificar que os códigos de conta são diferentes dos perfis "Default" e "Banking", sendo possível candidato para novo perfil. Por isso, o mapeamento por texto é necessário para resolver corretamente os componentes dos demonstrativos.

Cabe mais investigação com variações de texto, contudo essa análise inicial já permite identificar dos componentes e realizar os ajustes necessários para calcular os indicadores corretamente.

> INFO: Seja criterioso com cada codigo adicionado aos mapeamentos, pois apenas um código pode significar o carregamento de milhares de linhas do demonstrativo no banco de dados.

***É importante continuar a pesquisa nos contextos econômicos/financeiros, para validar se esses componentes fazem sentido nos indicadores de acordo com perfis específicos***.
