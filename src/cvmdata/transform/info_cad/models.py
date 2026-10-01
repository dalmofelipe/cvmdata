"""Contrato de retorno da classificação."""

from __future__ import annotations

from typing import TypedDict


class ClassificationCounts(TypedDict):
    """Métricas de :func:`cvmdata.transform.info_cad.classify_info_cad`.

    ``by_profile`` e ``by_rule`` são dicionários livres de propósito: os perfis
    e as regras evoluem com o projeto, e um TypedDict fechado exigiria editar
    este contrato a cada regra nova sem dar nenhuma garantia ao consumidor —
    que só faz ``get`` e soma.
    """

    total: int
    by_profile: dict[str, int]
    by_rule: dict[str, int]


class MissingCleanTablesError(RuntimeError):
    """Uma ou mais ``*_clean`` não existem — o universo está incompleto.

    Erro de uso, não de dado: classificar exige demonstrativo normalizado e não
    pode deduzir o universo de outra fonte. Cobre tanto "nenhuma clean existe"
    quanto "falta uma das três" — nos dois casos o conserto é rodar
    ``normalize``, e o perfil cairia no ``default`` por ausência de dado em vez
    de layout padrão, o que é pior que falhar.

    Distinto de uma clean existente e vazia: essa classifica um universo vazio
    sem erro, porque o universo está completo e genuinamente sem empresas.
    """