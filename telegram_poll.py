"""
NORCET AI Bot - Telegram Poll Module
======================================
Batched question generation, interleaved posting.

Session timing:
  Every Config.BATCH_SIZE questions (default 10), ONE Gemini call
  fetches a whole batch of fully-merged question+explanation dicts.
  Posting to Telegram still happens on the normal 30s cadence per
  question — only the *generation* is batched, not the posting.

  Example with BATCH_SIZE=10, 60 questions/session:
    1 batch call  → 10 questions ready
    → post Q1 (poll @0s, solution @15s)
    → post Q2 (poll @30s, solution @45s)
    ... (all 10 posted from the cached batch, 0 extra API calls)
    1 batch call  → next 10 questions ready
    ... repeat

Total API calls per session: 60 / BATCH_SIZE = 6 (with BATCH_SIZE=10),
instead of 120 (2 calls × 60 questions) with the old per-question flow.
"""

import asyncio
import random
import time
from typing import Optional

from telegram import (
    Bot,
    Poll,
    InputPollOption,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

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
    generate_difficulty_distribution,
)
from database import (
    store_question,
    update_poll_message_id,
    update_daily_stats,
    start_post_history,
    update_post_history,
    get_topic_progress,
)
from gemini import gemini_client, GeminiRateLimiter
from topic_manager import TopicManager
from duplicate_checker import duplicate_checker
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


# ── Solution Formatter ───────────────────────────────────────

def format_solution(question: dict, question_number: int) -> str:
    """
    Format the solution message.

    Visible: header line + difficulty badge.
    Hidden (inside spoiler): everything else.

    Inside the spoiler:
      ✔ Correct Answer
      ✔ Why correct option is correct
      ✔ Why every wrong option is wrong
      ✔ NORCET memory trick
      ✔ High-yield exam point
    """
    correct = question.get("correct_answer", "A").upper()
    option_labels = ["A", "B", "C", "D"]
    option_keys = ["optionA", "optionB", "optionC", "optionD"]
    rationale_keys = ["rationaleA", "rationaleB", "rationaleC", "rationaleD"]
    correct_idx = option_labels.index(correct)

    parts: list[str] = [
        f"\U0001f4a1 <b>Solution Q{question_number}</b>",
        "",
        '<span class="tg-spoiler">',
    ]

    # ✔ Correct answer
    correct_text = question.get(option_keys[correct_idx], "")
    parts.append(f"\u2714\ufe0f <b>Correct Answer: {correct}.</b> {escape_html(correct_text)}")
    parts.append("")

    # ✔ Why correct
    correct_rationale = question.get(rationale_keys[correct_idx], "").strip()
    if correct_rationale:
        parts.append("\u2714\ufe0f <b>Why {correct} is correct:</b>")
        parts.append(f"<i>{escape_html(correct_rationale)}</i>")
        parts.append("")

    # ✔ Why each wrong option is wrong
    for label, opt_key, rat_key in zip(option_labels, option_keys, rationale_keys):
        if label != correct:
            rationale = question.get(rat_key, "").strip()
            parts.append(f"\u2714\ufe0f <b>Why Option {label} is wrong:</b>")
            if rationale:
                parts.append(f"<i>{escape_html(rationale)}</i>")
            else:
                opt_text = question.get(opt_key, "")
                parts.append(f"<i>{escape_html(opt_text)} is incorrect.</i>")
            parts.append("")

    # ✔ Memory trick / NORCET exam trick
    memory_trick = question.get("memory_trick", "").strip()
    if memory_trick:
        parts.append("\u2714\ufe0f <b>NORCET Memory Trick:</b>")
        parts.append(f"<i>{escape_html(memory_trick)}</i>")
        parts.append("")

    # ✔ High-yield exam point
    pearl = question.get("pearl", "").strip()
    if pearl:
        parts.append("\u2714\ufe0f <b>High-Yield Exam Point:</b>")
        parts.append(f"<i>{escape_html(pearl)}</i>")
        parts.append("")

    # Reference
    reference = question.get("reference", "").strip()
    if reference:
        parts.append(f"\U0001f4d6 <b>Reference:</b> <i>{escape_html(reference)}</i>")
        parts.append("")

    parts.append("</span>")

    # Visible difficulty footer
    difficulty = question.get("difficulty", "Moderate")
    diff_emoji = {"Easy": "\U0001f7e2", "Moderate": "\U0001f7e1", "Hard": "\U0001f534"}
    parts.append(f"<b>Difficulty:</b> {diff_emoji.get(difficulty, '\U0001f7e1')} {escape_html(difficulty)}")

    return truncate_text("\n".join(parts))


