# Feature Specification: Pipeline CVM — Indicadores Fundamentalistas

**Feature Branch**: `001-cvm-pipeline`
**Created**: 2026-02-20
**Status**: Draft

## User Scenarios & Testing

### User Story 1 — Baixar e ingerir dados financeiros da CVM (Priority: P1)

Como analista/investidor, quero que o sistema baixe automaticamente os documentos financeiros de todas as empresas abertas da B3 publicados na CVM e os armazene localmente, para que eu tenha uma base de dados completa e atualizada sem precisar fazer isso manualmente.

**Why this priority**: Sem dados ingeridos nada mais funciona. É o fundamento de todo o pipeline.

**Independent Test**: Executar o comando de download e carga para o ano de 2024 e verificar que as tabelas BPA, BPP e DRE existem no banco com registros de múltiplas empresas.

**Acceptance Scenarios**:

1. **Given** conexão com a internet disponível, **When** o usuário executa o comando de download para 2024, **Then** os ZIPs da CVM são baixados para `data/raw/` e extraídos sem erros
2. **Given** os CSVs estão extraídos em `data/raw/`, **When** o usuário executa o comando de carga, **Then** os 8 tipos de demonstrativo (BPA, BPP, DRE, DFC-MD, DFC-MI, DRA, DMPL, DVA) são carregados no banco para as variantes consolidada e individual
3. **Given** um ZIP já foi baixado anteriormente, **When** o comando de download é reexecutado, **Then** o arquivo não é rebaixado (checksum idêntico) e o processo termina mais rápido
4. **Given** os dados de 2024 já estão carregados, **When** o usuário executa o download para 2023, **Then** os dados de 2023 são adicionados sem apagar os de 2024

---

### User Story 2 — Normalizar e dedupliar dados (Priority: P2)

Como analista, quero que o sistema elimine duplicatas e corrija inconsistências nos dados brutos da CVM, para que os cálculos de indicadores sejam baseados em dados confiáveis e na versão mais recente de cada documento.

**Why this priority**: Empresas republicam documentos com correções; sem deduplicação, os indicadores calculados podem ser incorretos.

**Independent Test**: Carregar um CSV com duas versões da mesma conta para a mesma empresa/período e verificar que após normalização existe apenas um registro (o de maior `VERSAO`).

**Acceptance Scenarios**:

1. **Given** existem múltiplas versões do mesmo documento para uma empresa/período, **When** a normalização é executada, **Then** apenas a linha com maior `VERSAO` é mantida para cada `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)`
2. **Given** registros com `ORDEM_EXERC = 'PENÚLTIMO'` existem no banco, **When** os indicadores são calculados, **Then** apenas registros `ÚLTIMO` são usados nos cálculos
3. **Given** `CD_CVM` com zero à esquerda (ex: `001023`), **When** normalização é executada, **Then** o valor é padronizado para inteiro sem zeros (ex: `1023`)
4. **Given** colunas de data como string, **When** normalização é executada, **Then** `DT_REFER` e `DT_FIM_EXERC` são convertidas para tipo `DATE`

---

### User Story 3 — Calcular indicadores fundamentalistas por empresa (Priority: P3)

Como analista/investidor, quero calcular os indicadores de análise fundamentalista (rentabilidade, liquidez e endividamento) para qualquer empresa da B3 em qualquer período disponível, para avaliar a saúde financeira da empresa ao longo do tempo.

**Why this priority**: É o entregável final do pipeline — o motivo de tudo existir.

**Independent Test**: Calcular os indicadores para CNPJ `00.000.000/0001-91` (BCO Brasil) no período `2024-09-30` e verificar que ROE, ROA, Liquidez Corrente e Endividamento Geral retornam valores numéricos plausíveis.

**Acceptance Scenarios**:

1. **Given** dados normalizados de uma empresa no banco, **When** o cálculo de indicadores é executado para aquela empresa/período, **Then** ROE, ROA e Margem Líquida são calculados e salvos na tabela `indicators`
2. **Given** dados normalizados de uma empresa no banco, **When** o cálculo é executado, **Then** Liquidez Corrente, Liquidez Geral e Liquidez Imediata são calculados e salvos
3. **Given** dados normalizados de uma empresa no banco, **When** o cálculo é executado, **Then** Endividamento Geral é calculado e salvo
4. **Given** uma conta necessária para um indicador não existe para uma empresa/período, **When** o cálculo é executado, **Then** o indicador retorna `null` e o processamento das demais empresas continua sem interrupção
5. **Given** indicadores já calculados para um período, **When** o cálculo é reexecutado, **Then** os valores existentes são substituídos (operação idempotente)
6. **Given** o comando é executado sem `--cnpj`, **When** o cálculo roda, **Then** todos os indicadores são calculados para todas as empresas/períodos disponíveis no banco

---

### User Story 4 — Consultar indicadores calculados (Priority: P4)

Como analista, quero consultar os indicadores calculados por empresa e período, para comparar a evolução histórica de uma empresa ou comparar empresas diferentes.

