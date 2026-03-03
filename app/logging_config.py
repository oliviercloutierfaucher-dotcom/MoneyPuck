"""Centralized logging configuration for MoneyPuck."""
from __future__ import annotations

import logging
import os
import sys


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure and return the root MoneyPuck logger.

    Reads LOG_LEVEL from environment if *level* is not provided.
    Defaults to INFO in production.
    """
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    logger = logging.getLogger("moneypuck")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(numeric_level)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the moneypuck namespace."""
    return logging.getLogger(f"moneypuck.{name}")
