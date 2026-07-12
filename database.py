"""
NORCET AI Bot - Database Module
======================================
SQLite database for storing posted questions, topic progress,
post history, and duplicate detection.

Tables:
    - questions: All posted quiz questions with metadata
    - topic_progress: Current position in the topics list
    - post_history: Log of every quiz session
    - duplicates: Hash-based duplicate detection index
    - daily_stats: Per-day statistics
"""

import sqlite3
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from contextlib import contextmanager

from config import Config
from logger import log

IST = timezone(timedelta(hours=5, minutes=30))


@contextmanager
def get_db_connection(db_path: Optional[str] = None):
    """
    Context manager for database connections.
    Ensures connections are properly closed after use.

    Yields:
        sqlite3.Connection object with row_factory set.
    """
    path = db_path or Config.DB_PATH
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_database() -> None:
    """Create all database tables if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                rationale_a TEXT,
                rationale_b TEXT,
                rationale_c TEXT,
                rationale_d TEXT,
                pearl TEXT,
                reference TEXT,
                difficulty TEXT DEFAULT 'Moderate',
                topic TEXT NOT NULL,
                question_hash TEXT UNIQUE NOT NULL,
                session_type TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                poll_message_id INTEGER,
                explanation_message_id INTEGER,
                poll_closed INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Migration: add poll_closed to pre-existing databases that were
        # created before this column existed.
        cursor.execute("PRAGMA table_info(questions)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "poll_closed" not in existing_cols:
            cursor.execute(
                "ALTER TABLE questions ADD COLUMN poll_closed INTEGER NOT NULL DEFAULT 0"
            )
            log.info("Migrated questions table: added poll_closed column")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_progress (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_topic_index INTEGER NOT NULL DEFAULT 0,
                current_topic_name TEXT NOT NULL DEFAULT '',
                topic_completed INTEGER NOT NULL DEFAULT 0,
                questions_asked INTEGER NOT NULL DEFAULT 0,
                questions_total INTEGER NOT NULL DEFAULT 0,
                last_updated TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                session_type TEXT NOT NULL,
                questions_posted INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT DEFAULT 'in_progress',
                error_message TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_hash TEXT UNIQUE NOT NULL,
                question_text TEXT NOT NULL,
                topic TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                questions_posted INTEGER DEFAULT 0,
                morning_session INTEGER DEFAULT 0,
                evening_session INTEGER DEFAULT 0,
                topics_covered TEXT DEFAULT '[]',
                easy_count INTEGER DEFAULT 0,
                moderate_count INTEGER DEFAULT 0,
                hard_count INTEGER DEFAULT 0
            )
        """)

        # Simple key-value store for runtime-changeable settings (e.g.
        # schedule times set via /setschedule) that need to survive a
        # restart. Lives on the same DB / persistent volume as
        # everything else, so it round-trips correctly.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Topics added at runtime via /addtopic. Kept separate from
        # topics.txt so they persist on the DB's volume even if
        # topics.txt itself only lives in the git repo (and would
        # otherwise be overwritten/lost on the next deploy).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                added_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Historical record of topic completions — separate from
        # topic_progress (which only holds the CURRENT state) so that
        # once all topics finish and Round 2 starts, there's still a
        # record of what was covered and when, per cycle.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_completion_log (
                topic_index INTEGER NOT NULL,
                topic_name TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                cycle INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (topic_index, cycle)
            )
        """)

        # Initialize topic_progress row if not exists
        cursor.execute("SELECT COUNT(*) FROM topic_progress")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO topic_progress (id, current_topic_index, current_topic_name)
                VALUES (1, 0, '')
            """)

        conn.commit()
        log.info("Database initialized successfully")


def generate_question_hash(question_text: str) -> str:
    """
    Generate a SHA-256 hash of a question for duplicate detection.
    Normalizes the text before hashing to catch near-duplicates.
    """
    normalized = " ".join(question_text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_duplicate(question_text: str) -> bool:
    """
    Check if a question already exists in the database.

    Args:
        question_text: The question text to check.

    Returns:
        True if the question (or a near-duplicate) already exists.
    """
    question_hash = generate_question_hash(question_text)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM duplicates WHERE question_hash = ?",
            (question_hash,)
        )
        count = cursor.fetchone()[0]
        return count > 0


