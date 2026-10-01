"""Perfil contábil de empresa, decidido pelo layout reportado.

O ``profile_id`` não vem do setor de atividade: ``SETOR_ATIV`` descreve o
negócio, e o negócio não determina o demonstrativo. Empresa do setor bancário
reporta layout padrão (``BPP 2.01`` = "Passivo Circulante") e holding de crédito
reporta layout financeiro (``BPP 2.01`` = "Passivos Financeiros Avaliados ao
Valor Justo"). O que separa os dois é o rótulo da conta, não o setor.

:class:`~cvmdata.transform.profile.models.SignatureRule` formaliza esse
conhecimento como sinais ``(tabela, CD_CONTA, DS_CONTA normalizado)``. Todos os
sinais de uma regra precisam concordar — no universo atual, ``BPA 1.01`` e
``BPP 2.01`` selecionam exatamente as mesmas 29 empresas, e nenhum dos dois
isolados tem falso positivo. Exigir os dois torna a detecção estável.

Organização do pacote:

- :mod:`~cvmdata.transform.profile.models` — o contrato (``SignatureSignal``,
  ``SignatureRule``, ``FALLBACK_PROFILE``), sem SQL;
- :mod:`~cvmdata.transform.profile.rules` — as regras do projeto
  (``SIGNATURE_RULES``);
- :mod:`~cvmdata.transform.profile.sql` — renderização das regras em SQL e da
  precedência;
- :mod:`~cvmdata.transform.profile.repository` — ``company_classification``
  (leitura e reconstrução).

Quem consome a classificação importa do submódulo que precisa: as regras e o
renderizador vêm deste pacote, a leitura da tabela vem de
:mod:`~cvmdata.transform.profile.repository`. Só há reexport quando o nome faz
sentido fora do pacote — ``SIGNATURE_RULES``, por exemplo, é a resposta para
"quais regras existem", e nenhum módulo interno devia ser obrigado a saber.

A normalização de ``DS_CONTA`` aparece em Python
(:func:`cvmdata.transform.text_map.normalize_text`, no fetch de indicadores) e em
SQL (:data:`~cvmdata.transform.profile.sql.NORM_DS_CONTA_SQL`, na classificação).
As duas devem concordar — coberto por teste.
"""

from __future__ import annotations

from cvmdata.transform.profile.models import (
    FALLBACK_PROFILE,
    SignatureRule,
    SignatureSignal,
)
from cvmdata.transform.profile.rules import SIGNATURE_RULES
from cvmdata.transform.profile.sql import (
    NORM_DS_CONTA_SQL,
    classification_sql,
    signature_flags_sql,
    signature_predicate,
)

__all__ = [
    "FALLBACK_PROFILE",
    "NORM_DS_CONTA_SQL",
    "SIGNATURE_RULES",
    "SignatureRule",
    "SignatureSignal",
    "classification_sql",
    "signature_flags_sql",
    "signature_predicate",
]