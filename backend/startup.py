"""
Startup script: make sure the data directory exists before Alembic migrations run.

The database file lives on a Docker volume mounted at the data directory. If the
file already exists it is used as-is; otherwise Alembic creates a fresh database.
"""

from pathlib import Path

from app.core.config import get_settings
from app.utils import logger


def prepare_data_directory() -> None:
    settings = get_settings()
    db_path = Path(settings.database.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        logger.info("Found existing database at '%s' - using volume data", db_path)
    else:
        logger.info("No database found at '%s' - a fresh one will be created", db_path)


if __name__ == "__main__":
    prepare_data_directory()
    logger.info("Startup complete")