**Why this priority**: Sem forma de consultar os dados o pipeline não entrega valor observável; necessário para validar os cálculos.

**Independent Test**: Consultar indicadores de BCO Brasil para todos os trimestres de 2024 e receber uma tabela com colunas `dt_refer`, `indicador`, `valor`.

**Acceptance Scenarios**:

1. **Given** indicadores calculados no banco, **When** o usuário consulta por `CNPJ` e período, **Then** uma tabela com `(dt_refer, indicador, valor)` é retornada
2. **Given** indicadores de múltiplos períodos para uma empresa, **When** consultados sem filtro de data, **Then** todos os períodos disponíveis são retornados ordenados por `dt_refer`

---

### Edge Cases

- O que acontece quando um ZIP da CVM está temporariamente indisponível para download?
- Como o sistema se comporta com empresas que publicaram dados apenas em alguns trimestres?
- O que acontece quando `VL_CONTA` é zero no denominador de um indicador (ex: Patrimônio Líquido = 0)?
- Como tratar empresas com `ESCALA_MOEDA = 'UNIDADE'` em vez de `MIL`?
- O que acontece quando o mesmo arquivo CSV aparece em ZIPs de anos diferentes (overlap de dados)?

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE baixar os ZIPs de ITR e DFP da CVM para anos configuráveis (padrão: 2021–2025) via HTTP
- **FR-002**: O sistema DEVE extrair os CSVs dos ZIPs para `data/raw/{tipo}/{year}/` sem modificar os arquivos originais
- **FR-003**: O sistema DEVE detectar ZIPs já baixados via checksum MD5 e pular o redownload quando idênticos
- **FR-004**: O sistema DEVE carregar os 8 tipos de demonstrativo (BPA, BPP, DRE, DFC-MD, DFC-MI, DRA, DMPL, DVA) nas variantes consolidada e individual
- **FR-005**: O sistema DEVE deduplicar registros mantendo apenas o de maior `VERSAO` por `(CNPJ_CIA, DT_REFER, CD_CONTA, ORDEM_EXERC)`
- **FR-006**: O sistema DEVE calcular os seguintes indicadores quando os dados estiverem disponíveis: ROE, ROA, Margem Líquida, Liquidez Corrente, Liquidez Geral, Liquidez Imediata, Endividamento Geral
- **FR-007**: O sistema DEVE retornar `null` para qualquer indicador cujo denominador seja zero ou cuja conta necessária esteja ausente
- **FR-008**: O sistema DEVE processar todas as ~600 empresas sem interromper o pipeline por erro em uma empresa individual
- **FR-009**: O sistema DEVE expor todas as operações via CLI com os comandos: `download`, `load`, `normalize`, `indicators`
- **FR-010**: Todos os comandos CLI DEVEM ser idempotentes — reexecutar não deve duplicar dados ou produzir resultados diferentes

### Key Entities

- **Demonstrativo Financeiro**: Conjunto de linhas contábeis de uma empresa para um período específico; identificado por `(CNPJ_CIA, DT_REFER, VERSAO, tipo)`; cada linha tem `CD_CONTA`, `DS_CONTA` e `VL_CONTA`
- **Conta Contábil**: Linha individual de um demonstrativo; identificada por `CD_CONTA` (hierárquica, ex: `1.01.02`); representa um componente financeiro (caixa, passivo circulante, lucro líquido, etc.)
- **Empresa**: Identificada por `CNPJ_CIA` e `CD_CVM`; publica múltiplos demonstrativos por ano (ITR trimestral + DFP anual)
- **Indicador**: Resultado de uma fórmula aplicada sobre contas de uma empresa em um período; armazenado como `(CNPJ_CIA, DT_REFER, indicador, valor)`
- **Mapeamento de Contas**: Dicionário que relaciona `CD_CONTA` a componentes semânticos (ex: `"1"` → `ativo_total`); evolui incrementalmente conforme descobertas nos dados

## Success Criteria

### Measurable Outcomes

- **SC-001**: O pipeline completo (download + load + normalize + indicators) para o ano de 2024 executa sem erros fatais em uma máquina com acesso à internet
- **SC-002**: Após o pipeline, a tabela `indicators` contém registros para pelo menos 90% das empresas com dados disponíveis no BPA + BPP + DRE de 2024
- **SC-003**: Para empresas onde todos os componentes necessários existem, nenhum indicador retorna `null` indevidamente
- **SC-004**: Reexecutar qualquer etapa do pipeline produz os mesmos resultados (idempotência verificável via contagem de registros)
- **SC-005**: Os valores calculados para BCO Brasil (CNPJ `00.000.000/0001-91`) Q3 2024 são verificáveis manualmente contra os dados brutos do CSV

## Review & Acceptance Checklist

- [ ] Todos os user stories têm cenários de aceitação testáveis
- [ ] Edge cases cobrem os principais riscos identificados nos dados da CVM
- [ ] Requisitos funcionais são suficientes para guiar a implementação
- [ ] Critérios de sucesso são mensuráveis e verificáveis
- [ ] A spec não prescreve tecnologia — foca no "o quê", não no "como"

