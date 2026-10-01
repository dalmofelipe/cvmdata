# Perfil de Empresa

## Objetivo
Calcular indicadores com a semântica contábil correta por tipo de empresa
(`default`, `banking`) sem quebrar o pipeline em lote.

Este documento descreve o que está implementado. A análise que deu origem à
assinatura estrutural está em [banking_profile.md](banking_profile.md).

## Problema
Um `ACCOUNT_MAP` único, orientado a perfil industrial, aplicado a todas as
empresas. Instituições financeiras reportam estrutura diferente, o que gerava
indicadores nulos (ou errados) em bancos e holdings de crédito.

## Como o perfil é decidido: layout, não setor

O perfil vem da **assinatura estrutural** do demonstrativo, lida das tabelas
`*_clean`. O setor de atividade é apenas override manual.

O motivo é que `SETOR_ATIV` não é discriminador de layout:
- bancos reportam o layout padrão (`1.01` = "Ativo Circulante"), não o financeiro;
- holdings de crédito (`Intermediacao Financeira`, `Securitizacao`) podem
  reportar o layout financeiro;
- holdings de participações em bancos (Celgpar, SUL 116, Oliveira Trust) usam o
  layout financeiro em poucos períodos e o padrão nos mais recentes.

Classificar por setor erra nos dois sentidos. A assinatura lê o que a empresa de
fato reportou.

### Assinatura `banking`
Exige os dois sinais, no mesmo conjunto de períodos:
- `bpa_clean`: `CD_CONTA = '1.01'` com `DS_CONTA` normalizado = "Caixa e Equivalentes de Caixa";
- `bpp_clean`: `CD_CONTA = '2.01'` com `DS_CONTA` começando com "Passivos Financeiros".

Ambos juntos é o que separa banco de não-banco: a empresa que concorda nas duas
pontas usa o layout financeiro.

`rule_applied` registra a decisão, ex.: `structure:banking:bpa.1.01+bpp.2.01`.

## Cadeia de decisão (precedência)
1. **Assinatura estrutural** — `bpa.1.01` + `bpp.2.01` concordando → `banking`.
2. **Override setorial explícito** — linha em `setor_profile_map` com
   `active = TRUE`.
3. **Fallback** → `default`.

A assinatura vence o override: se a estrutura prova o layout financeiro, ela
decide (e vice-versa).

## Entidades
- **Perfil** (`profile_id`): um dicionário em `transform/account_map.py`
  mapeando `CD_CONTA` → componente semântico, mais a política de cálculo
  (indicadores não aplicáveis ficam `None` por falta de componente honesto).
- **Classificação** (`company_classification`): uma linha por CNPJ, com
  `profile_id`, `rule_applied`, descritores e `updated_at`.
- **Override setorial** (`setor_profile_map`): `SETOR_ATIV` → `profile_id`,
  `active`. **Nasce vazia** e não é populada pelo pipeline.

Não há `confidence` nem `rule_version`: o perfil é uma asserção determinística
sobre o layout, não uma inferência probabilística. A auditabilidade vem de
`rule_applied`, que diz *por quê*, não de *quão confiante*.

## Resolução do patrimônio líquido (por rótulo)

O PL não tem posição estável, e o código não o identifica:

| `CD_CONTA` | Layout padrão | Layout financeiro (2026) |
|---|---|---|
| `2.03` | Patrimônio Líquido | Provisões (19 bancos) / Passivos ao Custo Amortizado (16) |
| `2.07` | — | Patrimônio Líquido Consolidado |
| `2.08` | — | Patrimônio Líquido Consolidado (Itaú) |

Mapear qualquer código fixaria o PL errado (Provisões virando patrimônio,
passivos virando patrimônio). Por isso `resolve_pl` (`transform/text_map.py`)
resolve o PL pelo **rótulo normalizado** (`startswith("patrimonio liquido")`),
que é estável entre e dentro dos perfis. O mesmo vale para a cauda do DRE
(`resolve_tail`).

`2.03`, `2.07` e `2.08` entram no fetch (`BPP_PL_CODES`) mesmo fora do
`ACCOUNT_MAP`, só para o resolvedor textual poder ver o rótulo.

## Batch
- Perfil resolvido uma vez, em SQL, por CNPJ (`fetch_profiles`).
- Sem query por linha/período no laço de cálculo.

## Onde o perfil é persistido
`classify_info_cad` (step do pipeline, pós-normalize) reconstrói
`company_classification` em transação, sobre o universo das `*_clean`, sem
filtrar `SIT` (empresa cancelada que reporta continuava sendo classificada).