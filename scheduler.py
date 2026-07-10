"""
NORCET AI Bot - Scheduler Module
======================================
Manages scheduled quiz sessions using APScheduler.

Schedules:
    - Morning session: 7:00 AM IST (50 MCQ polls)
    - Evening session: 7:00 PM IST (50 MCQ polls)

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
from telegram_poll import run_quiz_session
from topic_manager import TopicManager


IST = timezone(timedelta(hours=5, minutes=30))


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
