# Banking Profile

## Objetivo
Documentar a analise dos codigos CVM usados por bancos e explicar por que o `ACCOUNT_MAP` orientado a perfil industrial gerava indicadores nulos (ou errados) para instituicoes financeiras.

O perfil `banking` esta implementado. As secoes "Proposta" e " proximos passos" sao o registro do raciocinio que levou a ele; o estado atual esta em [setor_profile.md](setor_profile.md).

## Fontes analisadas
- `src/cvmdata/transform/account_map.py`
- `tests/integration/test_indicators.py`
- `tests/fixtures/sample_bank_bpa.csv`
- `tests/fixtures/sample_bank_bpp.csv`
- `tests/fixtures/sample_bank_dre.csv`
- `data/raw/itr/2025/itr_cia_aberta_BPA_con_2025.csv` (CNPJ `60.872.504/0001-23`)
- `data/raw/itr/2025/itr_cia_aberta_BPP_con_2025.csv` (CNPJ `60.872.504/0001-23`)
- `data/raw/itr/2025/itr_cia_aberta_DRE_con_2025.csv` (CNPJ `60.872.504/0001-23`)

## Resumo executivo
- O mapa atual assume contas industriais para divida (`2.01.04`, `2.02.01`) e lucro liquido (`3.11`).
- Em bancos, essas contas podem nao existir, ou ter semantica diferente.
- Evidencia real (Itau 2025 ITR) mostra ausencia de:
  - `1.01.01` (caixa)
  - `1.01.02` (aplicacoes financeiras)
  - `1.01.04` (estoques)
  - `2.01.04` (emprestimos CP)
  - `2.02.01` (emprestimos LP)
  - `3.11` (lucro liquido)
- Com isso, indicadores dependentes ficam `None` com a estrategia atual.

## Logica do perfil default (o problema)
O `ACCOUNT_MAP` do perfil `default` usa a seguinte logica:
- `divida_bruta = 2.01.04 + 2.02.01`
- `divida_liquida = divida_bruta - 1.01.01 - 1.01.02`
- `liquidez_seca = (1.01 - 1.01.04) / 2.01`
- `roe = 3.11 / 2.03`

Ja existe anotacao explicita em `account_map.py` indicando necessidade de `sector_profile` para bancos.

## Evidencias de testes
Os indicadores sem equivalente honesto no layout bancario ficam `None` de
propósito, e o teste fixa esse comportamento:
- `test_bank_sector_liquidez_seca_is_none` — banco nao reporta `1.01.04` (estoques).
- `test_bank_sector_divida_bruta_is_none` — banco nao reporta `2.01.04` (emprestimos).

A distinção importa: `None` porque a conta nao existe e nao tem substituto
honesto é diferente de `None` por bug de ingestao.

## Evidencias de dados (fixtures bancarios)
No fixture `sample_bank_*` (BCO Brasil):
- BPA contem `1`, `1.01`, `1.01.01`, `1.01.02`, `1.02`, `1.02.01`.
- BPP contem `2`, `2.01`, `2.02`, `2.02.01`, `2.03`.
- DRE contem `3.01`, `3.03`, `3.05`, `3.06.02`, `3.11`.

Observacao: o fixture ajuda na reproducao de pipeline, mas nao cobre toda variacao de codigos que aparece em bancos reais no ITR.

## Evidencias de dados reais (Itau, ITR 2025)
CNPJ analisado: `60.872.504/0001-23`.

Cobertura dos codigos industriais no ITR 2025:

### BPA
- Presente: `1`, `1.01`, `1.02`, `1.02.01`
- Ausente: `1.01.01`, `1.01.02`, `1.01.04`

Exemplos de semantica observada:
- `1.01` -> `Caixa e Equivalentes de Caixa`
- `1.02` -> `Ativos Financeiros`
- `1.02.01` -> `Ativos Financeiros Avaliados a Valor Justo atraves do Resultado`

### BPP
- Presente: `2`, `2.01`, `2.02`, `2.03`
- Ausente: `2.01.04`, `2.02.01`

