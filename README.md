# cvmdata

Pipeline de dados CVM para cálculo de **indicadores de análise fundamentalista** de companhias abertas brasileiras. 

***Consultar indicadores trimestrais da `PETROBRAS` dos últimos 5 anos.***

```sh
$ cvmdata indicators --cnpj "33.000.167/0001-01"
```

```sh
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ dt_refer   ┃ indicador           ┃             valor ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 2021-03-31 │ cobertura_juros     │           -1.0789 │
│ 2021-03-31 │ divida_bruta        │ 404316000000.0000 │
│ 2021-03-31 │ divida_liquida      │ 332862000000.0000 │
│ 2021-03-31 │ divida_liquida_pl   │            1.0394 │
│ 2021-03-31 │ endividamento_geral │           67.9204 │
│ 2021-03-31 │ giro_ativo          │            0.0863 │
│ ...        │ ...                 │...                │
│ 2025-09-30 │ roe                 │           18.3523 │
│ 2025-12-31 │ cobertura_juros     │          -43.9300 │
│ 2025-12-31 │ divida_bruta        │ 384025000000.0000 │
│ 2025-12-31 │ divida_liquida      │ 333417000000.0000 │
│ 2025-12-31 │ divida_liquida_pl   │            0.7984 │
│ 2025-12-31 │ endividamento_geral │           65.8664 │
│ 2025-12-31 │ giro_ativo          │            0.4067 │
│ 2025-12-31 │ liquidez_corrente   │            0.7059 │
│ 2025-12-31 │ liquidez_geral      │            0.3498 │
│ 2025-12-31 │ liquidez_imediata   │            0.1795 │
│ 2025-12-31 │ liquidez_seca       │            0.4782 │
│ 2025-12-31 │ margem_bruta        │           47.6331 │
│ 2025-12-31 │ margem_liquida      │           22.2300 │
│ 2025-12-31 │ margem_operacional  │           29.2691 │
│ 2025-12-31 │ roa                 │            9.0409 │
│ 2025-12-31 │ roe                 │           26.4867 │
└────────────┴─────────────────────┴───────────────────┘
```


### Indicadores calculados

Atualmente, são calculados 15 indicadores por trimestre, dos ultimos 5 anos de dados divulgados. 

Segue lista de fórmulas e mapeamento de contas CVM, de cada indicador: [`docs/analise_fundamentalista.md`](docs/analise_fundamentalista.md).


## Inicio Rápido

Projeto é gerenciado pelo [`UV - https://docs.astral.sh/uv/`](https://docs.astral.sh/uv/)


```bash
git clone https://github.com/dalmofelipe/cvmdata.git
cd cvmdata
uv sync
```

Para desenvolvimento (linter + testes + cobertura):

```bash
uv sync --extra dev
```


## Pipeline

Em ambiente Linux

```bash
make all
```

O processamento dos dados, geralmente leva entre **3 a 6 min**. Esse tempo varia conforme a configuração da maquina.

Para personalizar o pipeline, leia o documento [`docs/pipeline.md`](docs/pipeline.md).

Para executar diretamente via CLI:

```bash
cvmdata pipeline run
cvmdata pipeline run --years 2021:2025
```


## Consultando Indicadores

### Informações Cadastrais de Empresas

Atualmente, as buscas são feita com base no CNPJ da empresa.

Para buscas por informações cadastrais de empresas, use `info-cad`:

```bash
cvmdata info-cad
cvmdata info-cad --cnpj "33.000.167/0001-01"
```

## Indicadores

```bash
cvmdata indicators --cnpj "33.000.167/0001-01"

cvmdata indicators --cnpj "33.000.167/0001-01" --year 2025 # Somente indicadores de 2025
```

Retorna uma tabela contendo todos os indicadores trimestrais dos ultimos 5 anos.