# ── Send Poll ────────────────────────────────────────────────

async def _send_poll(
    bot: Bot,
    chat_id: str,
    question: dict,
    question_number: int,
) -> Optional[int]:
    """
    Send one QuizPoll to Telegram. Returns the message_id on success.
    """
    correct = question.get("correct_answer", "A").upper()
    options = [
        InputPollOption(text=sanitize_text(question.get("optionA", "")), text_parse_mode=ParseMode.HTML),
        InputPollOption(text=sanitize_text(question.get("optionB", "")), text_parse_mode=ParseMode.HTML),
        InputPollOption(text=sanitize_text(question.get("optionC", "")), text_parse_mode=ParseMode.HTML),
        InputPollOption(text=sanitize_text(question.get("optionD", "")), text_parse_mode=ParseMode.HTML),
    ]

    msg = await async_retry(
        bot.send_poll,
        chat_id=chat_id,
        question=sanitize_text(question.get("question", "")),
        options=options,
        type=Poll.QUIZ,
        correct_option_id=_option_index(correct),
        is_anonymous=True,
        is_closed=False,
        open_period=Config.QUESTION_INTERVAL,
        explanation=None,
        explanation_parse_mode=ParseMode.HTML,
        disable_notification=True,
        max_retries=Config.MAX_TELEGRAM_RETRIES,
        delay=1.0,
        description=f"send_poll_Q{question_number}",
    )
    log.info(f"Poll sent (Q{question_number}): msg_id={msg.message_id}")
    return msg.message_id


# ── Send Solution ────────────────────────────────────────────

async def _send_solution(
    bot: Bot,
    chat_id: str,
    question: dict,
    question_number: int,
) -> Optional[int]:
    """
    Send the solution message (with spoiler) to Telegram.
    """
    text = format_solution(question, question_number)
    msg = await async_retry(
        bot.send_message,
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        disable_notification=True,
        max_retries=Config.MAX_TELEGRAM_RETRIES,
        delay=1.0,
        description=f"send_solution_Q{question_number}",
    )
    log.info(f"Solution sent (Q{question_number}): msg_id={msg.message_id}")
    return msg.message_id


def _option_index(letter: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3}.get(letter.upper(), 0)


# ── Single Question Post (no generation — question already in hand) ──

async def _post_one_question(
    bot: Bot,
    chat_id: str,
    question: dict,
    question_number: int,
    session_type: str,
    topic: str,
) -> Optional[dict]:
    """
    Post ONE already-generated (question+explanation merged) dict to
    Telegram, on the normal 30-second cadence.

    Unlike the old _run_one_question, this makes NO Gemini API calls —
    the question dict was already produced by a batch call earlier.

    Timeline:
      00s → Telegram sends QuizPoll
      15s → Telegram sends Solution spoiler

    Returns the question dict if successful, None if failed.
    On failure the session continues to the next question — never cancels.
    """
    q_start = time.monotonic()
    try:
        # Duplicate check — if it's a dup, just skip it (no regeneration,
        # to avoid burning an extra API call outside the batch).
        if duplicate_checker.is_duplicate(question.get("question", "")):
            log.info(f"Q{question_number}: Duplicate detected, skipping (no regen).")
            return None

        # Randomize option order
        question = randomize_options(question)

        # ── 00s: Send poll ─────────────────────────────────
        poll_msg_id = await _send_poll(bot, chat_id, question, question_number)
        if poll_msg_id is None:
            log.error(f"Q{question_number}: Failed to send poll. Skipping to next.")
            return None

        # ── 15s: Wait until solution time ─────────────────
        elapsed_so_far = time.monotonic() - q_start
        time_to_solution = Config.SOLUTION_DELAY - elapsed_so_far
        if time_to_solution > 0:
            await asyncio.sleep(time_to_solution)

        # ── 15s: Send solution ────────────────────────────
        sol_msg_id = await _send_solution(bot, chat_id, question, question_number)

        # ── Store in database ──────────────────────────────
        if poll_msg_id is not None:
            q_id = store_question(question, topic, session_type)
            if q_id and sol_msg_id is not None:
                update_poll_message_id(q_id, poll_msg_id, sol_msg_id)
            duplicate_checker.add_to_cache(question.get("question", ""))

        return question

    except Exception as e:
        log.error(
            f"Q{question_number}: Post cycle failed: {type(e).__name__}: {e}. "
            "Skipping to next question."
        )
        return None


# ── Full Session ────────────────────────────────────────────

