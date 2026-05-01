"""Configuração centralizada de logging do CLI."""

import logging


def configure_logging(verbose: bool = False) -> None:
    """Configura o nível de logging com base no flag verbose."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )


# Compatibilidade retroativa com implementação inicial da feature.
def setup_logging(verbose: bool = False) -> None:
    """Alias retrocompatível para configure_logging."""
    configure_logging(verbose)
