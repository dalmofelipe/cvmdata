"""Leitura das fontes que alimentam a classificação.

Fica separado de :mod:`cvmdata.transform.info_cad.classify` porque "quais
tabelas existem" é uma pergunta de leitura; a reconstrução da tabela de
classificação é de :mod:`cvmdata.transform.profile.repository`, e a composição
do SQL é de :mod:`cvmdata.transform.info_cad.queries`.
"""

from __future__ import annotations

import duckdb

from cvmdata.ingestion.tables import CLEAN_TABLES
from cvmdata.transform.info_cad.models import MissingCleanTablesError
from cvmdata.transform.profile.repository import existing_tables


def require_clean_tables(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """As três clean, na ordem de :data:`CLEAN_TABLES`, ou erro.

    Não filtra as ausentes. As regras de assinatura citam ``bpa_clean`` e
    ``bpp_clean`` por nome em SQL, então um universo montado sobre um subconjunto
    das clean não classificaria — estouraria erro de catálogo no meio do
    statement. E o que ele classificaria, se o SQL deixasse, seria pior: um CNPJ
    que só reporta DRE entraria no universo sem o BPA que decide o perfil, e
    cairia no ``default`` por ausência de dado, não por layout padrão. Falhar é
    o resultado correto para um universo incompleto.

    A ordem é fixa para que duas execuções sobre o mesmo banco produzam o mesmo
    SQL — e, portanto, o mesmo plano.

    Raises:
        MissingCleanTablesError: Se alguma faltar.
    """
    existentes = set(existing_tables(conn))
    faltando = [t for t in CLEAN_TABLES if t not in existentes]
    if faltando:
        raise MissingCleanTablesError(
            f"Clean faltando ({', '.join(faltando)}) — "
            "rode 'normalize' antes de classificar"
        )
    return list(CLEAN_TABLES)