async def run_quiz_session(
    bot: Bot,
    topic_manager: TopicManager,
    session_type: str,
) -> dict:
    """
    Run a complete 30-minute quiz session (60 questions).

    For each question:
      1. Generate ONE MCQ via Gemini  (rate-limited, HTTP 429 retried)
      2. Send QuizPoll to Telegram
      3. Generate ONE explanation via Gemini  (rate-limited, HTTP 429 retried)
      4. Send Solution spoiler to Telegram
      5. Fill remaining time to maintain 30s cadence

    No preloading. No batching. No caching.
    """
    topic = topic_manager.current_topic
    total_questions = Config.QUESTIONS_PER_SESSION
    chat_id = parse_chat_id(Config.QUIZ_CHAT_ID)

    log.info(
        f"Starting {session_type} session: topic='{topic}', "
        f"questions={total_questions}, chat_id={chat_id}"
    )

    history_id = start_post_history(topic, session_type)

    # Send session header
    header = format_session_header(topic, session_type, total_questions)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=header,
            parse_mode=ParseMode.HTML,
            disable_notification=False,
        )
    except TelegramError as e:
        log.error(f"Failed to send session header: {e}")

    # Pre-compute difficulty distribution for the session
    difficulties = generate_difficulty_distribution(total_questions)

    # ── Main loop: fetch in batches, post one-by-one on cadence ──
    posted_questions: list[dict] = []
    failed_count = 0
    batch_size = max(1, Config.BATCH_SIZE)

    for batch_start in range(0, total_questions, batch_size):
        batch_end = min(batch_start + batch_size, total_questions)
        batch_difficulties = difficulties[batch_start:batch_end]

        log.info(
            f"[{session_type}] Fetching batch: questions "
            f"{batch_start + 1}-{batch_end} ({len(batch_difficulties)} q) "
            f"— 1 Gemini call"
        )
        try:
            batch_questions = await gemini_client.generate_question_batch(
                topic=topic,
                difficulties=batch_difficulties,
            )
        except Exception as e:
            log.error(
                f"[{session_type}] Batch fetch failed for questions "
                f"{batch_start + 1}-{batch_end}: {type(e).__name__}: {e}. "
                "Skipping this batch."
            )
            failed_count += len(batch_difficulties)
            continue

        if len(batch_questions) < len(batch_difficulties):
            failed_count += len(batch_difficulties) - len(batch_questions)

        for i, question in enumerate(batch_questions):
            q_num = batch_start + i + 1
            q_cycle_start = time.monotonic()

            log.info(
                f"[{session_type}] Q{q_num}/{total_questions} "
                f"(difficulty={question.get('difficulty', '?')}) — posting"
            )

            posted = await _post_one_question(
                bot=bot,
                chat_id=chat_id,
                question=question,
                question_number=q_num,
                session_type=session_type,
                topic=topic,
            )

            if posted:
                posted_questions.append(posted)
            else:
                failed_count += 1

            # ── Fill remaining time to hit 30-second cadence ────
            is_last_overall = (batch_start + i + 1) >= total_questions
            if not is_last_overall:
                elapsed = time.monotonic() - q_cycle_start
                remaining = Config.QUESTION_INTERVAL - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)

    # ── Session wrap-up ────────────────────────────────────
    posted_count = len(posted_questions)
    date_str = datetime.now(IST).strftime("%Y-%m-%d")

    update_post_history(history_id, posted_count, "completed")
    update_daily_stats(date_str, session_type, posted_questions)
    topic_manager.increment_questions_asked(posted_count)

    # Topic advancement
    progress = get_topic_progress()
    questions_asked = progress.get("questions_asked", 0) + posted_count
    QUESTIONS_PER_TOPIC = 100
    if questions_asked >= QUESTIONS_PER_TOPIC:
        log.info(
            f"Topic '{topic}' reached {questions_asked} questions. Advancing."
        )
        new_topic = topic_manager.advance_to_next_topic()
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"<b>\U0001f389 Topic Complete!</b>\n\n"
                    f"Finished: <i>{escape_html(topic)}</i>\n"
                    f"Questions covered: {questions_asked}\n\n"
                    f"<b>Next Topic:</b> <i>{escape_html(new_topic)}</i>"
                ),
                parse_mode=ParseMode.HTML,
                disable_notification=False,
            )
        except TelegramError as e:
            log.error(f"Failed to send topic completion message: {e}")

    # Session summary
    try:
        summary = (
            f"<b>\U0001f4cb Session Summary — {session_type}</b>\n"
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
        f"{session_type} session complete: {posted_count} posted, "
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
    """Trigger an immediate quiz session (used by /postnow)."""
    now = datetime.now(IST)
    session_type = "Morning" if now.hour < 12 else "Evening"
    return await run_quiz_session(bot, topic_manager, session_type)
