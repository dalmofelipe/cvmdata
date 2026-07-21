# cvmdata

Pipeline dos dados abertos da CVM para cálculo de **indicadores fundamentalistas** de companhias abertas brasileiras.

Por padrão, calcula 15 indicadores trimestrais dos últimos 5 anos

Segue lista de fórmulas e mapeamento de contas CVM, de cada indicador: [`docs/analise_fundamentalista.md`](docs/analise_fundamentalista.md).

```
Indicadores — 33.000.167/0001-01 - PETROBRAS 
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ dt_refer   ┃ indicador           ┃             valor ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 2021-03-31 │ cobertura_juros     │           -1.0789 │
│ 2021-03-31 │ divida_bruta        │ 404316000000.0000 │
│ 2021-03-31 │ divida_liquida      │ 332862000000.0000 │
│ 2021-03-31 │ divida_liquida_pl   │            1.0394 │
│ 2021-03-31 │ endividamento_geral │           67.9204 │
│ 2021-03-31 │ giro_ativo          │            0.0863 │
│ 2021-03-31 │ liquidez_corrente   │            1.2370 │
│ 2021-03-31 │ liquidez_geral      │            0.3952 │
│ 2021-03-31 │ liquidez_imediata   │            0.5476 │
│ 2021-03-31 │ liquidez_seca       │            0.9178 │
│ 2021-03-31 │ margem_bruta        │           51.0978 │
│ 2021-03-31 │ margem_liquida      │            1.4807 │
│ 2021-03-31 │ margem_operacional  │           39.3437 │
│ 2021-03-31 │ roa                 │            0.1278 │
│ 2021-03-31 │ roe                 │            0.3984 │
| ...        | ...                 | ...               |
│ 2025-09-30 │ roa                 │            6.4346 │
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


### Configuração do Ambiente

Projeto é gerenciado pelo [`UV - https://docs.astral.sh/uv/`](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/dalmofelipe/cvmdata.git
cd cvmdata
uv sync
uv sync --extra dev
```


## Pipeline

O processamento dos dados varia conforme a configuração da maquina. Geralmente é concluído em 10min.

__Configuração padrão__

| Variável | Valor Padrão | Descrição |
|----------|----------------|-----------|
| CVM_DATA_DIR | ./data | Diretório de storage dos dados |
| CVM_YEARS | 2021,2022,2023,2024,2025 | Anos a serem processados. Também aceita range inclusivo como `2021:2025` ou `2021-2025`. |
| CVM_FORCE_DOWNLOAD | false | Forçar download dos documentos |
| CVM_VERBOSE | false | Nível de log detalhado |
| CVM_CNPJ | None | CNPJ da empresa a ser processada. Se None, processa todas as empresas. |


### Entry Point

```bash
# Executa o pipeline completo (configuração padrão)
uv run cvmdata

# Ou equivalente:
uv run python -m cvmdata.pipeline

# Variaveis de ambiente via CLI têm prioridade sobre 'config.py' e '.env'
CVM_YEARS=2020:2026 cvmdata
```


### Exemplo `.env`

Caso necessário, crie um arquivo `.env` na raiz do projeto, com as variáveis de configuração desejadas.

```env
CVM_YEARS=2024
CVM_FORCE_DOWNLOAD=true
CVM_CNPJ=00.000.000/0001-91
```

_O `.env` acima, personaliza a execução para baixar novamente os documentos e reprocessar o ano 2024, somente para os dados do Banco do Brasil._

Para personalizar o pipeline, leia o documento [`docs/pipeline.md`](docs/pipeline.md).


### Scripts

Para consultar indicadores pela CLI

```sh
# Instale dependencias de scripts
uv sync --extra scripts

# Script padrão retorna todos indicadores da PETROBRAS
python scripts/indicators.py

# Indique um CNPJ e/ou ANO especifico. O comando abaixo retorna indicadores de 2026 da VALE S.A.
python scripts/indicators.py --cnpj "33.592.510/0001-54" --year 2026
```


### DBGate

Use o gerenciador de database `DbGate Community` para explorar os dados e indicadores calculados.

Link: [DbGate Community](https://www.dbgate.io/download-community/)