def store_question(question: dict, topic: str, session_type: str) -> Optional[int]:
    """
    Store a posted question in the database.

    Args:
        question: Question dict with all fields.
        topic: Topic name.
        session_type: "Morning" or "Evening".

    Returns:
        The question ID, or None if it was a duplicate.
    """
    question_hash = generate_question_hash(question["question"])

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO questions (
                    question_text, option_a, option_b, option_c, option_d,
                    correct_answer, rationale_a, rationale_b, rationale_c, rationale_d,
                    pearl, reference, difficulty, topic, question_hash, session_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                question["question"],
                question.get("optionA", ""),
                question.get("optionB", ""),
                question.get("optionC", ""),
                question.get("optionD", ""),
                question.get("correct_answer", "A"),
                question.get("rationaleA", ""),
                question.get("rationaleB", ""),
                question.get("rationaleC", ""),
                question.get("rationaleD", ""),
                question.get("pearl", ""),
                question.get("reference", ""),
                question.get("difficulty", "Moderate"),
                topic,
                question_hash,
                session_type,
            ))

            # Also insert into duplicates table
            cursor.execute("""
                INSERT OR IGNORE INTO duplicates (question_hash, question_text, topic)
                VALUES (?, ?, ?)
            """, (question_hash, question["question"], topic))

            conn.commit()
            question_id = cursor.lastrowid
            log.debug(f"Stored question ID {question_id}: {question['question'][:50]}...")
            return question_id
        except sqlite3.IntegrityError:
            log.warning(f"Duplicate question skipped: {question['question'][:50]}...")
            return None


def get_open_poll_ids() -> list[tuple[int, int]]:
    """
    Get all (question_id, poll_message_id) pairs for polls that haven't
    been closed yet. Used by the daily job that closes all of today's
    polls at end-of-day.

    Returns:
        List of (question_id, poll_message_id) tuples.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, poll_message_id FROM questions
            WHERE poll_closed = 0 AND poll_message_id IS NOT NULL
        """)
        return [(row["id"], row["poll_message_id"]) for row in cursor.fetchall()]


def mark_polls_closed(question_ids: list[int]) -> None:
    """
    Mark a batch of questions' polls as closed, so they're not
    re-processed by future daily-close runs.

    Args:
        question_ids: List of question IDs whose polls were closed.
    """
    if not question_ids:
        return
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            "UPDATE questions SET poll_closed = 1 WHERE id = ?",
            [(qid,) for qid in question_ids],
        )
        conn.commit()
        log.info(f"Marked {len(question_ids)} polls as closed")


def update_poll_message_id(question_id: int, poll_message_id: int, explanation_message_id: int) -> None:
    """
    Update a question record with the Telegram message IDs
    for the poll and explanation messages.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE questions
            SET poll_message_id = ?, explanation_message_id = ?
            WHERE id = ?
        """, (poll_message_id, explanation_message_id, question_id))
        conn.commit()


def get_topic_progress() -> dict:
    """
    Get the current topic progress from the database.

    Returns:
        Dict with keys: current_topic_index, current_topic_name,
        topic_completed, questions_asked, questions_total, last_updated.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM topic_progress WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {
            "current_topic_index": 0,
            "current_topic_name": "",
            "topic_completed": 0,
            "questions_asked": 0,
            "questions_total": 0,
            "last_updated": None,
        }


def set_topic_progress(index: int, topic_name: str, questions_asked: int = 0,
                       questions_total: int = 0,
                       topic_completed: Optional[int] = None) -> None:
    """
    Update the topic progress in the database.

    Args:
        index: Current topic index in the topics list.
        topic_name: Name of the current topic.
        questions_asked: Questions asked for this topic so far.
        questions_total: Estimated total questions for this topic.
        topic_completed: If given (0 or 1), explicitly sets the
            completed flag. If None (default), the existing value in
            the DB is left untouched. This matters because this
            function is also called from increment_questions_asked()
            after every batch — without this, every question-count
            update was silently forcing topic_completed back to 0,
            even moments after mark_topic_completed() had set it to 1.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if topic_completed is None:
            cursor.execute("""
                UPDATE topic_progress
                SET current_topic_index = ?,
                    current_topic_name = ?,
                    questions_asked = ?,
                    questions_total = ?,
                    last_updated = datetime('now')
                WHERE id = 1
            """, (index, topic_name, questions_asked, questions_total))
        else:
            cursor.execute("""
                UPDATE topic_progress
                SET current_topic_index = ?,
                    current_topic_name = ?,
                    questions_asked = ?,
                    questions_total = ?,
                    topic_completed = ?,
                    last_updated = datetime('now')
                WHERE id = 1
            """, (index, topic_name, questions_asked, questions_total, topic_completed))
        conn.commit()
        log.info(f"Topic progress updated: index={index}, topic='{topic_name}'")


