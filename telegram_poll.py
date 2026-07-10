"""
NORCET AI Bot - Telegram Poll Module
======================================
Handles creating and posting quiz polls to Telegram,
sending explanations, and managing Telegram rate limits.

Each question follows this flow:
1. Send QuizPoll to channel (anonymous, is_closed=False)
2. Wait for poll_open_duration seconds
3. Send detailed explanation message with correct answer
4. Store message IDs in database
"""

import asyncio
import random
from typing import Optional

from telegram import (
    Bot,
    Update,
    Poll,
    InputPollOption,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut

from config import Config
from logger import log
from utils import (
    escape_html,
    sanitize_text,
    truncate_text,
    randomize_options,
    parse_chat_id,
    format_session_header,
    async_retry,
)
from database import (
    store_question,
    update_poll_message_id,
    update_daily_stats,
    start_post_history,
    update_post_history,
    set_topic_progress,
    get_topic_progress,
)
from gemini import gemini_client
from topic_manager import TopicManager
from duplicate_checker import duplicate_checker
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def format_explanation(question: dict, question_number: int) -> str:
    """
    Format the detailed explanation message for a question.

    Includes:
    - Question number and text
    - All four options with ✓/✗ indicators
    - Detailed rationale for each option
    - NORCET Pearl
    - Reference
    - Difficulty level

    Args:
        question: Question dict with all fields.
        question_number: The question number in the session.

    Returns:
        HTML-formatted string for Telegram message.
    """
    correct = question.get("correct_answer", "A").upper()
    option_labels = {
        "A": ("optionA", "rationaleA"),
        "B": ("optionB", "rationaleB"),
        "C": ("optionC", "rationaleC"),
        "D": ("optionD", "rationaleD"),
    }

    # Question header
    parts = [
        f"<b>Q{question_number}</b>",
        f"{escape_html(question.get('question', ''))}",
        "",
    ]

    # Options with correct/incorrect indicators
    for label, (opt_key, rat_key) in option_labels.items():
        opt_text = question.get(opt_key, "")
        is_correct = label == correct
        indicator = "✅" if is_correct else "❌"
        parts.append(f"{indicator} <b>{label}.</b> {escape_html(opt_text)}")

    parts.append("")
    parts.append("<b>━━━━ Detailed Rationale ━━━━</b>")

    # Rationales for each option
    for label, (opt_key, rat_key) in option_labels.items():
        rationale = question.get(rat_key, "").strip()
        if rationale:
            is_correct = label == correct
            tag = "✅ CORRECT" if is_correct else "❌ INCORRECT"
            parts.append(f"<b>{label}. [{tag}]</b>")
            parts.append(f"<i>{escape_html(rationale)}</i>")
            parts.append("")

    # Pearl
    pearl = question.get("pearl", "").strip()
    if pearl:
        parts.append("<b>💎 NORCET Pearl:</b>")
        parts.append(f"<i>{escape_html(pearl)}</i>")
        parts.append("")

    # Reference
    reference = question.get("reference", "").strip()
    if reference:
        parts.append("<b>📖 Reference:</b>")
        parts.append(f"<i>{escape_html(reference)}</i>")
        parts.append("")

    # Difficulty badge
    difficulty = question.get("difficulty", "Moderate")
    diff_emoji = {"Easy": "🟢", "Moderate": "🟡", "Hard": "🔴"}
    diff_emoji_str = diff_emoji.get(difficulty, "🟡")
    parts.append(f"<b>Difficulty:</b> {diff_emoji_str} {escape_html(difficulty)}")

    return truncate_text("\n".join(parts))


async def send_quiz_poll(
    bot: Bot,
    chat_id: str,
    question: dict,
    question_number: int,
) -> Optional[tuple[int, int]]:
    """
    Send a single quiz poll and its explanation to a Telegram chat.

    Flow:
    1. Send anonymous quiz poll (is_closed=False)
    2. Wait for poll duration
    3. Close the poll
    4. Send explanation message

    Args:
        bot: Telegram Bot instance.
        chat_id: Target chat/channel ID.
        question: Question dict.
        question_number: Question number for display.

    Returns:
        Tuple of (poll_message_id, explanation_message_id) or None on failure.
    """
    correct = question.get("correct_answer", "A").upper()
    options = [
        InputPollOption(
            text=sanitize_text(question.get("optionA", "")),
            text_parse_mode=ParseMode.HTML,
        ),
        InputPollOption(
            text=sanitize_text(question.get("optionB", "")),
            text_parse_mode=ParseMode.HTML,
        ),
        InputPollOption(
            text=sanitize_text(question.get("optionC", "")),
            text_parse_mode=ParseMode.HTML,
        ),
        InputPollOption(
            text=sanitize_text(question.get("optionD", "")),
            text_parse_mode=ParseMode.HTML,
        ),
    ]

    question_text = sanitize_text(question.get("question", ""))

    try:
        # Send the quiz poll
        poll_message = await async_retry(
            bot.send_poll,
            chat_id=chat_id,
            question=question_text,
            options=options,
            type=Poll.QUIZ,
            correct_option_id=_option_index(correct),
            is_anonymous=True,
            is_closed=False,
            open_period=Config.POLL_OPEN_DURATION,
            explanation=None,
            explanation_parse_mode=ParseMode.HTML,
            disable_notification=True,
            max_retries=Config.MAX_TELEGRAM_RETRIES,
            delay=1.0,
            description="send_quiz_poll",
        )

        log.info(
            f"Poll sent (Q{question_number}): msg_id={poll_message.message_id}"
        )

        # Wait for poll to close (it auto-closes after open_period)
        await asyncio.sleep(Config.POLL_OPEN_DURATION + 2)

        # Send explanation
        explanation_text = format_explanation(question, question_number)
        explanation_message = await async_retry(
            bot.send_message,
            chat_id=chat_id,
            text=explanation_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            disable_notification=True,
            max_retries=Config.MAX_TELEGRAM_RETRIES,
            delay=1.0,
            description="send_explanation",
        )

        log.info(
            f"Explanation sent (Q{question_number}): msg_id={explanation_message.message_id}"
        )

        return poll_message.message_id, explanation_message.message_id

    except TelegramError as e:
        log.error(
            f"Failed to send poll Q{question_number}: "
            f"{type(e).__name__}: {e}"
        )
        return None
    except Exception as e:
        log.error(
            f"Unexpected error sending poll Q{question_number}: {e}"
        )
        return None


def _option_index(letter: str) -> int:
    """Convert option letter to index for Telegram Poll API."""
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    return mapping.get(letter.upper(), 0)


async def run_quiz_session(
    bot: Bot,
    topic_manager: TopicManager,
    session_type: str,
) -> dict:
    """
    Run a complete quiz session for the current topic.

    Generates questions via Gemini, posts polls with explanations,
    stores everything in the database, and handles topic advancement.

    Args:
        bot: Telegram Bot instance.
        topic_manager: TopicManager instance.
        session_type: "Morning" or "Evening".

    Returns:
        Dict with session results (questions_posted, topic, etc.)
    """
    topic = topic_manager.current_topic
    questions_needed = Config.QUESTIONS_PER_SESSION
    chat_id = parse_chat_id(Config.QUIZ_CHAT_ID)

    log.info(
        f"Starting {session_type} quiz session: topic='{topic}', "
        f"questions={questions_needed}, chat_id={chat_id}"
    )

    # Create post history entry
    history_id = start_post_history(topic, session_type)

    # Send session header
    header = format_session_header(topic, session_type, questions_needed)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=header,
            parse_mode=ParseMode.HTML,
            disable_notification=False,
        )
        log.info(f"Session header sent for {session_type} session")
    except TelegramError as e:
        log.error(f"Failed to send session header: {e}")

    # Generate questions
    try:
        questions = await gemini_client.generate_batch(
            topic=topic,
            total_count=questions_needed,
        )
    except Exception as e:
        log.error(f"Failed to generate questions: {e}")
        update_post_history(history_id, 0, "failed", str(e))
        return {
            "success": False,
            "topic": topic,
            "session_type": session_type,
            "questions_posted": 0,
            "error": str(e),
        }

    if not questions:
        log.error("No questions generated")
        update_post_history(history_id, 0, "failed", "No questions generated")
        return {
            "success": False,
            "topic": topic,
            "session_type": session_type,
            "questions_posted": 0,
            "error": "No questions generated",
        }

    # Filter duplicates
    questions = duplicate_checker.filter_duplicates(questions)
    if not questions:
        log.error("All generated questions were duplicates")
        update_post_history(history_id, 0, "failed", "All questions were duplicates")
        return {
            "success": False,
            "topic": topic,
            "session_type": session_type,
            "questions_posted": 0,
            "error": "All questions were duplicates",
        }

    # Randomize option order for each question
    questions = [randomize_options(q) for q in questions]

    # Post polls one by one
    posted_questions: list[dict] = []
    failed_count = 0

    for i, question in enumerate(questions, start=1):
        log.info(
            f"Posting poll {i}/{len(questions)} "
            f"[{session_type}] - '{question.get('question', '')[:60]}...'"
        )

        result = await send_quiz_poll(bot, chat_id, question, i)

        if result:
            poll_msg_id, explanation_msg_id = result
            question_id = store_question(question, topic, session_type)
            if question_id:
                update_poll_message_id(question_id, poll_msg_id, explanation_msg_id)
            posted_questions.append(question)
            duplicate_checker.add_to_cache(question.get("question", ""))
        else:
            failed_count += 1

        # Rate limiting: delay between messages
        if i < len(questions):
            await asyncio.sleep(Config.TELEGRAM_RATE_LIMIT + Config.POLL_OPEN_DURATION)

    # Update stats
    posted_count = len(posted_questions)
    date_str = datetime.now(IST).strftime("%Y-%m-%d")

    update_post_history(history_id, posted_count, "completed")
    update_daily_stats(date_str, session_type, posted_questions)
    topic_manager.increment_questions_asked(posted_count)

    # Check if we should advance to next topic
    progress = get_topic_progress()
    questions_asked = progress.get("questions_asked", 0) + posted_count

    # Auto-advance after 100 questions per topic (configurable logic)
    QUESTIONS_PER_TOPIC = 100
    if questions_asked >= QUESTIONS_PER_TOPIC:
        log.info(
            f"Topic '{topic}' has reached {questions_asked} questions. "
            "Advancing to next topic."
        )
        new_topic = topic_manager.advance_to_next_topic()
        # Send topic completion message
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"<b>🎉 Topic Complete!</b>\n\n"
                    f"Finished: <i>{escape_html(topic)}</i>\n"
                    f"Questions covered: {questions_asked}\n\n"
                    f"<b>Next Topic:</b> <i>{escape_html(new_topic)}</i>"
                ),
                parse_mode=ParseMode.HTML,
                disable_notification=False,
            )
        except TelegramError as e:
            log.error(f"Failed to send topic completion message: {e}")

    # Send session summary
    try:
        summary = (
            f"<b>📋 Session Summary — {session_type}</b>\n"
            f"Topic: <i>{escape_html(topic)}</i>\n"
            f"Questions posted: <b>{posted_count}</b>\n"
            f"Failed: {failed_count}\n"
            f"Date: {date_str}"
        )
        await bot.send_message(
            chat_id=chat_id,
            text=summary,
            parse_mode=ParseMode.HTML,
            disable_notification=True,
        )
    except TelegramError as e:
        log.error(f"Failed to send session summary: {e}")

    log.info(
        f"{session_type} session complete: {posted_count} questions posted, "
        f"{failed_count} failed"
    )

    return {
        "success": True,
        "topic": topic,
        "session_type": session_type,
        "questions_posted": posted_count,
        "failed": failed_count,
    }


async def post_immediate_session(bot: Bot, topic_manager: TopicManager) -> dict:
    """
    Trigger an immediate quiz session (bypassing the scheduler).
    Used by the /postnow admin command.

    Args:
        bot: Telegram Bot instance.
        topic_manager: TopicManager instance.

    Returns:
        Session result dict.
    """
    now = datetime.now(IST)
    session_type = "Morning" if now.hour < 12 else "Evening"
    return await run_quiz_session(bot, topic_manager, session_type)
