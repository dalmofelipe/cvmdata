# Metodologias de Análise Fundamentalista

## Diagnóstico do código atual

O pipeline calcula **Point-in-Time Snapshot (PiT)** por padrão.  
Cada indicador é calculado de forma independente e estática para um único par `(CNPJ_CIA, DT_REFER)` — sem lookback, sem janela deslizante, sem acumulação entre períodos.

Evidências no código:

- `calculate_all()` itera sobre pares `(CNPJ_CIA, DT_REFER)` em isolamento.
- `_extract_components()` filtra com `WHERE CNPJ_CIA = ? AND DT_REFER = ?` — exatamente um período.
- `normalize.py` descarta `ORDEM_EXERC != 'ÚLTIMO'`, mantendo apenas o dado definitivo para aquele trimestre.

> **Impacto no TTM:** o descarte de `PENÚLTIMO` bloqueia a fórmula TTM, que necessita
> do YTD do mesmo período do ano anterior (`PENÚLTIMO`). O normalize da DRE precisará
> ser ajustado para preservar as linhas `PENÚLTIMO` antes de implementar TTM.

Bugs adicionais identificados que afetam ambas as metodologias:

- **Bug DRE (P2-2A):** a deduplicação atual não distingue linha YTD da trimestral — ambas têm o mesmo `VERSAO` dentro do mesmo `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)`, resultando em seleção não-determinística. Corrigido com `ORDER BY DT_INI_EXERC ASC` (linha YTD sempre tem menor `DT_INI_EXERC`).
- **Calendário fiscal variável:** o `DT_REFER` não é fixo em março/junho/setembro — reflete o trimestre relativo ao ano fiscal de cada empresa. Qualquer lógica de filtro por mês fixo (ex.: `MONTH(DT_INI_EXERC) = 1`) está **incorreta** para empresas com ano fiscal não-janeiro.

---

## Point-in-Time (PiT)

### O que é

Registra exatamente o que o mercado sabia em determinada data, na forma de uma "foto" (snapshot) dos fundamentos públicos. Ao contrário de bases que atualizam retroativamente quando a empresa republica um balanço, o PiT preserva o estado original do dado no momento em que foi divulgado.

### Por que é válido

- **Sem viés de antecipação**: evita analisar o passado com informações reveladas meses depois (ex.: republicações de balanços pelo RI).
- **Fidelidade histórica**: simula com precisão o que o investidor sabia naquela data.
- **Padrão-ouro em quant**: essencial para backtesting e modelos quantitativos confiáveis.

### Casos de uso

| Uso | Descrição |
|-----|-----------|
| Backtesting | Testa estratégias históricas sem usar lucros revisados posteriormente |
| Modelagem preditiva | Garante fiabilidade em algoritmos de seleção de ações |
| Avaliação de risco/crédito | Calcula Probabilidade de Default em cenários econômicos específicos |
| Auditoria de decisões | Reconstrói a "foto" dos fundamentos disponíveis em uma data passada |

### Limitação no código atual

`DT_REFER` é a data de **competência** do demonstrativo (ex.: `2024-12-31`), não a data de divulgação. Se uma empresa republicar um balanço, o `INSERT OR REPLACE` atual substitui o dado silenciosamente. Para PiT rigoroso, seria necessário:

1. Adicionar coluna `dt_ingestao TIMESTAMP DEFAULT NOW()` na tabela `indicators`.
2. Substituir `INSERT OR REPLACE` por `INSERT` puro, preservando o histórico de versões.

---

## Trailing Twelve Months (TTM)

### O que é

Soma os valores de fluxo (DRE) dos últimos 12 meses encerrados, independentemente de estarem no mesmo ano fiscal. Contas de estoque (BPA/BPP) continuam usando o snapshot mais recente.

### Regra por tipo de conta

| Tipo | PiT | TTM |
|------|-----|-----|
| **BPA/BPP** (estoque) | Snapshot do `DT_REFER` | Snapshot mais recente — **igual ao PiT** |
| **DRE** (fluxo) | Valor YTD do `DT_REFER` | `YTD_atual + (FY_anterior − YTD_anterior_mesmo_periodo)` |

### Fórmula TTM (contas `3.xx`)

A CVM armazena valores acumulados YTD — não trimestres isolados — nas linhas `ÚLTIMO` e
`PENÚLTIMO`. A construção correta do TTM usa esses acumulados:

```
TTM = YTD_atual + (FY_ano_anterior − YTD_mesmo_periodo_ano_anterior)
```