def mark_topic_completed(index: int) -> None:
    """
    Mark the current topic as completed and move to the next one.

    Args:
        index: The topic index that was completed.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE topic_progress
            SET topic_completed = 1,
                last_updated = datetime('now')
            WHERE current_topic_index = ?
        """, (index,))
        conn.commit()
        log.info(f"Topic at index {index} marked as completed")


def log_topic_completion(topic_index: int, topic_name: str, cycle: int = 1) -> None:
    """
    Record that a topic was completed, on a given cycle (Round 1, 2, ...).

    Safe to call more than once for the same (topic_index, cycle) —
    the PRIMARY KEY makes it idempotent (INSERT OR IGNORE), so a retry
    or duplicate call won't error out or overwrite the original
    completion timestamp.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO topic_completion_log
                (topic_index, topic_name, completed_at, cycle)
            VALUES (?, ?, datetime('now'), ?)
        """, (topic_index, topic_name, cycle))
        conn.commit()
        log.info(f"Topic completion logged: '{topic_name}' (cycle {cycle})")


def get_topic_completion_history(topic_name: Optional[str] = None) -> list[dict]:
    """
    Get completion history, optionally filtered to one topic name.
    Ordered most-recent-first — useful for e.g. "when did I last cover
    this topic" once Round 2+ is underway.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if topic_name:
            cursor.execute("""
                SELECT topic_index, topic_name, completed_at, cycle
                FROM topic_completion_log
                WHERE topic_name = ?
                ORDER BY completed_at DESC
            """, (topic_name,))
        else:
            cursor.execute("""
                SELECT topic_index, topic_name, completed_at, cycle
                FROM topic_completion_log
                ORDER BY completed_at DESC
            """)
        return [dict(row) for row in cursor.fetchall()]


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a persisted runtime setting (e.g. 'morning_hour').

    Returns the stored string value, or `default` if not set. Callers
    are responsible for converting to int/etc as needed.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """Persist a runtime setting (e.g. schedule times set via /setschedule)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bot_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
        """, (key, str(value)))
        conn.commit()
        log.info(f"Setting updated: {key} = {value}")


def add_custom_topic(name: str) -> bool:
    """
    Persist a topic added at runtime via /addtopic.

    Returns:
        True if added, False if it already existed.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO custom_topics (name) VALUES (?)", (name,)
            )
            conn.commit()
            log.info(f"Custom topic added: '{name}'")
            return True
        except sqlite3.IntegrityError:
            return False


def get_custom_topics() -> list[str]:
    """Get all topics added at runtime via /addtopic, in the order added."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM custom_topics ORDER BY id ASC")
        return [row["name"] for row in cursor.fetchall()]


def start_post_history(topic: str, session_type: str) -> int:
    """
    Create a new post history entry for a quiz session.

    Args:
        topic: Topic name.
        session_type: "Morning" or "Evening".

    Returns:
        The post history ID.
    """
    now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO post_history (topic, session_type, questions_posted, started_at, status)
            VALUES (?, ?, 0, ?, 'in_progress')
        """, (topic, session_type, now_ist))
        conn.commit()
        return cursor.lastrowid


