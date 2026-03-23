# Centralized logging setup
import logging


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level based on verbose flag.
    
    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )

