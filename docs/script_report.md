# SCRIPT - Relatório de comparação de indicadores com plataformas externas

O [scripts/report.py](../scripts/report.py) compara os indicadores
fundamentalistas calculados pelo `cvmdata` com os valores publicados por
plataformas externas, como Status Invest, Fundamentus, Investidor10 e Dados de
Mercado.

Para cada empresa, período, plataforma e indicador configurado, o script:

- busca o valor correspondente na tabela `indicators` do DuckDB;
- compara o valor do `cvmdata` com o valor da plataforma externa;
- calcula o desvio percentual;
- destaca em vermelho os valores fora da tolerância configurada;
- exibe o resultado no terminal usando Rich;
- salva o resultado em `scripts/report.csv`.

Os valores externos são cadastrados manualmente no próprio
[scripts/report.py](../scripts/report.py). O script não acessa as plataformas
externas automaticamente.

## Como executar

Na raiz do projeto, instale as dependências dos scripts:

```sh
uv sync --extra scripts
```

Depois execute:

```sh
uv run python scripts/report.py
```

O banco utilizado é o configurado pelo projeto, normalmente:

```text
data/db/cvmdata.duckdb
```

Se o banco estiver em outro diretório, use a configuração já suportada pelo
projeto, por exemplo:

```sh
CVM_DATA_DIR=/caminho/para/data uv run python scripts/report.py
```

O arquivo CSV é sempre criado no mesmo diretório do script:

```text
scripts/report.csv
```

Esse arquivo está incluído no `.gitignore` e não deve ser versionado.

## Tolerância do desvio

A tolerância é definida no início do script:

```python
TOLERANCE: float = 0.05
```

O valor é informado como decimal:

```python
TOLERANCE = 0.05  # 5%
TOLERANCE = 0.10  # 10%
```

O desvio é calculado como:

```text
(valor_cvmdata - valor_externo) / valor_externo_absoluto
```

Assim:

- `+5.56%` significa que o valor do `cvmdata` é maior;
- `-4.20%` significa que o valor do `cvmdata` é menor;
- `--` significa que um dos valores não está disponível ou que o valor
  externo é zero.

Os valores comparados são arredondados para duas casas antes do cálculo.

## Estrutura da configuração

As estruturas principais são:

```python
@dataclass(frozen=True)
class Indicator:
    name: str
    value: float | None


PlatformIndicators = dict[Period, list[Indicator]]


@dataclass(frozen=True)
class Company:
    cnpj: str
    platforms: dict[str, PlatformIndicators]


@dataclass(frozen=True)
class ReportCompany:
    companies: list[Company]
```

O `ReportCompany` contém uma lista explícita de objetos `Company`. Dessa forma,
cada CNPJ permanece agrupado com seus próprios dados e não depende da posição
de outro dicionário ou lista.

## Guia: adicionando uma nova plataforma

### 1. Crie o CNPJ da empresa

Use o mesmo CNPJ armazenado na coluna `cnpj_cia` do DuckDB, normalmente no
formato mascarado:

```python
FUNDAMENTUS_CVM_ITUB_CNPJ = "60.872.504/0001-23"
```

O CNPJ é usado para buscar:

- os indicadores na tabela `indicators`;
- o nome da empresa na tabela `company_classification`;
- o perfil da empresa na tabela `company_classification`.

### 2. Crie o dicionário de indicadores da plataforma

O dicionário deve ter períodos como chaves e listas de `Indicator` como
valores:

```python
FUNDAMENTUS_CVM_ITUB_INDICATORS: PlatformIndicators = {
    Period(2025, 12): [
        Indicator("giro_ativo", 0.13),
        Indicator("margem_bruta", 35.89),
        Indicator("margem_liquida", 11.59),
        Indicator("roe", 21.93),
    ],
    Period(2026, 6): [
        Indicator("giro_ativo", 0.12),
        Indicator("margem_bruta", 37.23),
        Indicator("margem_liquida", 12.13),
        Indicator("roe", 21.50),
    ],
}
```

Use `None` quando a plataforma não publicar um indicador:

```python
Indicator("roic", None)
```

Não é necessário cadastrar todos os indicadores do `CALC_PLAN`. A plataforma
pode conter somente os indicadores disponíveis nela.

### 3. Adicione a plataforma na empresa

Inclua a plataforma no dicionário `platforms` da empresa:

```python
REPORT_COMPANY = ReportCompany(
    companies=[
        Company(
            cnpj=STATUS_INVEST_CVM_ITUB_CNPJ,
            platforms={
                "Status Invest": STATUS_INVEST_CVM_ITUB_INDICATORS,
                "Fundamentus": FUNDAMENTUS_CVM_ITUB_INDICATORS,
            },
        ),
    ]
)
```

O nome da chave, como `"Fundamentus"`, é o nome que aparecerá na coluna
`Plataforma` do terminal e no CSV.

