"""Classificação cadastral de empresas CVM.

Fluxo:
  classify_info_cad(conn) -> dict com contagens de resultados

Etapas internas:
  1. Ler linhas SIT='ATIVO' de cad_cia_aberta_raw
  2. Resolver setor único por CNPJ usando apenas SETOR_ATIV
  3. Lookup profile_id via setor_profile_map
  4. Aplicar fallback default para não-mapeados/ambíguos/vazios
  5. (Se raw_bpa_clean existir) classificar CNPJs totalmente ausentes do
     cadastro via assinatura estrutural (SIGNATURE_RULES) e persistir em
     company_classification com confidence='medium'
  6. Persistir company_classification (INSERT OR REPLACE)
  7. Registrar eventos de curadoria para casos confidence=low e
     structural (upsert idempotente)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import duckdb

from cvmdata.transform.profile import find_profiles_missing_info_cad

logger = logging.getLogger(__name__)

# Perfil padrão quando setor não está mapeado ou é ambíguo
FALLBACK_PROFILE = "default"

# Tipos de evento de curadoria
EVENT_AMBIGUOUS = "ambiguous_setor"
EVENT_EMPTY = "empty_setor"
EVENT_UNMAPPED = "unmapped_setor"
EVENT_MISSING_FROM_CADASTRO = "missing_from_cadastro"

# Classificação por assinatura estrutural (CNPJ ausente do cadastro)
STRUCTURAL_CONFIDENCE = "medium"
STRUCTURAL_RULE = "structural_heuristic:1.01_caixa_direto:"


# ── SQL helpers ───────────────────────────────────────────────────────────────

# Lê todas as linhas ATIVO do bruto, escolhendo campos descritivos
# pela linha mais recente (DT_INI_SIT DESC, CD_CVM ASC, DENOM_SOCIAL ASC).
# Retorna (cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ, n_setores_distintos)
_SQL_ACTIVE_CLASSIFICATION = """
WITH ranked AS (
    SELECT
        CNPJ_CIA                    AS cnpj_cia,
        CD_CVM                      AS cd_cvm,
        DENOM_SOCIAL                AS denom_social,
        COALESCE(DENOM_COMERC, '')  AS denom_comerc,
        SETOR_ATIV                  AS setor_ativ,
        ROW_NUMBER() OVER (
            PARTITION BY CNPJ_CIA
            ORDER BY
                TRY_CAST(DT_INI_SIT AS DATE) DESC NULLS LAST,
                CD_CVM ASC,
                DENOM_SOCIAL ASC
        ) AS rn
    FROM cad_cia_aberta_raw
    WHERE SIT = 'ATIVO'
),
sectors AS (
    SELECT
        CNPJ_CIA AS cnpj_cia,
        COUNT(DISTINCT SETOR_ATIV) AS n_setores_distintos,
        MAX(CASE WHEN SETOR_ATIV IS NOT NULL AND TRIM(SETOR_ATIV) != '' THEN SETOR_ATIV END) 
            AS setor_unico
    FROM cad_cia_aberta_raw
    WHERE SIT = 'ATIVO'
    GROUP BY CNPJ_CIA
)
SELECT
    r.cnpj_cia,
    r.cd_cvm,
    r.denom_social,
    r.denom_comerc,
    r.setor_ativ,
    s.n_setores_distintos,
    s.setor_unico
FROM ranked r
JOIN sectors s ON s.cnpj_cia = r.cnpj_cia
WHERE r.rn = 1
"""

# Busca profile_id para um setor_ativ na tabela de governança
_SQL_PROFILE_LOOKUP = """
SELECT profile_id
FROM setor_profile_map
WHERE setor_ativ = ?
    AND active = TRUE
