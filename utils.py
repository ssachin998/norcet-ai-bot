"""
NORCET AI Bot - Utilities Module
======================================
Helper functions used across the project.
"""

import random
import re
import html
import asyncio
from typing import Any

from logger import log


def escape_html(text: str) -> str:
    """
    Escape special characters for Telegram HTML parse_mode.
    Telegram supports: &lt; &gt; &amp; &quot;
    """
    text = html.escape(str(text), quote=True)
    return text


def sanitize_text(text: str) -> str:
    """
    Clean up text that may contain unwanted formatting.
    Strips excessive whitespace, normalizes line breaks, removes
    markdown-style formatting that could conflict with Telegram HTML.
    """
    if not text:
        return ""
    # Remove markdown bold/italic markers
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def truncate_text(text: str, max_length: int = 4096) -> str:
    """
    Truncate text to fit within Telegram message limits.
    Telegram's maximum message length is 4096 characters.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 20] + "\n\n[...truncated]"


def truncate_poll_text(text: str, max_length: int) -> str:
    """
    Truncate poll question/option text to Telegram's hard limits.

    Telegram enforces: poll question <= 300 chars, poll option <= 100 chars.
    Unlike truncate_text() (used for regular messages, limit 4096), this
    keeps the cut short and clean so quiz polls never get rejected by
    Telegram's BadRequest "length must not exceed N" error.
    """
    text = (text or "").strip()
    if len(text) <= max_length:
        return text
    return text[:max_length - 1].rstrip() + "…"


def randomize_options(question: dict[str, Any]) -> dict[str, Any]:
    """
    Randomize the order of options in a question while keeping
    correct_answer mapped correctly.

    Expects keys: optionA, optionB, optionC, optionD, rationaleA-D
    Returns a new dict with shuffled options labeled A-D.
    """
    options = [
        {"label": "A", "text": question.get("optionA", ""), "rationale": question.get("rationaleA", "")},
        {"label": "B", "text": question.get("optionB", ""), "rationale": question.get("rationaleB", "")},
        {"label": "C", "text": question.get("optionC", ""), "rationale": question.get("rationaleC", "")},
        {"label": "D", "text": question.get("optionD", ""), "rationale": question.get("rationaleD", "")},
    ]

    original_correct = question.get("correct_answer", "A").strip().upper()
    # Map original labels to index
    label_to_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
    correct_idx = label_to_idx.get(original_correct, 0)
    correct_text = options[correct_idx]["text"]

    # Shuffle
    random.shuffle(options)

    # Rebuild with new labels and find new correct answer
    new_labels = ["A", "B", "C", "D"]
    new_correct = "A"
    for i, opt in enumerate(options):
        if opt["text"] == correct_text:
            new_correct = new_labels[i]
            break

    result = {
        "question": question.get("question", ""),
        "optionA": options[0]["text"],
        "optionB": options[1]["text"],
        "optionC": options[2]["text"],
        "optionD": options[3]["text"],
        "rationaleA": options[0]["rationale"],
        "rationaleB": options[1]["rationale"],
        "rationaleC": options[2]["rationale"],
        "rationaleD": options[3]["rationale"],
        "correct_answer": new_correct,
        "pearl": question.get("pearl", ""),
        "reference": question.get("reference", ""),
        "difficulty": question.get("difficulty", "Moderate"),
    }
    return result


def parse_chat_id(raw_id: str) -> str:
    """
    Parse a chat ID string to ensure it's properly formatted for Telegram API.
    Handles @username, -100xxxxx (supergroups), and plain numeric IDs.
    """
    raw_id = raw_id.strip()
    if raw_id.startswith("@"):
        return raw_id
    try:
        return str(int(raw_id))
    except ValueError:
        log.warning(f"Invalid chat ID format: {raw_id}")
        return raw_id


def generate_difficulty_distribution(count: int) -> list[str]:
    """
    Generate a list of difficulty labels matching the configured distribution.

    Args:
        count: Number of difficulty labels to generate.

    Returns:
        List of "Easy", "Moderate", or "Hard" strings.
    """
    from config import Config

    easy_count = round(count * Config.DIFFICULTY_EASY)
    hard_count = round(count * Config.DIFFICULTY_HARD)
    moderate_count = count - easy_count - hard_count

    distribution: list[str] = []
    distribution.extend(["Easy"] * easy_count)
    distribution.extend(["Moderate"] * moderate_count)
    distribution.extend(["Hard"] * hard_count)

    random.shuffle(distribution)
    return distribution


async def async_retry(
    func,
    *args,
    max_retries: int = 3,
    delay: float = 5.0,
    description: str = "operation",
    **kwargs,
) -> Any:
    """
    Execute an async function with automatic retry on failure.

    Args:
        func: Async callable to execute.
        *args: Positional arguments for func.
        max_retries: Maximum number of retry attempts.
        delay: Delay between retries in seconds.
        description: Human-readable description for logging.
        **kwargs: Keyword arguments for func.

    Returns:
        The return value of func on success.

    Raises:
        Exception: If all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            log.warning(
                f"{description} failed (attempt {attempt}/{max_retries}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(delay * attempt)  # Exponential backoff
    log.error(f"{description} failed after {max_retries} retries")
    raise last_exc  # type: ignore


def format_session_header(topic: str, session_type: str, count: int) -> str:
    """
    Generate the header message for a quiz session.

    Args:
        topic: Current topic name.
        session_type: "Morning" or "Evening".
        count: Number of questions in this session.
    """
    from config import Config

    return (
        f"<b>NORCET Daily Quiz — {session_type} Session</b>\n"
        f"<b>Topic:</b> <i>{escape_html(topic)}</i>\n"
        f"<b>Questions:</b> {count} MCQs\n"
        f"<b>Polls stay open until:</b> {Config.POLL_CLOSE_HOUR:02d}:{Config.POLL_CLOSE_MINUTE:02d} IST tonight\n\n"
        f"<i>Answer anytime today. Explanations follow ~{Config.SOLUTION_DELAY}s after each poll.</i>"
    )
