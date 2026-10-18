# cvmdata

**cvmdata** é um motor de dados para análise fundamentalista de empresas brasileiras de capital aberto. Ele automatiza todo o pipeline de dados públicos da CVM — desde o download e extração dos arquivos ITR e DFP até a normalização das demonstrações financeiras e o cálculo dos indicadores.

O motor trata as diferenças nos planos de contas entre setores, permitindo calcular **18 indicadores fundamentalistas trimestrais** de forma padronizada. O histórico é parametrizável desde **2011**; por padrão, o processamento considera os últimos **5 anos**.

Os resultados são consolidados em **DuckDB**, totalizando aproximadamente **200 mil a 450 mil indicadores**, dependendo do período e da cobertura processada.

```
$ python scripts/indicators.py 

  Indicadores — 33.000.167/0001-01 — PETROBRAS (PETR)   
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ dt_refer   ┃ indicador           ┃             valor ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 2011-03-31 │ capital_giro        │  59446049000.0000 │
│ 2011-03-31 │ cobertura_juros     │          -17.8491 │
│ 2011-03-31 │ divida_bruta        │ 128999907000.0000 │
│ ...        │ ...                 │ ...               │
│ 2026-06-30 │ capital_giro        │ -26401000000.0000 │
│ 2026-06-30 │ cobertura_juros     │          -14.1391 │
│ 2026-06-30 │ divida_bruta        │ 366533000000.0000 │
│ 2026-06-30 │ divida_liquida      │ 312769000000.0000 │
│ 2026-06-30 │ divida_liquida_pl   │            0.6491 │
│ 2026-06-30 │ endividamento_geral │           62.3263 │
│ 2026-06-30 │ endividamento_pl    │          165.4370 │
│ 2026-06-30 │ giro_ativo          │            0.4288 │
│ 2026-06-30 │ liquidez_corrente   │            0.8544 │
│ 2026-06-30 │ liquidez_geral      │            0.3766 │
│ 2026-06-30 │ liquidez_imediata   │            0.1850 │
│ 2026-06-30 │ liquidez_seca       │            0.5771 │
│ 2026-06-30 │ margem_bruta        │           50.5954 │
│ 2026-06-30 │ margem_ebit         │           33.8648 │
│ 2026-06-30 │ margem_liquida      │           24.3861 │
│ 2026-06-30 │ roa                 │           10.4577 │
│ 2026-06-30 │ roe                 │           27.7586 │
│ 2026-06-30 │ roic                │           16.1892 │
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
- Linux (Recomendado)

<br>

```bash
git clone https://github.com/dalmofelipe/cvmdata.git
cd cvmdata
uv sync
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
# Importante: execute um dos comandos no diretório raiz do projeto
cvmdata

# Ou
uv run cvmdata
```

O tempo para concluir o pipeline pode variar entre 3 e 10 minutos. Essa variação depende da configuração da máquina utilizada, velocidade de internet e da personalização do pipeline.


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


## Scripts

Todos scripts estão localizados na pasta `scripts/` e podem ser executados diretamente pelo terminal.

Caso o arquivo do database estiver em uso serão exibidos erros de acesso. Feche o DbGate ou qualquer outro programa que esteja utilizando o arquivo `cvmdata.duckdb` antes de executar os scripts.

### `indicators.py`

Consulta rápida aos indicadores pelo terminal

```sh
# Instale dependencias de scripts
uv sync --extras scripts

# por padrão retorna todos indicadores da PETROBRAS
python scripts/indicators.py

# Filtre pelo código CVM da empresa
python scripts/indicators.py --cod_cvm "200"

# Filtre pelo ticker
python scripts/indicators.py --ticker "petr"

# Combine e filtre por CNPJ, ticker e/ou ANO especifico.
python scripts/indicators.py --cnpj "33.592.510/0001-54" --year 2026
python scripts/indicators.py --ticker "PETR" --year 2024

# Busque pela denominação comercial (mínimo 4 caracteres).
# Quando a busca retorna mais de uma empresa, será exibida 
# uma tabela com as informações de cada uma delas.
python scripts/indicators.py --name "BRASIL"
```

### `report.py`

Compara indicadores do cvmdata com plataformas externas exibindo devios conforme a tolerância configurada.

```sh
uv sync --extras scripts

python scripts/report.py
```

Exibe um gera um relatório `report.csv` na raiz da pasta scripts/.


## DBGate

Recomendo o uso do `DbGate Community` para explorar o banco de dados DuckDB gerado.

Link: [DbGate Community](https://www.dbgate.io/download-community/)
