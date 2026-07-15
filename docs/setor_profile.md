# Setor Profile

## Objetivo
Definir uma arquitetura de perfis setoriais para calcular indicadores de forma correta por tipo de empresa (ex.: industrial, bancos) sem quebrar performance do pipeline em lote.

## Problema atual
- Um unico `ACCOUNT_MAP` e aplicado a todas as empresas.
- Empresas financeiras usam contas CVM diferentes.
- Resultado: indicadores nulos ou semanticamente incorretos em alguns setores.

## Principios
- Perfil por empresa deve ser deterministico e auditavel.
- Regras devem ser extensivas sem alterar o core a cada novo setor.
- Fallback seguro para `default`.
- Performance em batch deve ser preservada.

## Entidades conceituais
### 1) Profile
Conjunto de regras de calculo para um grupo de empresas.

Campos recomendados:
- `profile_id` (ex.: `default`, `banking`)
- `description`
- `account_map` (componente -> lista ordenada de contas CVM)
- `indicator_policy` (enabled, disabled, alt_formula)
- `version`

### 2) Resolver de profile
Funcao que determina `profile_id` por empresa, usando dados cadastrais e regras.

## Cadeia de decisao (precedencia)
1. Regra explicita por CNPJ (override)
2. Regra por `SETOR_ATIV`
3. Regra por `CD_CVM` (se aplicavel)
4. Heuristica por denominacao social/comercial
5. Fallback para `default`

## confidence e rule_version
- `confidence`: confianca da classificacao (`high`, `medium`, `low`).
- `rule_version`: versao do ruleset usado na decisao.

Esses campos sao obrigatorios para governanca e auditoria.

## Estrategia de calculo por profile
### Industrial (padrao)
- Mantem formulas e contas atuais.

### Banking
- Usa contas e semantica proprias para bancos.
- Alguns indicadores industriais podem ser desativados ou substituidos.

## Politica de indicadores
Cada profile deve declarar para cada indicador:
- `enabled`: calcula normalmente
- `disabled`: nao aplicavel ao perfil
- `alt_formula`: formula alternativa para o setor

## Performance (requisito nao funcional)
- Resolver profile em batch por CNPJ antes do loop de calculo.
- Evitar query por linha (empresa/periodo).
- Preservar abordagem de duas queries grandes + calculo em memoria.

## Observacao importante sobre ingestao
Se o loader filtrar estritamente contas por mapa industrial, contas setoriais novas podem ser descartadas antes da analise.

Diretriz:
- prever modo de descoberta/evolucao de perfil para nao perder contas relevantes.

## Roadmap sugerido
1. Fase 1: `default` + `banking`.
2. Fase 2: `insurance` e `securitization` (se necessario por evidencia).
3. Fase 3: consolidar matriz de aplicabilidade de indicadores por setor.

## Criterios de aceite (planejamento)
- Perfil aplicado por CNPJ de forma deterministica.
- Resultado do calculo registra `profile_id` utilizado.
- Empresas industriais sem regressao.
- Bancos com reducao de nulos indevidos e semantica melhorada.
- Inclusao de novos perfis sem refatoracao ampla do core.
