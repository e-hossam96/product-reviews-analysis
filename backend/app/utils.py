import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from app.core.config import get_settings


def setup_logger(name: str = __name__, log_level: str = "INFO") -> logging.Logger:
    level = getattr(logging, log_level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        theme = Theme(
            {
                "info": "cyan",
                "warning": "yellow",
                "error": "red",
                "critical": "red bold",
                "debug": "grey50",
            }
        )
        console = Console(theme=theme, width=130, tab_size=4)

        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=False,  # log messages may contain user text with [brackets]
            show_time=True,
            show_path=False,
            omit_repeated_times=True,
        )
        console_handler.setFormatter(logging.Formatter(f"{name.upper()} | %(message)s"))
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

        Path("logs").mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(f"logs/{name}.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(f"{name.upper()} | %(asctime)s | %(levelname)s | %(message)s"))
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


_settings = get_settings()
logger = setup_logger(_settings.application.name, _settings.application.log_level)
