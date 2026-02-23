# Quickstart — Implementação das Correções

**Branch**: `002-p1-refactor-scope-con`

## Status atual

| Item | Arquivo | Status |
|------|---------|--------|
| P1 — scope `_con_` only | `downloader.py`, `loader.py`, `db.py` | ✅ DONE |
| P4 — filtrar ACCOUNT_MAP no load | `loader.py` | ✅ DONE |
| P2-2A — DRE deduplicação YTD | `normalize.py` | ⏳ pendente |
| P2-2B — TTM para contas 3.xx | `indicators.py` | ⏳ pendente |
| P3 — batch query calculate_all | `indicators.py` | ⏳ pendente |

---

## Passo 1 — Corrigir `normalize.py` (P2-2A)

**Arquivo**: `src/cvmdata/transform/normalize.py`

**O que fazer**: Criar dois templates de SQL — um para BPA/BPP (atual) e um para DRE
(novo). O `normalize_table` detecta pelo nome da tabela qual usar.

```python
# SQL para BPA e BPP — sem mudança
_NORMALIZE_BALANCE_SQL = """\
CREATE OR REPLACE TABLE {clean} AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT
        * REPLACE (
            VL_CONTA::DECIMAL(29, 10)         AS VL_CONTA,
            TRY_CAST(TRIM(CD_CVM) AS INTEGER) AS CD_CVM
        ),
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
            ORDER BY VERSAO DESC
        ) AS rn
    FROM {table}
)
WHERE rn = 1
  AND ORDEM_EXERC = 'ÚLTIMO'
"""

# SQL para DRE — duas diferenças:
#   1. ORDER BY DT_INI_EXERC ASC, VERSAO DESC  → garante YTD (DT_INI mais antigo)
#   2. Sem filtro ORDEM_EXERC                  → preserva PENÚLTIMO para TTM
_NORMALIZE_FLOW_SQL = """\
CREATE OR REPLACE TABLE {clean} AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT
        * REPLACE (
            VL_CONTA::DECIMAL(29, 10)         AS VL_CONTA,
            TRY_CAST(TRIM(CD_CVM) AS INTEGER) AS CD_CVM
        ),
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC
            ORDER BY DT_INI_EXERC ASC, VERSAO DESC
        ) AS rn
    FROM {table}
)
WHERE rn = 1
"""
```

**Testes a escrever** (`tests/test_normalize.py`):
- DRE Q2+: fixture com duas linhas mesmo grupo → `raw_dre_clean` retém YTD
- DRE Q1: fixture com uma linha → normalização OK (sem erro)
- DRE: `PENÚLTIMO` sobrevive em `raw_dre_clean`
- BPA/BPP: `PENÚLTIMO` ainda é descartado (comportamento atual mantido)
- Empresa com ano fiscal não-janeiro: linha com `DT_INI_EXERC=2024-04-01` ganha sobre `2024-07-01`

---

## Passo 2 — Implementar TTM em `indicators.py` (P2-2B)

**Arquivo**: `src/cvmdata/transform/indicators.py`

**O que fazer**: Adicionar `_get_dre_value` que retorna o valor correto por metodologia:

```python
# Contas de resultado — usam TTM
DRE_ACCOUNTS = frozenset(ACCOUNT_MAP[k] for k in ACCOUNT_MAP if k.startswith("3."))

def _get_dre_value(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str,
    dt_refer: str,
    cd_conta: str,
) -> float | None:
    """Retorna o valor TTM para uma conta DRE.

    Fórmula: YTD_atual + (FY_anterior - YTD_anterior_mesmo_periodo)
    Fallback: FY_anterior direto se YTD_anterior ausente.
    Fallback final: None se FY_anterior também ausente.
    """
    # YTD atual (ÚLTIMO, DT_INI mínimo)
    ytd_atual = conn.execute("""
        SELECT VL_CONTA FROM raw_dre_clean
        WHERE CNPJ_CIA = ? AND DT_REFER = ? AND CD_CONTA = ? AND ORDEM_EXERC = 'ÚLTIMO'
    """, [cnpj, dt_refer, cd_conta]).fetchone()

    # YTD ano anterior (PENÚLTIMO, DT_INI mínimo)
    ytd_anterior = conn.execute("""
        SELECT VL_CONTA FROM raw_dre_clean
        WHERE CNPJ_CIA = ? AND DT_REFER = ? AND CD_CONTA = ? AND ORDEM_EXERC = 'PENÚLTIMO'
    """, [cnpj, dt_refer, cd_conta]).fetchone()

    # FY anterior — MAX(DT_FIM_EXERC) do DFP antes do DT_REFER
    fy_dt = conn.execute("""
        SELECT MAX(DT_FIM_EXERC) FROM raw_dre_clean
        WHERE CNPJ_CIA = ? AND source = 'dfp' AND DT_FIM_EXERC < ?
    """, [cnpj, dt_refer]).fetchone()

    fy_valor = None
    if fy_dt and fy_dt[0]:
        row = conn.execute("""
            SELECT VL_CONTA FROM raw_dre_clean
            WHERE CNPJ_CIA = ? AND DT_FIM_EXERC = ? AND CD_CONTA = ? AND ORDEM_EXERC = 'ÚLTIMO'
        """, [cnpj, str(fy_dt[0]), cd_conta]).fetchone()
        fy_valor = float(row[0]) if row and row[0] is not None else None

    if ytd_atual is None or ytd_atual[0] is None:
        return fy_valor  # fallback: sem ITR recente

    ytd_v = float(ytd_atual[0])

    if fy_valor is None:
        return ytd_v  # fallback: sem DFP anterior

    if ytd_anterior is None or ytd_anterior[0] is None:
        return fy_valor  # fallback: sem PENÚLTIMO

    ytd_a = float(ytd_anterior[0])
    return ytd_v + (fy_valor - ytd_a)
```