LIMIT 1
"""

# Upsert em company_classification (INSERT OR REPLACE)
_SQL_UPSERT_CLASSIFICATION = """
INSERT OR REPLACE INTO company_classification(
    cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ, profile_id, confidence, 
    rule_applied, updated_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Upsert idempotente em classification_curation_events
# Usa ON CONFLICT para atualizar details/updated_at sem duplicar
_SQL_UPSERT_CURATION_EVENT = """
INSERT INTO classification_curation_events(cnpj_cia, event_type, details, created_at, updated_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (cnpj_cia, event_type)
DO UPDATE SET
    details    = excluded.details,
    updated_at = excluded.updated_at
"""

# Enriquecimento descritivo de CNPJs sem cadastro, via raw_bpa_clean
# (campos descritivos não existem em cad_cia_aberta_raw para esses CNPJs).
_SQL_STRUCTURAL_ENRICH = """
SELECT CNPJ_CIA, ANY_VALUE(CD_CVM) AS cd_cvm, ANY_VALUE(DENOM_CIA) AS denom
FROM raw_bpa_clean
WHERE CNPJ_CIA = ANY(?) AND CD_CVM IS NOT NULL
GROUP BY CNPJ_CIA
"""


# ── Lógica principal ──────────────────────────────────────────────────────────


def _load_profile_map(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Carrega mapa setor_ativ -> profile_id ativo em memória."""
    rows = conn.execute(
        "SELECT setor_ativ, profile_id FROM setor_profile_map WHERE active = TRUE"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _load_structural_descriptors(
    conn: duckdb.DuckDBPyConnection,
    cnpjs: list[str],
) -> dict[str, tuple[str | None, str | None]]:
    """Busca (cd_cvm, denom) em raw_bpa_clean para CNPJs sem cadastro."""
    if not cnpjs:
        return {}
    rows = conn.execute(_SQL_STRUCTURAL_ENRICH, [cnpjs]).fetchall()
    return {cnpj_cia: (cd_cvm, denom) for cnpj_cia, cd_cvm, denom in rows}


def classify_info_cad(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Classifica CNPJs ativos (setor) e CNPJs ausentes do cadastro (estrutural).

    Returns:
        dict com chaves 'high', 'low', 'structural', 'total' e contagens.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Verificar se tabelas existem
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }
    if "cad_cia_aberta_raw" not in tables:
        raise RuntimeError("Tabela cad_cia_aberta_raw não encontrada — rode 'load-cad' primeiro")

    # Carregar mapa de perfis em memória (evita query por CNPJ)
    profile_map = _load_profile_map(conn)
    logger.info("setor_profile_map: %d mapeamentos ativos", len(profile_map))

    # Ler todos os CNPJs ativos com seus setores
    rows = conn.execute(_SQL_ACTIVE_CLASSIFICATION).fetchall()
    logger.info("CNPJs ativos encontrados: %d", len(rows))

    counts = {"high": 0, "low": 0, "structural": 0, "total": 0}

    classification_rows = []
    curation_rows = []

    for cnpj_cia, cd_cvm, denom_social, denom_comerc, setor_ativ, n_setores, setor_unico in rows:
        setor_str = (setor_ativ or "").strip()
        n = n_setores or 0

        # Determinar confidence, profile e event_type
        if n > 1:
            # Ambiguidade: múltiplos setores ativos distintos
            confidence = "low"
            profile_id = FALLBACK_PROFILE
            rule = "ambiguous_setor:fallback"
            event_type = EVENT_AMBIGUOUS
            details = f"n_setores_distintos={n}"
        elif not setor_str:
            # Setor vazio
            confidence = "low"
            profile_id = FALLBACK_PROFILE
            rule = "empty_setor:fallback"
            event_type = EVENT_EMPTY
            details = "setor_ativ vazio ou nulo"
        elif setor_str not in profile_map:
            # Setor presente mas não mapeado
            confidence = "low"
            profile_id = FALLBACK_PROFILE
            rule = f"unmapped_setor:{setor_str}:fallback"
            event_type = EVENT_UNMAPPED
            details = f"setor_ativ='{setor_str}' sem mapeamento em setor_profile_map"
        else:
            # Setor único e mapeado
            confidence = "high"
            profile_id = profile_map[setor_str]
            rule = f"setor_ativ:{setor_str}"
            event_type = None
            details = None

        classification_rows.append((
            cnpj_cia,
            cd_cvm,
            denom_social,
            denom_comerc,
            setor_str or None,
            profile_id,
            confidence,
            rule,
            now,
        ))

        if event_type is not None:
            curation_rows.append((cnpj_cia, event_type, details, now, now))

        counts[confidence] += 1
        counts["total"] += 1

    # Fase estrutural: CNPJs com demonstrativos em raw_*_clean mas totalmente
    # ausentes do cadastro (e de company_classification) — ex.: caso Banco Inter.
    profile_map = find_profiles_missing_info_cad(conn)
    if profile_map:
        descriptors = _load_structural_descriptors(conn, list(profile_map))
        for cnpj_cia, profile_id in profile_map.items():
            cd_cvm, denom = descriptors.get(cnpj_cia, (None, None))
            classification_rows.append((
                cnpj_cia,
                cd_cvm,
                denom,
                denom,
                None,
                profile_id,
                STRUCTURAL_CONFIDENCE,
                STRUCTURAL_RULE + profile_id,
                now,
            ))
            curation_rows.append((
                cnpj_cia,
                EVENT_MISSING_FROM_CADASTRO,
                "cnpj ausente de cad_cia_aberta_raw; perfil via assinatura estrutural",
                now,
                now,
            ))
            counts["structural"] += 1

    counts["total"] += counts["structural"]
    
    conn.execute("BEGIN")
    try:
        if classification_rows:
            conn.executemany(_SQL_UPSERT_CLASSIFICATION, classification_rows)
        if curation_rows:
            conn.executemany(_SQL_UPSERT_CURATION_EVENT, curation_rows)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    logger.info(
        "Classificação concluída: %d total (%d high, %d low, %d structural)",
        counts["total"],
        counts["high"],
        counts["low"],
        counts["structural"],
    )
    return counts
