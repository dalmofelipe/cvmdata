# Banking Profile

## Objetivo
Documentar a analise dos codigos CVM usados por bancos e explicar por que o `ACCOUNT_MAP` atual (orientado a perfil industrial) gera indicadores nulos para instituicoes financeiras.

Este documento e de planejamento e analise. Nao implementa alteracoes no pipeline.

## Fontes analisadas
- `src/cvmdata/transform/account_map.py`
- `tests/test_indicators.py` (casos `xfail` com `sector_profile pending`)
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

## Estado atual no codigo
O `ACCOUNT_MAP` atual usa a seguinte logica principal:
- `divida_bruta = 2.01.04 + 2.02.01`
- `divida_liquida = divida_bruta - 1.01.01 - 1.01.02`
- `liquidez_seca = (1.01 - 1.01.04) / 2.01`
- `roe = 3.11 / 2.03`

Ja existe anotacao explicita em `account_map.py` indicando necessidade de `sector_profile` para bancos.

## Evidencias de testes
Em `tests/test_indicators.py`:
- `test_bank_sector_liquidez_seca_not_none` esta `xfail`.
  - Motivo: banco nao reporta `1.01.04` (estoques).
- `test_bank_sector_divida_bruta_not_none` esta `xfail`.
  - Motivo: banco nao reporta `2.01.04`.

Esses testes confirmam que os nulos em bancos sao comportamento esperado no estado atual, e nao falha de ingestao.

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

## Proposta de mapeamento preliminar para `banking`
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
- `patrimonio_liquido` -> avaliar por caso:
  - em alguns bancos pode continuar em `2.03` (por fixture)
  - em outros, `2.03` pode ter semantica de passivo financeiro
- `receita_liquida` -> `3.01`
- `resultado_bruto` -> `3.03`
- `ebit` -> `3.05`
- `despesas_financeiras` -> revisar `3.06.02` (em bancos pode ser imposto diferido)
- `lucro_liquido` -> usar `3.09` quando `3.11` nao existir

## Regras minimas recomendadas (planejamento)
- Criar profile `banking` com precedencia por classificacao cadastral (`SETOR_ATIV`).
- Aplicar fallback de conta por lista ordenada (ex.: `lucro_liquido`: `3.11`, depois `3.09`).
- Marcar indicadores nao aplicaveis ao setor em `indicator_policy` (`disabled` ou `alt_formula`).
- Registrar `profile_id`, `confidence` e `rule_version` para auditoria.

## Riscos e pontos em aberto
- O significado de `2.03` e `3.06.02` varia entre companhias; nao assumir sem validação por amostra maior.
- Bancos com operacoes de seguridade/previdencia podem misturar estruturas de conta.
- Existe heterogeneidade entre ITR e DFP; regra final deve ser validada nas duas fontes.

## Proximos passos sugeridos
1. Fechar um dicionario de componentes do profile `banking` usando amostra de bancos relevantes.
2. Definir matriz de aplicabilidade de indicadores para perfil bancario.
3. Rodar teste de regressao comparando `industrial_default` vs `banking` em CNPJs de referencia.
4. Promover os `xfail` bancarios para testes verdes apos implementacao do profile.
