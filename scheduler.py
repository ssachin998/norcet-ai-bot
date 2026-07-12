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

    def _setup_jobs(self) -> None:
        """
        Configure the morning and evening quiz session jobs.
        Jobs use CronTrigger for precise daily scheduling.
        """
        # Morning "test starts in 10 minutes" reminder
        morning_reminder_hour, morning_reminder_minute = _minus_minutes(
            Config.MORNING_HOUR, Config.MORNING_MINUTE, 10
        )
        self._scheduler.add_job(
            self._run_morning_reminder,
            trigger=CronTrigger(
                hour=morning_reminder_hour,
                minute=morning_reminder_minute,
                timezone=Config.TIMEZONE,
            ),
            id="morning_reminder",
            name="Morning Test Reminder",
            replace_existing=True,
            misfire_grace_time=120,
            max_instances=1,
        )
        log.info(
            f"Morning reminder scheduled at "
            f"{morning_reminder_hour:02d}:{morning_reminder_minute:02d} {Config.TIMEZONE}"
        )

        # Morning quiz session
        self._scheduler.add_job(
            self._run_morning_session,
            trigger=CronTrigger(
                hour=Config.MORNING_HOUR,
                minute=Config.MORNING_MINUTE,
                timezone=Config.TIMEZONE,
            ),
            id="morning_quiz",
            name="Morning Quiz Session",
            replace_existing=True,
            misfire_grace_time=300,  # 5-minute grace for missed jobs
            max_instances=1,  # Prevent overlapping sessions
        )
        log.info(
            f"Morning quiz scheduled at "
            f"{Config.MORNING_HOUR:02d}:{Config.MORNING_MINUTE:02d} {Config.TIMEZONE}"
        )

        # Evening "test starts in 10 minutes" reminder
        evening_reminder_hour, evening_reminder_minute = _minus_minutes(
            Config.EVENING_HOUR, Config.EVENING_MINUTE, 10
        )
        self._scheduler.add_job(
            self._run_evening_reminder,
            trigger=CronTrigger(
                hour=evening_reminder_hour,
                minute=evening_reminder_minute,
                timezone=Config.TIMEZONE,
            ),
            id="evening_reminder",
            name="Evening Test Reminder",
            replace_existing=True,
            misfire_grace_time=120,
            max_instances=1,
        )
        log.info(
            f"Evening reminder scheduled at "
            f"{evening_reminder_hour:02d}:{evening_reminder_minute:02d} {Config.TIMEZONE}"
        )

        # Evening quiz session
        self._scheduler.add_job(
            self._run_evening_session,
            trigger=CronTrigger(
                hour=Config.EVENING_HOUR,
                minute=Config.EVENING_MINUTE,
                timezone=Config.TIMEZONE,
            ),
            id="evening_quiz",
            name="Evening Quiz Session",
            replace_existing=True,
            misfire_grace_time=300,
            max_instances=1,
        )
        log.info(
            f"Evening quiz scheduled at "
            f"{Config.EVENING_HOUR:02d}:{Config.EVENING_MINUTE:02d} {Config.TIMEZONE}"
        )

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
            misfire_grace_time=300,
            max_instances=1,
        )
        log.info(
            f"Daily poll-close scheduled at "
            f"{Config.POLL_CLOSE_HOUR:02d}:{Config.POLL_CLOSE_MINUTE:02d} {Config.TIMEZONE}"
        )

    async def _run_morning_session(self) -> None:
        """Execute the morning quiz session."""
        log.info("=== Morning Quiz Session Started ===")
        try:
            await run_quiz_session(
                bot=self._bot,
                topic_manager=self._topic_manager,
                session_type="Morning",
            )
        except Exception as e:
            log.error(f"Morning session failed: {e}", exc_info=True)
            await self._notify_admin(f"Morning session failed: {e}")
        finally:
            log.info("=== Morning Quiz Session Ended ===")

    async def _run_evening_session(self) -> None:
        """Execute the evening quiz session."""
        log.info("=== Evening Quiz Session Started ===")
        try:
            await run_quiz_session(
                bot=self._bot,
                topic_manager=self._topic_manager,
                session_type="Evening",
            )
        except Exception as e:
            log.error(f"Evening session failed: {e}", exc_info=True)
            await self._notify_admin(f"Evening session failed: {e}")
        finally:
            log.info("=== Evening Quiz Session Ended ===")

    async def _run_morning_reminder(self) -> None:
        """Send the 'test starts in 10 minutes' reminder for the Morning session."""
        await self._send_test_reminder("Morning")

    async def _run_evening_reminder(self) -> None:
        """Send the 'test starts in 10 minutes' reminder for the Evening session."""
        await self._send_test_reminder("Evening")

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
        """Handle missed job executions."""
        log.warning(f"Scheduler job missed: {event.job_id}")
        # Schedule recovery if needed
        if event.job_id in ("morning_quiz", "evening_quiz"):
            session_type = "Morning" if event.job_id == "morning_quiz" else "Evening"
            log.info(f"Scheduling recovery for missed {session_type} session")

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
