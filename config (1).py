"""
NORCET AI Bot - Configuration Module
======================================
Loads and validates all configuration from environment variables.
Uses python-dotenv for local development.
"""

import os
from dotenv import load_dotenv


def _parse_admin_ids(value: str) -> list[int]:
    """Parse comma-separated admin chat IDs from environment."""
    if not value.strip():
        return []
    ids: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if token:
            try:
                ids.append(int(token))
            except ValueError:
                pass
    return ids


# Load .env file at module import time
load_dotenv()


class Config:
    """Central configuration class. All settings loaded from environment."""

    # ── Telegram ──────────────────────────────────────────────
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_CHAT_IDS: list[int] = _parse_admin_ids(os.getenv("ADMIN_CHAT_IDS", ""))

    # ── Google Gemini ─────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    # ── Scheduler ────────────────────────────────────────────
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    MORNING_HOUR: int = int(os.getenv("MORNING_HOUR", "7"))
    MORNING_MINUTE: int = int(os.getenv("MORNING_MINUTE", "0"))
    EVENING_HOUR: int = int(os.getenv("EVENING_HOUR", "19"))
    EVENING_MINUTE: int = int(os.getenv("EVENING_MINUTE", "0"))
    QUESTIONS_PER_SESSION: int = int(os.getenv("QUESTIONS_PER_SESSION", "60"))
    POLL_OPEN_DURATION: int = int(os.getenv("POLL_OPEN_DURATION", "30"))  # seconds
    SOLUTION_DELAY: int = int(os.getenv("SOLUTION_DELAY", "15"))  # seconds after poll to send solution
    QUESTION_INTERVAL: int = int(os.getenv("QUESTION_INTERVAL", "30"))  # seconds between questions

    # ── Channels ────────────────────────────────────────────
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")  # e.g. "@norcet_quiz" or "-100123456"
    QUIZ_CHAT_ID: str = os.getenv("QUIZ_CHAT_ID", "")  # where polls are posted

    # ── Database ────────────────────────────────────────────
    DB_PATH: str = os.getenv("DB_PATH", "norcet_bot.db")

    # ── Topics ──────────────────────────────────────────────
    TOPICS_FILE: str = os.getenv("TOPICS_FILE", "topics.txt")

    # ── Gemini Generation Settings ────────────────────────────
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))  # questions per API call
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.9"))
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    GEMINI_RETRY_DELAY: int = int(os.getenv("GEMINI_RETRY_DELAY", "5"))  # seconds
    GEMINI_RATE_LIMIT_MAX: int = int(os.getenv("GEMINI_RATE_LIMIT_MAX", "4"))  # max requests per rolling window
    GEMINI_RATE_LIMIT_WINDOW: int = int(os.getenv("GEMINI_RATE_LIMIT_WINDOW", "60"))  # rolling window in seconds

    # ── Telegram Rate Limits ─────────────────────────────────
    TELEGRAM_RATE_LIMIT: float = float(os.getenv("TELEGRAM_RATE_LIMIT", "0.7"))
    MAX_TELEGRAM_RETRIES: int = int(os.getenv("MAX_TELEGRAM_RETRIES", "3"))

    # ── Logging ─────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "norcet_bot.log")

    # ── Difficulty Distribution ──────────────────────────────
    DIFFICULTY_EASY: float = float(os.getenv("DIFFICULTY_EASY", "0.2"))
    DIFFICULTY_MODERATE: float = float(os.getenv("DIFFICULTY_MODERATE", "0.6"))
    DIFFICULTY_HARD: float = float(os.getenv("DIFFICULTY_HARD", "0.2"))

    @classmethod
    def validate(cls) -> list[str]:
        """Validate critical config values. Returns list of error messages."""
        errors: list[str] = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required. Set it in .env or environment.")
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required. Set it in .env or environment.")
        if not cls.QUIZ_CHAT_ID:
            errors.append("QUIZ_CHAT_ID is required. Set the channel/chat ID where polls should be posted.")
        difficulty_sum = cls.DIFFICULTY_EASY + cls.DIFFICULTY_MODERATE + cls.DIFFICULTY_HARD
        if abs(difficulty_sum - 1.0) > 0.01:
            errors.append(
                f"Difficulty weights must sum to 1.0, got {difficulty_sum}"
            )
        return errors
