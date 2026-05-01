
---

## Comandos CLI

### `cvmdata pipeline run`

Executa o pipeline completo (financeiro + cadastral) de forma orquestrada.

```bash
cvmdata pipeline run

cvmdata pipeline run --years 2024
cvmdata pipeline run --years 2021:2025
cvmdata pipeline run --years 2021,2022,2024

cvmdata pipeline run --force-download
cvmdata pipeline run --verbose
```

### `cvmdata indicators`

Consulta indicadores calculados (tabela `indicators`) para um CNPJ.

```bash
cvmdata indicators --cnpj "00.000.000/0001-91"
cvmdata indicators --cnpj "00.000.000/0001-91" --year 2024
```

### `cvmdata info-cad`

Consulta classificação cadastral (tabela `company_classification`).
O `--page-size` aceita valores entre 20 e 1000.

```bash
cvmdata info-cad
cvmdata info-cad --page 2
cvmdata info-cad --page-size 50
cvmdata info-cad --page 2 --page-size 50
cvmdata info-cad --page-size 1000
cvmdata info-cad --cnpj "00.000.000/0001-91"
```

### `Scripts`

`list_companies.py` - Listar as empresas presentes no banco de dados cvmdata.

```bash
uv run scripts/list_companies.py
uv run scripts/list_companies.py --limit 50
uv run scripts/list_companies.py --filter petro
```

