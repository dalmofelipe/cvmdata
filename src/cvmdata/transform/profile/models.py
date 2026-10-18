from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleCondition:
    """Um sinal de estrutura: rótulo esperado numa conta de ``CD_CONTA`` fixo.

    ### Properties
        `clean_table`: Tabela clean onde o condição da regra é procurado.
        `cd_conta`: Código de conta que precisa existir.
        `ds_conta_normalized`: Texto já normalizado — minúsculo, sem acento,
            sem espaços nas pontas.
        `starts_with`: Casa por prefixo em vez de igualdade exata. Use quando o
            rótulo varia no final ("Passivos Financeiros Avaliados ao Valor
            Justo..." vs "...ao Custo Amortizado").
    """

    clean_table: str
    cd_conta: str
    ds_conta_normalized: str
    starts_with: bool = False

    def sql_condition(self, norm_expr: str) -> str:
        """Comparação do rótulo normalizado contra o param do sinal."""
        if self.starts_with:
            return f"starts_with({norm_expr}, ?)"
        return f"{norm_expr} = ?"


@dataclass(frozen=True)
class StructuralRule:
    """Regra de classificação: todos os ``conditions`` precisam concordar."""

    profile_id: str
    conditions: tuple[RuleCondition, ...]
    description: str = ""

    @property
    def rule_applied(self) -> str:
        """Identificador estável da regra, persistido em ``rule_applied``."""
        parts = "+".join(
            f"{condition.clean_table.removesuffix('_clean')}.{condition.cd_conta}" 
            for condition in self.conditions
        )
        return f"structure:{self.profile_id}:{parts}"