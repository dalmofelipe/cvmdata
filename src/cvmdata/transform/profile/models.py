"""Contratos de dados da classificação de perfil.

:class:`SignatureSignal` e :class:`SignatureRule` são o conhecimento de domínio
"que layout contábil indica qual perfil", sem nenhuma dependência de SQL: são
consumidos tanto pelo renderizador de :mod:`cvmdata.transform.profile.sql` quanto
pela leitura da regra em Python.
"""

from __future__ import annotations

from dataclasses import dataclass

# Perfil aplicado quando a assinatura não casa e não há override setorial.
FALLBACK_PROFILE = "default"


@dataclass(frozen=True)
class SignatureSignal:
    """Um sinal de layout: rótulo esperado numa conta de ``CD_CONTA`` fixo.

    Args:
        table: Tabela clean onde o sinal é procurado (``bpa_clean``/``bpp_clean``).
        cd_conta: Código de conta que precisa existir.
        ds_conta_normalized: Rótulo já normalizado — minúsculo, sem acento,
            sem espaços nas pontas.
        starts_with: Casa por prefixo em vez de igualdade exata. Use quando o
            rótulo varia na cauda ("Passivos Financeiros Avaliados ao Valor
            Justo..." vs "...ao Custo Amortizado").
    """

    table: str
    cd_conta: str
    ds_conta_normalized: str
    starts_with: bool = False

    def sql_condition(self, norm_expr: str) -> str:
        """Comparação do rótulo normalizado contra o param do sinal.

        Args:
            norm_expr: Expressão SQL que produz o rótulo normalizado.

        Returns:
            Predicado com um ``?`` placeholder, na posição em que o caller
            passa :attr:`ds_conta_normalized` como param.
        """
        if self.starts_with:
            return f"starts_with({norm_expr}, ?)"
        return f"{norm_expr} = ?"


@dataclass(frozen=True)
class SignatureRule:
    """Regra de classificação: todos os ``signals`` precisam concordar.

    Args:
        profile_id: Perfil atribuído quando a regra casa.
        signals: Sinais que precisam ser todos satisfeitos.
        description: Texto explicando o critério — documentação, não executado.
    """

    profile_id: str
    signals: tuple[SignatureSignal, ...]
    description: str = ""

    @property
    def rule_applied(self) -> str:
        """Identificador estável da regra, persistido em ``rule_applied``."""
        parts = "+".join(
            f"{s.table.removesuffix('_clean')}.{s.cd_conta}" for s in self.signals
        )
        return f"structure:{self.profile_id}:{parts}"