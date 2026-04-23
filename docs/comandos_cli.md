
---

## Comandos CLI

### `cvmdata download`

Baixa os arquivos ZIP da CVM e extrai os CSVs de BPA, BPP e DRE.

```bash
cvmdata download                     # todos os anos configurados (2021–2025)
cvmdata download --year 2024         # apenas 2024
cvmdata download --year 2024 --force # re-baixa mesmo se ZIP já existir
cvmdata download --verbose           # log detalhado
```

### `cvmdata load`

Ingere os CSVs extraídos nas tabelas raw do DuckDB (idempotente: DELETE + INSERT).

```bash
cvmdata load                         # todos os anos disponíveis em data/raw/
cvmdata load --year 2024             # apenas 2024
cvmdata load --verbose
```

### `cvmdata normalize`

Deduplica (mantém `VERSAO` mais recente), filtra `ORDEM_EXERC = 'ÚLTIMO'` e faz cast de tipos.
Cria tabelas `raw_*_clean` no DuckDB.

```bash
cvmdata normalize
```

### `cvmdata indicators`

Calcula os 15 indicadores fundamentalistas para todos os pares `(cnpj_cia, dt_refer)` e persiste em `indicators`.

```bash
cvmdata indicators                           # todas as empresas
cvmdata indicators --cnpj "00.000.000/0001-91"  # apenas BCO Brasil
```

### `cvmdata query`

Exibe os indicadores calculados em tabela formatada.

```bash
cvmdata query --cnpj "00.000.000/0001-91"        # todos os períodos de uma empresa Ex.: BCO BRASIL S.A.
cvmdata query --cnpj "00.000.000/0001-91" --year 2024  # filtrar por ano
cvmdata query                                    # top-10 empresas com mais indicadores
```

### `cvmdata download-cad`

Baixa os arquivos cadastrais oficiais da CVM para `data/raw/cad/`.

```bash
cvmdata download-cad               # baixa meta + CSV cadastral
cvmdata download-cad --force       # re-baixa mesmo se já existir
```

### `cvmdata load-cad`

Faz recarga total do `cad_cia_aberta.csv` na tabela `cad_cia_aberta_raw` do DuckDB.
Valida paridade de linhas CSV × tabela (SC-001) e registra no log.

```bash
cvmdata load-cad
```

### `cvmdata classify-cad`

Classifica todos os CNPJs com `SIT='ATIVO'` pelo `SETOR_ATIV` e persiste em `company_classification`.
CNPJs mapeados recebem `confidence=high`; ambíguos/vazios/não-mapeados recebem `industrial_default` e `confidence=low`.

```bash
cvmdata classify-cad
```

### `cvmdata query-cad`

Consulta classificação cadastral no DuckDB.

```bash
cvmdata query-cad                              # últimas 20 classificações
cvmdata query-cad --cnpj "00.000.000/0001-91" # detalhe de uma empresa
```

### `Scripts`

`list_companies.py` - Listar as empresas presentes no banco de dados cvmdata.

```bash
uv run scripts/list_companies.py
uv run scripts/list_companies.py --limit 50
uv run scripts/list_companies.py --filter petro
```