Exemplos de semantica observada:
- `2.01` -> `Passivos Financeiros ao Valor Justo atraves do Resultado`
- `2.02` -> `Outros Passivos Financeiros Designados ao Valor Justo atraves do Resultado`
- `2.03` -> `Passivos Financeiros ao Custo Amortizado`

### DRE
- Presente: `3.01`, `3.03`, `3.05`, `3.06.02`
- Ausente: `3.11`
- Conta observada para lucro consolidado: `3.09` -> `Lucro/Prejuizo Consolidado do Periodo`

## Impacto por indicador
Indicadores com maior risco de `None` no perfil bancario atual:
- `divida_bruta` (depende de `2.01.04` + `2.02.01`)
- `divida_liquida` (depende de divida_bruta e de `1.01.01` + `1.01.02`)
- `divida_liquida_pl` (efeito cascata de `divida_liquida`)
- `liquidez_seca` (depende de `1.01.04`)
- `roe` e `roa` quando `3.11` nao existe no DRE do banco

Indicadores com chance maior de continuar calculaveis:
- `liquidez_corrente` (`1.01` / `2.01`)
- `liquidez_geral` (`(1.01 + 1.02.01) / (2.01 + 2.02)`)
- `endividamento_geral` (`(2.01 + 2.02) / 1`)

## Mapeamento do perfil `banking` (implementado)
Abaixo, proposta inicial de correspondencia por componente semantico.

- `ativo_total` -> `1`
- `ativo_circulante` -> `1.01`
- `caixa_equivalentes` -> priorizar `1.01`; fallback `1.01.01` quando existir
- `aplicacoes_financeiras` -> ausente como categoria estavel em varios bancos; avaliar uso de subcontas de `1.02` com regra explicita por setor
- `estoques` -> nao aplicavel (politica de indicador deve tratar)
- `passivo_total` -> `2`
- `passivo_circulante` -> `2.01`
- `emprestimos_cp` -> substituir por agregado financeiro de curto prazo do perfil bancario (nao `2.01.04`)
- `passivo_nao_circulante` -> `2.02`
- `emprestimos_lp` -> substituir por agregado financeiro de longo prazo do perfil bancario (nao `2.02.01`)
- `patrimonio_liquido` -> **nao mapeado por codigo**; resolvido por rotulo
  (`resolve_pl`). `2.03` significa PL no layout padrao, mas "Provisoes" em 19
  bancos e "Passivos Financeiros ao Custo Amortizado" em 16; o PL no financeiro
  fica em `2.07` ou `2.08` conforme o ano. Ver [setor_profile.md](setor_profile.md)
- `receita_liquida` -> `3.01`
- `resultado_bruto` -> `3.03`
- `ebit` -> `3.05`
- `despesas_financeiras` -> revisar `3.06.02` (em bancos pode ser imposto diferido)
- `lucro_liquido` -> usar `3.09` quando `3.11` nao existir

## Decisoes que substituíram o plano inicial
- **Precedencia por `SETOR_ATIV` foi descartada.** O setor nao e discriminador de
  layout: bancos reportam layout padrao, e holdings reportam o financeiro. A
  assinatura estrutural (`bpa.1.01` + `bpp.2.01`) classifica as 562 empresas do
  universo real em 29 `banking` / 533 `default`, sem filtro `SIT`.
- **`confidence` foi removido.** O perfil e uma asercao estrutural; `rule_applied`
  registra a origem da decisao.
- **PL por codigo foi descartado.** Resolvido por rotulo normalizado.

## Riscos e pontos em abertos
- **Hibridos**: 5 dos 29 `banking` (Celgpar, GP Investments, Oliveira Trust,
  SUL 116, Inter&Co) reportam o layout financeiro em poucos periodos e o padrao
  nos mais recentes — a assinatura e por empresa, nao por periodo, entao o perfil
  e o mesmo para todo o historico. Componentes que dependem do layout (caixa,
  EBIT) podem divergir nos periodos do outro layout.
- O significado de `3.06.02` ainda varia entre companhias.
- Bancos com operacoes de seguridade/previdencia podem misturar estruturas de conta.