## Guia: adicionando uma nova empresa

Para cadastrar uma nova empresa:

1. defina o CNPJ;
2. crie um dicionário de indicadores para cada plataforma desejada;
3. adicione um novo `Company` dentro de `REPORT_COMPANY.companies`.

Exemplo:

```python
DADOS_DE_MERCADO_CVM_PETR_CNPJ = "33.000.167/0001-01"

DADOS_DE_MERCADO_CVM_PETR_INDICATORS: PlatformIndicators = {
    Period(2025, 12): [
        Indicator("capital_giro", -58342 * 1_000_000),
        Indicator("divida_bruta", 384025 * 1_000_000),
        Indicator("divida_liquida", 333417 * 1_000_000),
        Indicator("giro_ativo", 0.41),
        Indicator("margem_bruta", 47.63),
        Indicator("roe", 26.49),
    ],
}

REPORT_COMPANY = ReportCompany(
    companies=[
        Company(
            cnpj=STATUS_INVEST_CVM_ITUB_CNPJ,
            platforms={
                "Status Invest": STATUS_INVEST_CVM_ITUB_INDICATORS,
            },
        ),
        Company(
            cnpj=DADOS_DE_MERCADO_CVM_PETR_CNPJ,
            platforms={
                "Dados de Mercado": DADOS_DE_MERCADO_CVM_PETR_INDICATORS,
            },
        ),
    ]
)
```

Para remover temporariamente uma empresa do relatório, remova o respectivo
objeto `Company` da lista. Para remover uma plataforma, remova apenas sua
entrada no dicionário `platforms`.

## Guia de períodos

Use sempre `Period(ano, mês)`:

```python
Period(2025, 12)
Period(2026, 6)
```

O período é convertido para `YYYY-MM` e comparado como prefixo da coluna
`dt_refer`. Por exemplo:

```text
Period(2026, 6) -> "2026-06"
"2026-06"       -> "2026-06-30"
```

O mês deve ser informado como número entre 1 e 12. A classe faz o
preenchimento do zero à esquerda automaticamente.

## Guia de indicadores

O campo `Indicator.name` deve ser exatamente igual ao nome usado na coluna
`indicador` da tabela `indicators`. Os nomes formalizados pelo projeto estão
em `CALC_PLAN`, no arquivo
[src/cvmdata/transform/calc_plan.py](../src/cvmdata/transform/calc_plan.py).

Exemplos válidos:

```python
Indicator("capital_giro", -58342 * 1_000_000)
Indicator("divida_bruta", 384025 * 1_000_000)
Indicator("divida_liquida", 333417 * 1_000_000)
Indicator("margem_bruta", 47.63)
Indicator("roe", 26.49)
```

Indicadores cadastrados em uma plataforma são comparados somente para aquela
plataforma. Portanto, é possível que cada plataforma tenha uma quantidade
diferente de indicadores.

### Unidades e casos especiais

Os valores devem usar a mesma unidade esperada pelo indicador no `cvmdata`.
Para os indicadores monetários abaixo, informe o valor absoluto em reais:

- `capital_giro`;
- `divida_bruta`;
- `divida_liquida`.

Eles são formatados no terminal e no CSV como moeda brasileira, por exemplo:

```text
R$ -58.342.000.000,00
R$ 384.025.000.000,00
```

O indicador `roa` deve seguir a convenção usada pelo `cvmdata`, em percentual.
Se uma plataforma publicar ROA em formato decimal, faça a conversão durante o
cadastro:

```python
Indicator("roa", 0.10 * 100)
```

## Saída

A tabela do terminal contém:

| Coluna | Descrição |
|---|---|
| Empresa | `denom_comerc` ou `denom_social` da classificação |
| Período | Período informado no cadastro |
| Plataforma | Nome configurado no dicionário `platforms` |
| Indicador | Nome do indicador comparado |
| CVMData | Valor encontrado na tabela `indicators` |
| Externo | Valor informado manualmente |
| Desvio | Diferença percentual entre os valores |

O CSV contém as mesmas informações, além de `cnpj`, `perfil` e
`fora_tolerancia`. Valores ausentes são representados como `--`.

## Checklist para um novo cadastro

- [ ] Confirmar o CNPJ na tabela `company_classification`.
- [ ] Confirmar que o CNPJ está no mesmo formato usado no DuckDB.
- [ ] Usar nomes de indicadores existentes em `CALC_PLAN`.
- [ ] Conferir a unidade dos valores monetários.
- [ ] Converter indicadores percentuais publicados em formato decimal.
- [ ] Informar `None` quando a plataforma não tiver um valor.
- [ ] Confirmar o período com `Period(ano, mês)`.
- [ ] Executar o script e revisar o terminal.
- [ ] Revisar `scripts/report.csv`.