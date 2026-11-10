## Metodologias implementadas


### Point-in-Time (PiT)

Calcula cada indicador usando exclusivamente os valores do `DT_REFER` solicitado.
Não há lookback — é uma foto dos fundamentos naquele momento.

- **Balanço (1.xx/2.xx):** snapshot do `DT_REFER`
- **Resultado (3.xx):** valor acumulado YTD do `DT_REFER` (pode ser sub-anual em ITRs)

Uso: backtesting, auditoria histórica, modelos quantitativos.


### Trailing Twelve Months (TTM)

Acumula os resultados dos últimos 12 meses encerrados, independentemente do ano fiscal.
Bancos as contas de fluxo ficam anualizadas. Balanço continua em snapshot.

- **Balanço (1.xx/2.xx):** snapshot do `DT_REFER` mais recente — **idêntico ao PiT**
- **Resultado (3.xx):** calculado pela fórmula abaixo

**Fórmula TTM para contas de resultado:**
```
TTM = YTD_atual + (FY_ano_anterior − YTD_mesmo_periodo_ano_anterior)
```

| Variável | Significado | Origem no banco |
|---|---|---|
| **YTD atual** | Valor acumulado do ano corrente até o período mais recente disponível (ex: jan–set) | `ORDEM_EXERC = 'ÚLTIMO'`, mesmo `DT_REFER` do período sendo calculado |
| **YTD anterior** (penúltimo) | Valor acumulado do mesmo intervalo (jan–set), mas do ano anterior — serve pra "descontar" a sobreposição | `ORDEM_EXERC = 'PENÚLTIMO'`, mesmo `DT_REFER` |
| **FY anterior** | Valor do ano fiscal completo anterior (jan–dez) | `ORDEM_EXERC = 'ÚLTIMO'` da linha DFP (`source = 'dfp'`) mais recente com `DT_FIM_EXERC` < `DT_REFER` do período atual |


**Exemplo — Petrobras Q3/2024 (`3.01` Receita Líquida):**
```
YTD_atual          = 369.561M  (ÚLTIMO,    DT_INI=2024-01-01, DT_FIM=2024-09-30)
FY_2023            = 511.994M  (DFP 2023,  DT_INI=2023-01-01, DT_FIM=2023-12-31)
YTD_2023_9m        = 377.736M  (PENÚLTIMO, DT_INI=2023-01-01, DT_FIM=2023-09-30)

TTM = 369.561 + (511.994 − 377.736) = 503.819M
```

_A lógica: pega o ano fiscal fechado anterior inteiro, tira o pedaço equivalente ao trecho já coberto pelo YTD atual (pra não contar duas vezes), e soma o que já foi realizado no ano corrente. Resultado: uma janela móvel de 12 meses._

**Fallback (quando faltam dados)**

```
sem YTD_atual            → retorna FY_anterior (se existir), senão None
sem FY_anterior          → retorna YTD_atual (proxy parcial)
sem YTD_anterior         → retorna FY_anterior (proxy sem ajuste)
todos presentes          → aplica a fórmula completa
```