| Variável | `ORDEM_EXERC` | Fonte | Identificação |
|---|---|---|---|
| `YTD_atual` | `ÚLTIMO` | ITR do `DT_REFER` corrente | `DT_INI_EXERC` menor do grupo |
| `FY_ano_anterior` | `ÚLTIMO` | DFP do exercício anterior | `DT_INI_EXERC` menor do grupo |
| `YTD_mesmo_periodo_ano_anterior` | `PENÚLTIMO` | mesmo arquivo ITR | `DT_INI_EXERC` menor do grupo |

O `DT_INI_EXERC` mais antigo dentro de um grupo `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)`
identifica a linha YTD independentemente do mês de início do exercício fiscal da empresa.

### Pré-requisitos

1. **ITR + DFP carregados** (`data/raw/itr/` e `data/raw/dfp/`) — ambos necessários. Sem DFP não há `FY_ano_anterior`; sem ITR não há `YTD_atual` trimestral.
2. **`PENÚLTIMO` preservado na DRE normalizada** — o filtro atual `ORDEM_EXERC = 'ÚLTIMO'` em `normalize.py` descarta o dado necessário para `YTD_mesmo_periodo_ano_anterior`. Ajuste obrigatório antes da implementação TTM.
3. **Bug P2-2A corrigido** — deduplicação por `DT_INI_EXERC ASC` garantindo que cada `DT_REFER` tenha exatamente uma linha YTD por conta e `ORDEM_EXERC`.

### Casos de uso

| Uso | Descrição |
|-----|-----------|
| Screening atual | "Quais empresas têm ROE > X hoje?" — usa o resultado acumulado real dos últimos 12 meses |
| Valuation | P/L, EV/EBITDA — múltiplos calculados sobre lucro/EBITDA dos últimos 12 meses |
| Comparação entre empresas | Normaliza empresas com anos fiscais diferentes |

---

## Implementação planejada

As funções puras de cálculo (`indicators.py`) **não mudam** — elas recebem apenas floats. O que muda é a normalização, a extração dos componentes e o schema de armazenamento.

### 1. Pré-condição: corrigir `normalize.py` para DRE

Duas mudanças obrigatórias na SQL de normalização da DRE antes de implementar TTM:

```sql
-- Correção A: deduplicação por DT_INI_EXERC ASC (mantém YTD, descarta trimestral isolado)
-- Correção B: preservar PENÚLTIMO (necessário para YTD_anterior no TTM)
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
            ORDER BY DT_INI_EXERC ASC, VERSAO DESC  -- ← YTD tem menor DT_INI_EXERC
        ) AS rn
    FROM {table}
)
WHERE rn = 1
  AND ORDEM_EXERC IN ('ÚLTIMO', 'PENÚLTIMO')  -- ← preserva ambos para TTM
```

> BPA/BPP não têm `DT_INI_EXERC` — para essas tabelas continua `ORDER BY VERSAO DESC`
> e `ORDEM_EXERC = 'ÚLTIMO'`. A lógica de normalização precisa bifurcar por tipo de tabela.

### 2. Schema — coluna `methodology` em `indicators`

```python
# db.py
_INDICATORS_DDL = """\
CREATE TABLE IF NOT EXISTS indicators (
    cnpj_cia    VARCHAR NOT NULL,
    dt_refer    DATE    NOT NULL,
    indicador   VARCHAR NOT NULL,
    methodology VARCHAR NOT NULL DEFAULT 'pit',
    valor       DOUBLE,
    PRIMARY KEY (cnpj_cia, dt_refer, indicador, methodology)
);"""
```

### 3. Extração PiT (comportamento atual, sem mudança lógica)

```python
def _extract_components_pit(conn, cnpj, dt_refer):
    """Balanço + DRE YTD do DT_REFER exato. ORDEM_EXERC = 'ÚLTIMO' apenas."""
    rows = conn.execute("""
        SELECT CD_CONTA, VL_CONTA
        FROM (
            SELECT CD_CONTA, VL_CONTA FROM raw_bpa_clean
             WHERE CNPJ_CIA = ? AND DT_REFER = ?
            UNION ALL
            SELECT CD_CONTA, VL_CONTA FROM raw_bpp_clean
             WHERE CNPJ_CIA = ? AND DT_REFER = ?
            UNION ALL
            SELECT CD_CONTA, VL_CONTA FROM raw_dre_clean
             WHERE CNPJ_CIA = ? AND DT_REFER = ? AND ORDEM_EXERC = 'ÚLTIMO'
        )
        WHERE CD_CONTA IN (<ACCOUNT_MAP keys>)
    """, [cnpj, dt_refer] * 3).fetchall()
    ...
```

