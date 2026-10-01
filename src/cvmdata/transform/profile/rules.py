"""As regras de assinatura estrutural do projeto.

Uma regra nova entra aqui e vale para todos os consumidores: a classificação
(:mod:`cvmdata.transform.info_cad`) e qualquer auditoria que queira perguntar
"por que esta empresa é banking?" lendo a regra em Python.
"""

from __future__ import annotations

from cvmdata.ingestion.tables import TB_BPA_CLEAN, TB_BPP_CLEAN
from cvmdata.transform.profile.models import SignatureRule, SignatureSignal

SIGNATURE_RULES: list[SignatureRule] = [
    SignatureRule(
        profile_id="banking",
        signals=(
            SignatureSignal(
                table=TB_BPA_CLEAN,
                cd_conta="1.01",
                ds_conta_normalized="caixa e equivalentes de caixa",
            ),
            SignatureSignal(
                table=TB_BPP_CLEAN,
                cd_conta="2.01",
                ds_conta_normalized="passivos financeiros",
                starts_with=True,
            ),
        ),
        description=(
            "Layout financeiro: BPA 1.01 rotulado 'Caixa e Equivalentes de Caixa' "
            "(agregado, sem subdivisão 1.01.01) e BPP 2.01 rotulado 'Passivos "
            "Financeiros...'. Os dois sinais concordam exatamente nas mesmas 29 "
            "empresas do universo; exigir ambos elimina os falsos positivos que "
            "cada sinal sozinho teria (BPP 2.01 financeiro com BPA 1.01 padrão)."
        ),
    ),
]