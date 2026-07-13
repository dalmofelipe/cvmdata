# cvmdata

Pipeline de dados CVM para cálculo de **indicadores de análise fundamentalista** de companhias abertas brasileiras. 

- Baixa documentos CSVs (ITR, DFP) da base de dados abertos da CVM
- São carregados em base dados OLAD DuckDB
- CONTAS_CVM são selecionadas e aplicadas aos calculos dos indicadores fundamentalistas.
- Por padrão, serão processados dados dos ultimos 5 anos de todas empresas contidas nos documentos.
- Atualmente, são calculados 15 indicadores de cada trimestre. 

Segue lista de fórmulas e mapeamento de contas CVM, de cada indicador: [`docs/analise_fundamentalista.md`](docs/analise_fundamentalista.md).


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
| CVM_YEARS | 2021,2022,2023,2024,2025 | Anos a serem processados |
| CVM_FORCE_DOWNLOAD | false | Forçar download dos documentos |
| CVM_VERBOSE | false | Nível de log detalhado |
| CVM_CNPJ | None | CNPJ da empresa a ser processada. Se None, processa todas as empresas. |


### Entry Point

```bash
# Executa o pipeline completo (configurado via .env ou env vars)
uv run cvmdata

# Ou equivalente:
uv run python -m cvmdata.pipeline
```


### Exemplo `.env`

Caso necessário, crie um arquivo `.env` na raiz do projeto, com as variáveis de configuração desejadas.

```env
CVM_YEARS=2024
CVM_FORCE_DOWNLOAD=true
# CVM_CNPJ=00.000.000/0001-91
```

_O `.env` acima, personaliza a execução para baixar novamente os documentos e reprocessar o ano 2024, somente para os dados do Banco do Brasil._

Para personalizar o pipeline, leia o documento [`docs/pipeline.md`](docs/pipeline.md).


### DBGate

Use o gerenciador de database `DbGate Community` para explorar os dados e indicadores calculados.

Link: [DbGate Community](https://www.dbgate.io/download-community/)