**Nota**: Esta implementação ainda faz múltiplas queries por conta (problema P3).
P3 refatora isso para batch. Implementar P2-2B em estilo simples primeiro — P3 otimiza depois.

**Testes a escrever** (`tests/test_indicators.py`):
- TTM completo: YTD=369, FY=494, YTD_ant=377 → TTM=486
- Fallback sem PENÚLTIMO: retorna FY direto
- Fallback sem DFP: retorna YTD
- Fallback sem ITR: retorna FY
- Denominador zero em indicador de resultado com TTM → None (não erro)

---

## Passo 3 — Batch query em `calculate_all` (P3)

**Arquivo**: `src/cvmdata/transform/indicators.py`

**O que fazer**: Substituir o loop por uma única query que traz todos os dados de balanço
de uma vez. Contas DRE continuam sendo tratadas pelo caminho TTM individualmente por ora,
ou podem ser incluídas no batch com a janela de `MIN(DT_INI_EXERC)` se P2-2A estiver pronto
(nesse caso a deduplicação já está na tabela).

```python
def _fetch_all_balance_components(
    conn: duckdb.DuckDBPyConnection,
    cnpj: str | None = None,
) -> dict[tuple[str, str], dict[str, float | None]]:
    """Retorna {(cnpj, dt_refer): {componente: valor}} para contas de balanço."""
    filter_sql = "WHERE CNPJ_CIA = ?" if cnpj else ""
    params = [cnpj] if cnpj else []

    rows = conn.execute(f"""
        SELECT CNPJ_CIA, DT_REFER::VARCHAR, CD_CONTA, VL_CONTA
        FROM (
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpa_clean
            UNION ALL
            SELECT CNPJ_CIA, DT_REFER, CD_CONTA, VL_CONTA FROM raw_bpp_clean
        )
        {filter_sql}
        ORDER BY CNPJ_CIA, DT_REFER
    """, params).fetchall()

    result: dict[tuple[str, str], dict[str, float | None]] = {}
    for cnpj_cia, dt_refer, cd_conta, vl_conta in rows:
        key = (cnpj_cia, dt_refer)
        if key not in result:
            result[key] = {}
        name = get_component(cd_conta)
        if name:
            result[key][name] = float(vl_conta) if vl_conta is not None else None
    return result
```

**Testes a escrever**:
- `_fetch_all_balance_components` retorna dict com todas as empresas/períodos sem loop
- Com `cnpj=None`: retorna todas as empresas
- Com `cnpj=X`: retorna apenas empresa X

---

## Ordem de execução após implementação

```bash
# 1. Verificar testes passando
uv run pytest tests/ -v

# 2. Recarregar dados (necessário para re-normalizar com SQL correto)
uv run cvmdata load --year 2024
uv run cvmdata normalize

# 3. Calcular indicadores com TTM
uv run cvmdata indicators

# 4. Verificar resultado Petrobras Q3/2024
uv run cvmdata query --cnpj "33.000.167/0001-01"
# ROE/ROA devem ser ~2-3× maiores do que antes (YTD parcial → TTM anualizado)
```

## Validação cruzada

Comparar `margem_liquida` de Petrobras Q3/2024 com Status Invest / Investidor10.
Divergência esperada antes: ~3× subavaliada. Após TTM: deve convergir para ~±5%.