### 4. Extração TTM

```python
def _extract_components_ttm(conn, cnpj, dt_refer):
    """
    Balanço:  snapshot do dt_refer (igual ao PiT).
    DRE TTM:  YTD_atual + (FY_anterior - YTD_anterior_mesmo_periodo)
              usando PENÚLTIMO do mesmo ITR para YTD_anterior.
    """
    # Balanço — idêntico ao PiT
    comp = _extract_components_balance(conn, cnpj, dt_refer)

    # DRE — coleta YTD_atual (ÚLTIMO) e YTD_anterior (PENÚLTIMO) do mesmo DT_REFER
    dre_rows = conn.execute("""
        SELECT CD_CONTA, ORDEM_EXERC, VL_CONTA
        FROM raw_dre_clean
        WHERE CNPJ_CIA = ? AND DT_REFER = ?
          AND ORDEM_EXERC IN ('ÚLTIMO', 'PENÚLTIMO')
          AND CD_CONTA IN (<ACCOUNT_MAP DRE keys>)
    """, [cnpj, dt_refer]).fetchall()

    ytd_atual   = {cd: vl for cd, orex, vl in dre_rows if orex == 'ÚLTIMO'}
    ytd_ant     = {cd: vl for cd, orex, vl in dre_rows if orex == 'PENÚLTIMO'}

    # FY do exercício anterior: DFP com DT_FIM_EXERC imediatamente anterior ao DT_REFER
    fy_anterior = _extract_fy_anterior(conn, cnpj, dt_refer)

    # Aplica fórmula TTM por conta
    for cd_conta in ytd_atual:
        ytd = ytd_atual.get(cd_conta)
        fy  = fy_anterior.get(cd_conta)
        ant = ytd_ant.get(cd_conta)
        if None not in (ytd, fy, ant):
            name = get_component(cd_conta)
            if name:
                comp[name] = ytd + fy - ant
        elif ytd is not None and fy is not None and ant is None:
            # Fallback: Q1 sem PENÚLTIMO (YTD = trimestre = ano para empresas com 1 tri)
            name = get_component(cd_conta)
            if name:
                comp[name] = ytd  # ou fy como proxy
    return comp


def _extract_fy_anterior(conn, cnpj, dt_refer):
    """Busca o DFP do exercício anterior ao DT_REFER. Agnóstico ao mês fiscal."""
    rows = conn.execute("""
        SELECT CD_CONTA, VL_CONTA
        FROM raw_dre_clean
        WHERE CNPJ_CIA = ?
          AND source = 'dfp'
          AND ORDEM_EXERC = 'ÚLTIMO'
          AND DT_FIM_EXERC = (
              SELECT MAX(DT_FIM_EXERC)
              FROM raw_dre_clean
              WHERE CNPJ_CIA = ? AND source = 'dfp'
                AND DT_FIM_EXERC < ?
          )
          AND CD_CONTA IN (<ACCOUNT_MAP DRE keys>)
    """, [cnpj, cnpj, dt_refer]).fetchall()
    return {cd: float(vl) for cd, vl in rows if vl is not None}
```

### 5. `calculate_all()` com parâmetro `methodology`

```python
def calculate_all(conn, cnpj=None, methodology: str = "pit") -> int:
    extract_fn = _extract_components_pit if methodology == "pit" else _extract_components_ttm
    ...
    for cnpj_cia, dt_refer in pairs:
        comp = extract_fn(conn, cnpj_cia, dt_refer)
        _upsert_indicators(conn, cnpj_cia, dt_refer, comp, methodology)
```

### 6. CLI — flag `--methodology`

```
uv run cvmdata calculate --methodology ttm
uv run cvmdata calculate --methodology pit   # padrão atual
```

---

## Resumo de uso

| Objetivo | Metodologia recomendada |
|----------|------------------------|
| Validar se sua estratégia funciona ao longo do tempo | **PiT** |
| Decidir o que comprar hoje (screening) | **TTM** |
| Backtesting quantitativo rigoroso | **PiT** (com `dt_ingestao`) |
| Valuation / múltiplos de mercado | **TTM** |
| Auditoria de decisões passadas | **PiT** |
