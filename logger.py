"""
NORCET AI Bot - Logger Module
======================================
Configures structured logging with both console and file handlers.
Uses a custom formatter for readability.
"""

import logging
import sys
from datetime import datetime, timezone, timedelta
from config import Config

# India timezone offset
IST = timezone(timedelta(hours=5, minutes=30))


class ISTFormatter(logging.Formatter):
    """Custom formatter that timestamps logs in IST (Asia/Kolkata)."""

    def format(self, record: logging.LogRecord) -> str:
        now = datetime.now(IST)
        record.ist_time = now.strftime("%Y-%m-%d %H:%M:%S")
        return super().format(record)


def setup_logger(name: str = "norcet_bot") -> logging.Logger:
    """
    Create and configure the application logger.

    Returns a logger with both console (stdout) and file handlers.
    File handler uses append mode and includes daily rotation indication.
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))

    # ── Console Handler ─────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_fmt = ISTFormatter(
        fmt="%(ist_time)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    console_handler.setFormatter(console_fmt)

    # ── File Handler ────────────────────────────────────────
    file_handler = logging.FileHandler(Config.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = ISTFormatter(
        fmt="%(ist_time)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
    )
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Module-level logger instance for use across the project
log = setup_logger()
