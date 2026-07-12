"""
NORCET AI Bot - Scheduler Module
======================================
Manages scheduled quiz sessions using APScheduler.

Schedules:
    - Morning session: Config.MORNING_HOUR:MORNING_MINUTE IST
      (Config.QUESTIONS_PER_SESSION MCQ polls — currently 60)
    - Evening session: Config.EVENING_HOUR:EVENING_MINUTE IST
      (Config.QUESTIONS_PER_SESSION MCQ polls — currently 60)
    - 10-minute-before reminder for both sessions

Uses APScheduler's AsyncIOScheduler for seamless integration
with python-telegram-bot's event loop.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

from telegram import Bot

from config import Config
from logger import log
from telegram_poll import run_quiz_session, close_all_open_polls
from topic_manager import TopicManager


IST = timezone(timedelta(hours=5, minutes=30))


def _minus_minutes(hour: int, minute: int, delta: int) -> tuple[int, int]:
    """
    Return (hour, minute) that is `delta` minutes before the given
    hour:minute, wrapping correctly across midnight (e.g. 00:05 minus
    10 -> 23:55 the previous day). Used to schedule the "test starts
    in 10 minutes" reminder relative to the actual session time, so it
    always stays 10 minutes ahead even if MORNING_HOUR/MINUTE change.
    """
    total = (hour * 60 + minute - delta) % (24 * 60)
    return total // 60, total % 60


class QuizScheduler:
    """
    Manages scheduled quiz sessions using APScheduler.

    Integrates with the Telegram Bot event loop via AsyncIOScheduler.
    Handles job execution, error logging, and missed job recovery.
    """

    def __init__(self, bot: Bot, topic_manager: TopicManager) -> None:
        """
        Initialize the scheduler.

        Args:
            bot: Telegram Bot instance.
            topic_manager: TopicManager instance.
        """
        self._bot = bot
        self._topic_manager = topic_manager
        self._scheduler = AsyncIOScheduler(timezone=Config.TIMEZONE)
        self._setup_error_handlers()
        self._setup_jobs()

    def _setup_error_handlers(self) -> None:
        """Set up handlers for scheduler events."""
        self._scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR,
        )
        self._scheduler.add_listener(
            self._on_job_missed,
            EVENT_JOB_MISSED,
        )

    SESSIONS = ("Morning", "Evening")

    def _get_session_time(self, session_type: str) -> tuple[int, int]:
        """
        Get the scheduled hour/minute for a session — a DB-persisted
        override (set via /setschedule) takes priority over the
        Config .env default. This is what lets /setschedule survive a
        restart without needing a redeploy.
        """
        from database import get_setting

        if session_type == "Morning":
            default_h, default_m = Config.MORNING_HOUR, Config.MORNING_MINUTE
        else:
            default_h, default_m = Config.EVENING_HOUR, Config.EVENING_MINUTE

        prefix = session_type.lower()
        hour = int(get_setting(f"{prefix}_hour", str(default_h)))
        minute = int(get_setting(f"{prefix}_minute", str(default_m)))
        return hour, minute

    def _setup_jobs(self) -> None:
        """
        Configure the Morning and Evening quiz session jobs (plus their
        10-minute-before reminders) and the daily poll-closer.
        Jobs use CronTrigger for precise daily scheduling.
        """
        for session_type in self.SESSIONS:
            self._register_session_jobs(session_type)

        # Daily poll-closer — closes every poll posted that day so they
        # stay open "all day" (Telegram's open_period caps at 600s, so
        # this explicit sweep is what makes all-day polls possible).
        self._scheduler.add_job(
            self._run_close_polls,
            trigger=CronTrigger(
                hour=Config.POLL_CLOSE_HOUR,
                minute=Config.POLL_CLOSE_MINUTE,
                timezone=Config.TIMEZONE,
            ),
            id="close_daily_polls",
            name="Close Daily Polls",
            replace_existing=True,
            # 1 hour, not 5 min — a Railway redeploy around this time can
            # take longer than 300s, and a late poll-close is harmless
            # (it's just a cleanup sweep), so a generous grace window
            # costs nothing.
            misfire_grace_time=3600,
            max_instances=1,
        )
        log.info(
            f"Daily poll-close scheduled at "
            f"{Config.POLL_CLOSE_HOUR:02d}:{Config.POLL_CLOSE_MINUTE:02d} {Config.TIMEZONE}"
        )

    def _register_session_jobs(self, session_type: str) -> None:
        """
        Register (or re-register — replace_existing=True) both the
        quiz-session job and its 10-minute-before reminder for one
        session type, using whichever hour/minute is currently active.
        Shared by _setup_jobs() at startup and reschedule_session()
        (used by /setschedule) at runtime.
        """
        hour, minute = self._get_session_time(session_type)
        reminder_hour, reminder_minute = _minus_minutes(hour, minute, 10)
        prefix = session_type.lower()

        self._scheduler.add_job(
            self._run_session_reminder,
            trigger=CronTrigger(
                hour=reminder_hour, minute=reminder_minute, timezone=Config.TIMEZONE
            ),
            id=f"{prefix}_reminder",
            name=f"{session_type} Test Reminder",
            replace_existing=True,
            misfire_grace_time=120,
            max_instances=1,
            kwargs={"session_type": session_type},
        )
        self._scheduler.add_job(
            self._run_session,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=Config.TIMEZONE),
            id=f"{prefix}_quiz",
            name=f"{session_type} Quiz Session",
            replace_existing=True,
            # 1 hour, not 5 min — if a Railway redeploy is in progress
            # right at 7:00 AM and the container only comes back up at
            # 7:20, we still want the session to fire rather than
            # silently skip the whole day.
            misfire_grace_time=3600,
            max_instances=1,
            kwargs={"session_type": session_type},
        )
        log.info(
            f"{session_type} quiz scheduled at {hour:02d}:{minute:02d} {Config.TIMEZONE} "
            f"(reminder at {reminder_hour:02d}:{reminder_minute:02d})"
        )

    def get_current_times(self) -> dict:
        """
        Get the currently effective Morning/Evening times — reflects
        any /setschedule override, not just the Config .env defaults.
        Used by bot.py for the startup message and /schedule command.
        """
        result = {}
        for session_type in self.SESSIONS:
            hour, minute = self._get_session_time(session_type)
            result[session_type.lower()] = (hour, minute)
        return result

    def reschedule_session(self, session_type: str, hour: int, minute: int) -> None:
        """
        Used by the /setschedule admin command. Persists the new time
        to the DB (so it survives restarts) and immediately
        re-registers both the session job and its reminder job — no
        redeploy needed.
        """
        from database import set_setting

        if session_type not in self.SESSIONS:
            raise ValueError(f"session_type must be one of {self.SESSIONS}")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("hour must be 0-23 and minute 0-59")

        prefix = session_type.lower()
        set_setting(f"{prefix}_hour", str(hour))
        set_setting(f"{prefix}_minute", str(minute))
        self._register_session_jobs(session_type)
        log.info(f"{session_type} session rescheduled to {hour:02d}:{minute:02d} {Config.TIMEZONE}")

    async def _run_session(self, session_type: str) -> None:
        """Execute a quiz session (Morning or Evening)."""
        log.info(f"=== {session_type} Quiz Session Started ===")
        try:
            await run_quiz_session(
                bot=self._bot,
                topic_manager=self._topic_manager,
                session_type=session_type,
            )
        except Exception as e:
            log.error(f"{session_type} session failed: {e}", exc_info=True)
            await self._notify_admin(f"{session_type} session failed: {e}")
        finally:
            log.info(f"=== {session_type} Quiz Session Ended ===")

    async def _run_session_reminder(self, session_type: str) -> None:
        """Send the 'test starts in 10 minutes' reminder for a session."""
        await self._send_test_reminder(session_type)

    async def _send_test_reminder(self, session_type: str) -> None:
        """
        Post a pinned "test starts in 10 minutes" reminder to the quiz
        channel, in the same style as other NORCET test-series bots
        (hourglass header, topic line, countdown line, stay-online CTA).

        Best-effort: if the send or pin fails (e.g. bot lacks pin rights
        in the channel), it's logged and swallowed — a missing reminder
        should never block or crash the actual quiz session that follows.
        """
        from utils import escape_html, parse_chat_id

        chat_id = parse_chat_id(Config.QUIZ_CHAT_ID)
        topic = self._topic_manager.current_topic
        text = (
            "\u23f3 <b>TEST REMINDER</b>\n\n"
            f"\U0001f4d8 <b>NORCET Daily Quiz — {session_type} Session</b>\n"
            f"Topic: <i>{escape_html(topic)}</i>\n"
            f"\U0001f550 Your test will begin in 10 minutes "
            f"({Config.QUESTIONS_PER_SESSION} MCQs).\n\n"
            "\U0001f525 Please prepare yourself and stay online!"
        )

        try:
            msg = await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_notification=False,
            )
            log.info(f"{session_type} reminder sent")
        except Exception as e:
            log.error(f"Failed to send {session_type} reminder: {e}", exc_info=True)
            return

        try:
            await self._bot.pin_chat_message(
                chat_id=chat_id,
                message_id=msg.message_id,
                disable_notification=True,
            )
        except Exception as e:
            # Non-fatal — bot may not be admin/lack pin rights in this chat.
            log.warning(f"Could not pin {session_type} reminder: {e}")

    async def _run_close_polls(self) -> None:
        """Execute the daily poll-closing sweep."""
        log.info("=== Daily Poll Close Started ===")
        try:
            result = await close_all_open_polls(self._bot)
            log.info(
                f"Daily poll close: {result['closed']} closed, "
                f"{result['failed']} failed"
            )
        except Exception as e:
            log.error(f"Daily poll close failed: {e}", exc_info=True)
            await self._notify_admin(f"Daily poll close failed: {e}")
        finally:
            log.info("=== Daily Poll Close Ended ===")

    async def _notify_admin(self, message: str) -> None:
        """
        Send an error notification to all configured admin chat IDs.

        Args:
            message: Error message to send.
        """
        from utils import escape_html

        for admin_id in Config.ADMIN_CHAT_IDS:
            try:
                await self._bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ <b>NORCET Bot Alert</b>\n\n{escape_html(message)}",
                    parse_mode="HTML",
                    disable_notification=False,
                )
            except Exception as e:
                log.error(f"Failed to notify admin {admin_id}: {e}")

    def _on_job_error(self, event) -> None:
        """Handle job execution errors."""
        log.error(
            f"Scheduler job error: {event.job_id} - "
            f"{event.exception if hasattr(event, 'exception') else 'Unknown error'}"
        )

    def _on_job_missed(self, event) -> None:
        """
        Handle missed job executions (e.g. Railway redeploy overlapped
        the scheduled time and the misfire_grace_time window already
        passed). For a missed Morning/Evening quiz job, actually
        trigger the session immediately instead of just logging that
        recovery "would" happen — the previous version logged a
        recovery message but never did anything.

        Safe against double-firing: run_quiz_session() already guards
        each session_type with an asyncio.Lock, so if the real cron
        job and this recovery both end up trying to run, only one
        actually executes.
        """
        log.warning(f"Scheduler job missed: {event.job_id}")
        if event.job_id in ("morning_quiz", "evening_quiz"):
            session_type = "Morning" if event.job_id == "morning_quiz" else "Evening"
            log.info(f"Triggering recovery run for missed {session_type} session")
            asyncio.ensure_future(self._run_session(session_type))

    def start(self) -> None:
        """Start the scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()
            log.info("Quiz scheduler started")

            # Print next scheduled runs
            jobs = self._scheduler.get_jobs()
            for job in jobs:
                next_run = job.next_run_time
                if next_run:
                    log.info(
                        f"  Next '{job.name}': {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                    )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log.info("Quiz scheduler stopped")

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """Get the underlying APScheduler instance."""
        return self._scheduler

    def get_jobs_info(self) -> list[dict]:
        """
        Get information about all scheduled jobs.

        Returns:
            List of dicts with job id, name, and next run time.
        """
        jobs_info = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs_info.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S %Z") if next_run else "Not scheduled",
            })
        return jobs_info

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._scheduler.running
