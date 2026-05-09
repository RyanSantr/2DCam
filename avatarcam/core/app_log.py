from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from avatarcam.core.settings import LOG_DIR


def setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("avatarcam")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        LOG_DIR / "avatarcam.log",
        maxBytes=512_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