def update_post_history(history_id: int, questions_posted: int,
                        status: str = "completed", error_message: str = "") -> None:
    """
    Update a post history entry after a session completes.

    Args:
        history_id: The post history entry ID.
        questions_posted: Number of questions actually posted.
        status: "completed" or "failed".
        error_message: Error message if session failed.
    """
    now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE post_history
            SET questions_posted = ?,
                completed_at = ?,
                status = ?,
                error_message = ?
            WHERE id = ?
        """, (questions_posted, now_ist, status, error_message, history_id))
        conn.commit()


def update_daily_stats(date_str: str, session_type: str, questions: list) -> None:
    """
    Update daily statistics for a given date.

    Args:
        date_str: Date in YYYY-MM-DD format.
        session_type: "Morning" or "Evening".
        questions: List of question dicts posted in this session.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if record exists
        cursor.execute("SELECT * FROM daily_stats WHERE date = ?", (date_str,))
        row = cursor.fetchone()

        easy = sum(1 for q in questions if q.get("difficulty", "").lower() == "easy")
        moderate = sum(1 for q in questions if q.get("difficulty", "").lower() == "moderate")
        hard = sum(1 for q in questions if q.get("difficulty", "").lower() == "hard")

        if row:
            existing = dict(row)
            topics_covered = json.loads(existing["topics_covered"])
            topic_names = list(set(topics_covered + [q.get("topic", "") for q in questions]))
            cursor.execute("""
                UPDATE daily_stats
                SET questions_posted = questions_posted + ?,
                    morning_session = morning_session + ?,
                    evening_session = evening_session + ?,
                    topics_covered = ?,
                    easy_count = easy_count + ?,
                    moderate_count = moderate_count + ?,
                    hard_count = hard_count + ?
                WHERE date = ?
            """, (
                len(questions),
                1 if session_type == "Morning" else 0,
                1 if session_type == "Evening" else 0,
                json.dumps(topic_names),
                easy, moderate, hard,
                date_str,
            ))
        else:
            topic_names = list(set([q.get("topic", "") for q in questions]))
            cursor.execute("""
                INSERT INTO daily_stats (
                    date, questions_posted, morning_session, evening_session,
                    topics_covered, easy_count, moderate_count, hard_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str,
                len(questions),
                1 if session_type == "Morning" else 0,
                1 if session_type == "Evening" else 0,
                json.dumps(topic_names),
                easy, moderate, hard,
            ))
        conn.commit()


def get_daily_stats(date_str: str) -> Optional[dict]:
    """Get daily statistics for a specific date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_stats WHERE date = ?", (date_str,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result["topics_covered"] = json.loads(result["topics_covered"])
            return result
        return None


def get_weekly_stats(week_start: str) -> list[dict]:
    """
    Get daily stats for a week starting from the given date.

    Args:
        week_start: Date in YYYY-MM-DD format.

    Returns:
        List of daily stat dicts.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM daily_stats
            WHERE date >= ? AND date < date(?, '+7 days')
            ORDER BY date ASC
        """, (week_start, week_start))
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            result["topics_covered"] = json.loads(result["topics_covered"])
            results.append(result)
        return results


def get_monthly_stats(month: str) -> list[dict]:
    """
    Get daily stats for a specific month.

    Args:
        month: Month in YYYY-MM format.

    Returns:
        List of daily stat dicts.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM daily_stats
            WHERE date LIKE ? || '-%'
            ORDER BY date ASC
        """, (month,))
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            result["topics_covered"] = json.loads(result["topics_covered"])
            results.append(result)
        return results


def get_total_questions_posted() -> int:
    """Get the total number of questions ever posted."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions")
        return cursor.fetchone()[0]


def get_questions_count_by_difficulty() -> dict:
    """Get question counts grouped by difficulty."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT difficulty, COUNT(*) as count
            FROM questions
            GROUP BY difficulty
        """)
        return {row["difficulty"]: row["count"] for row in cursor.fetchall()}


def get_topics_covered_count() -> int:
    """Get the number of unique topics that have had questions posted."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT topic) FROM questions")
        return cursor.fetchone()[0]


def get_all_question_hashes() -> set[str]:
    """
    Get all question hashes from the database for batch duplicate checking.

    Returns:
        Set of all question hashes.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT question_hash FROM duplicates")
        return {row["question_hash"] for row in cursor.fetchall()}


def get_topic_completion_percentage(topic_index: int, total_topics: int) -> float:
    """
    Calculate the overall topic completion percentage.

    Args:
        topic_index: Current topic index.
        total_topics: Total number of topics.

    Returns:
        Percentage complete (0-100).
    """
    if total_topics == 0:
        return 0.0
    return round((topic_index / total_topics) * 100, 1)
