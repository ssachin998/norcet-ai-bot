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
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    # ── Scheduler ────────────────────────────────────────────
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    MORNING_HOUR: int = int(os.getenv("MORNING_HOUR", "7"))
    MORNING_MINUTE: int = int(os.getenv("MORNING_MINUTE", "0"))
    EVENING_HOUR: int = int(os.getenv("EVENING_HOUR", "19"))
    EVENING_MINUTE: int = int(os.getenv("EVENING_MINUTE", "0"))
    QUESTIONS_PER_SESSION: int = int(os.getenv("QUESTIONS_PER_SESSION", "60"))
    SOLUTION_DELAY: int = int(os.getenv("SOLUTION_DELAY", "15"))  # seconds after poll to reveal solution text (poll stays open — intentional for self-paced learning)
    QUESTION_INTERVAL: int = int(os.getenv("QUESTION_INTERVAL", "30"))  # seconds between posting one question and the next
    # Polls are sent WITHOUT an auto-close timer (Telegram caps open_period
    # at 600s / 10 min, far too short for "open all day"). Instead, a daily
    # job explicitly closes every poll posted that day at this time.
    POLL_CLOSE_HOUR: int = int(os.getenv("POLL_CLOSE_HOUR", "23"))
    POLL_CLOSE_MINUTE: int = int(os.getenv("POLL_CLOSE_MINUTE", "55"))

    # ── Channels ────────────────────────────────────────────
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")  # e.g. "@norcet_quiz" or "-100123456"
    QUIZ_CHAT_ID: str = os.getenv("QUIZ_CHAT_ID", "")  # where polls are posted

    # ── Database ────────────────────────────────────────────
    DB_PATH: str = os.getenv("DB_PATH", "norcet_bot.db")

    # ── Topics ──────────────────────────────────────────────
    TOPICS_FILE: str = os.getenv("TOPICS_FILE", "topics.txt")

    # ── Gemini Generation Settings ────────────────────────────
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "5"))  # questions per API call
    QUESTIONS_PER_TOPIC: int = int(os.getenv("QUESTIONS_PER_TOPIC", "100"))  # advance topic after this many
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.6"))
    # Output token ceiling per Gemini call. Even with BATCH_SIZE=5, a
    # fully-merged MCQ+explanation item (rationales, memory trick, pearl,
    # reference) is verbose — too low a limit truncates the JSON
    # mid-response and makes the whole batch unparseable. 16384 gives
    # comfortable headroom (matches the safety floor in gemini.py's
    # MIN_SAFE_OUTPUT_TOKENS, so both files agree).
    GEMINI_MAX_OUTPUT_TOKENS: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "16384"))
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
        if not cls.ADMIN_CHAT_IDS:
            print(
                "⚠️  WARNING: ADMIN_CHAT_IDS is not set. Admin commands "
                "(/postnow, /skip, /nexttopic, etc.) will be DISABLED for "
                "everyone until this is configured. Set it in Railway/your "
                ".env to your Telegram user ID."
            )
        if not cls.DB_PATH.startswith(("/app/data", "/data", "/mnt")):
            print(
                "⚠️  WARNING: DB_PATH looks like a relative/ephemeral path "
                f"('{cls.DB_PATH}'). On Railway this file is WIPED on every "
                "redeploy — topic progress, duplicate-question history, and "
                "stats will silently reset to zero. Attach a Railway Volume "
                "and set DB_PATH to a path inside it "
                "(e.g. DB_PATH=/app/data/norcet_bot.db) so it persists "
                "across deploys."
            )
        return errors
