"""
Este modulo forneçe uma estrutura base para mapeamento e ajustes de caracteristicas 
observadas nos demonstrativos financeiros.

Referências: docs/profiles.md, docs/classificacao.md
"""

from __future__ import annotations

from cvmdata.ingestion.tables import TB_BPA_CLEAN, TB_BPP_CLEAN
from cvmdata.transform.profile.models import RuleCondition, StructuralRule

FALLBACK_PROFILE = "default"

STRUCTURAL_RULES: list[StructuralRule] = [
    StructuralRule(
        profile_id="banking",
        conditions=(
            RuleCondition(
                clean_table=TB_BPA_CLEAN,
                cd_conta="1.01",
                ds_conta_normalized="caixa e equivalentes de caixa",
            ),
            RuleCondition(
                clean_table=TB_BPP_CLEAN,
                cd_conta="2.01",
                ds_conta_normalized="passivos financeiros",
                starts_with=True,
            ),
        ),
        description=(
            "Estrutura financeira: BPA 1.01 texto 'Caixa e Equivalentes de Caixa' "
            "(agregado, sem subdivisão 1.01.01) e BPP 2.01 texto 'Passivos "
            "Financeiros...'. Exigir os dois sinais elimina os falsos positivos de "
            "cada um sozinho — BPP 2.01 com BPA 1.01 padrão acontece, e é estrutura "
            "híbrido, não banco.\n\nNote quem casa fora do setor Bancos: holdings de "
            "crédito, securitizadoras e participações que reportam estrutura financeiro."
            "É por isso que a assinatura existe em vez de um mapeamento por setor."
        ),
    ),
]