# Implementation Plan: Correções de Corretude do Pipeline CVM

**Branch**: `002-p1-refactor-scope-con` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-p1-refactor-scope-con/spec.md`

## Summary

Três bugs de corretude no pipeline CVM, dos quais dois já foram corrigidos (P1/P4) neste branch.
Os três itens restantes são: (P2-2A) normalização não-determinística da DRE entre valor YTD e
trimestral; (P2-2B) indicadores de resultado calculados com YTD parcial em vez de TTM anualizado;
(P3) 10.000 round-trips DuckDB→Python substituídos por uma query batch.

Abordagem: corrigir SQL de deduplicação DRE → implementar TTM simples → otimizar para batch.
Sem mudança de schema de tabelas. Sem dependências externas novas.

## Technical Context

**Language/Version**: Python 3.12 (gerenciado por `uv`)
**Primary Dependencies**: DuckDB (OLAP local), httpx (download), Typer (CLI), pydantic-settings (config)
**Storage**: DuckDB arquivo único `data/db/cvmdata.duckdb`
**Testing**: pytest com DuckDB in-memory; fixtures CSV em `tests/fixtures/`
**Target Platform**: Linux (desenvolvimento); qualquer plataforma com Python 3.12
**Project Type**: Single project — `src/cvmdata/`
**Performance Goals**: `calculate_all` para ~600 empresas × 20 períodos em < 10s (de ~minutos atuais)
**Constraints**: Pandas proibido na ingestão; sem dependências além das já no `pyproject.toml`
**Scale/Scope**: ~600 empresas abertas B3, 2021–2025, ~3 períodos ITR + 1 DFP por empresa/ano

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação |
|-----------|-----------|
| I. Simplicidade | ✅ Nenhuma abstração nova. Dois templates SQL em vez de um, TTM como função pura simples. |
| II. Pipeline por etapas isoladas | ✅ `normalize` e `indicators` continuam independentes via DuckDB. |
| III. Dados como fonte da verdade | ✅ `DT_INI_EXERC ASC` é determinístico e rastreável ao dado CVM original. |
| IV. Tolerância a falhas | ✅ Fallback chain no TTM: TTM → FY direto → YTD → None. Nunca levanta exceção. |
| V. Código Pythônico e testável | ✅ Funções puras, tipos anotados. Testes unitários com DuckDB in-memory. |
| VI. Evolução incremental | ✅ `_NORMALIZE_FLOW_SQL` é uma variação do SQL atual, não uma arquitetura nova. |
| VII. Schemas heterogêneos (NON-NEGOTIABLE) | ✅ DRE e BPA/BPP continuam em tabelas separadas com SQLs separados. |

**Violations**: nenhuma. Nenhuma justificativa de complexidade necessária.

**Post-design re-check**: ✅ — `data-model.md` confirma zero tabelas novas, zero dependências novas.

## Project Structure

### Documentation (this feature)

```text
specs/002-p1-refactor-scope-con/
├── plan.md        ← este arquivo
├── spec.md        ← user stories e acceptance criteria
├── research.md    ← decisões técnicas e alternativas consideradas
├── data-model.md  ← mudanças de comportamento nas tabelas *_clean
└── quickstart.md  ← pseudocódigo dos três passos de implementação
```

### Source Code (arquivos afetados)

```text
src/cvmdata/
├── ingestion/
│   ├── db.py          ✅ P1 done — SCOPES removido
│   ├── downloader.py  ✅ P1 done — _ind_ ignorado na extração
│   └── loader.py      ✅ P1+P4 done — scope/ind rejeitado + filtro ACCOUNT_MAP
└── transform/
    ├── normalize.py   ⏳ P2-2A — dois templates SQL (balance/flow)
    └── indicators.py  ⏳ P2-2B + P3 — TTM + batch query

tests/
├── test_normalize.py  ⏳ novos casos DRE YTD/PENÚLTIMO
└── test_indicators.py ⏳ novos casos TTM com fallback
```

**Structure Decision**: Single project, sem mudanças de layout. Apenas comportamento dos
módulos existentes é alterado.

## Complexity Tracking

> Nenhuma violação — seção não aplicável.
