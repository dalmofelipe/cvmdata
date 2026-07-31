# cvmdata

Pipeline para processamento dos dados abertos da CVM, desenvolvido para calcular indicadores fundamentalistas de empresas brasileiras de capital aberto. Por padrão, processa os últimos cinco anos de demonstrações financeiras e gera 15 indicadores fundamentalistas trimestrais para todas as empresas disponíveis na base de dados da CVM.

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

Segue lista de fórmulas e mapeamento de contas CVM, de cada indicador: [docs/analise_fundamentalista.md](docs/analise_fundamentalista.md).


### Features

- Download automático dos dados públicos da CVM (ITR e DFP)
- Suporte ao processamento de uma única empresa (CNPJ)
- Integração com dados da B3, quando disponíveis
- Configuração via variáveis de ambiente


## Configuração do Ambiente

### Requisitos

- UV: [https://docs.astral.sh/uv](https://docs.astral.sh/uv/)
- Python 3.12+
- Linux (extremamente recomendado)

<br>

```bash
git clone https://github.com/dalmofelipe/cvmdata.git

cd cvmdata

uv sync

uv sync --extra dev # apenas para desenvolvimento
```


## Pipeline

Ative o ambiente virtual Python, criado pelo UV

```bash
# Linux
source .venv/bin/activate

# Windows (powershell / cmd)
.venv/Scripts/activate
```

Execute o pipeline completo (configuração padrão)

```sh
# Importante: execute o comando no diretório raiz do projeto
cvmdata

# Ou
uv run cvmdata
```

O tempo para concluir o pipeline pode variar entre 3 e 10 minutos. Essa variação depende da configuração da máquina utilizada e da personalização do pipeline.


### Personalizando o pipeline

É possível modificar o comportamento do pipeline por meio de variáveis de ambiente.

```sh
# Variáveis de ambiente via terminal têm prioridade sobre 'config.py' e '.env'
CVM_YEARS=2020:2026 cvmdata

CVM_YEARS=2024 CVM_FORCE_DOWNLOAD=true CVM_CNPJ=00.000.000/0001-91 cvmdata

# Windows (powershell)
$env:CVM_YEARS="2020:2026"; cvmdata

# Windows (cmd)
set CVM_YEARS=2020:2026 && cvmdata
```

Também é possível configurar via arquivo `.env` na raiz do projeto, com as variáveis de configuração desejadas, por exemplo:

```
CVM_YEARS=2024
CVM_FORCE_DOWNLOAD=true
CVM_CNPJ=00.000.000/0001-91
```

_O `.env` acima, personaliza o pipeline para baixar novamente os documentos e recalcular os indicadores de 2024 do Banco do Brasil._

Lista completa de variáveis em: [docs/pipeline.md](docs/pipeline.md)


### Scripts

`indicators.py`: consulta rápida aos indicadores pelo terminal

```sh
# Instale dependencias de scripts
uv sync --extras scripts

# por padrão retorna todos indicadores da PETROBRAS
python scripts/indicators.py

# Filtre por CNPJ e/ou ANO especifico.
# O comando abaixo retorna os indicadores de 2026 da VALE S.A.
python scripts/indicators.py --cnpj "33.592.510/0001-54" --year 2026

# Filtre pelo código CVM da empresa
python scripts/indicators.py --cod_cvm "200"

# Filtre pelo ticker (4 letras maiúsculas)
python scripts/indicators.py --ticker "PETR"

# Busque pela denominação comercial (mínimo 4 caracteres).
# Quando a busca retorna mais de uma empresa, uma tabela
# de seleção é exibida com CNPJ, COD_CVM, TICKER e NOME.
python scripts/indicators.py --name "BRASIL"

# Os filtros podem ser combinados (AND)
python scripts/indicators.py --ticker "PETR" --year 2024
```


### DBGate

O banco de dados DuckDB gerado, pode ser explorado utilizando o `DbGate Community`.

Link: [DbGate Community](https://www.dbgate.io/download-community/)
