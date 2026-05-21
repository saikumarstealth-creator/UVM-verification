# src/tracking/logger.py — Structured logging setup

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from src.config import LoggingConfig


def setup_logging(cfg: LoggingConfig) -> logging.Logger:
    logger = logging.getLogger("uvmgen")
    logger.setLevel(getattr(logging, cfg.level.upper(), logging.INFO))

    if not logger.handlers:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(getattr(logging, cfg.level.upper(), logging.INFO))
        console.setFormatter(logging.Formatter(cfg.format))
        logger.addHandler(console)

    if cfg.file:
        log_path = Path(cfg.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path))
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(cfg.format))
        logger.addHandler(fh)

    return logger
