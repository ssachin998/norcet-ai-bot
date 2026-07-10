"""
NORCET AI Bot - Main Entry Point
======================================
Telegram Bot for NORCET (AIIMS Nursing Entrance) Quiz preparation.

Features:
    - Automated daily quiz sessions (7 AM and 7 PM IST)
    - AI-generated MCQ questions via Google Gemini
    - Anonymous quiz polls with detailed explanations
    - Topic rotation with progress tracking
    - Admin commands for control and monitoring
    - Daily/weekly/monthly statistics
    - Duplicate question detection
    - Graceful restart and error recovery

Admin Commands:
    /status   - Bot status and progress
    /nexttopic - Skip to next topic
    /skip     - Skip current topic
    /postnow  - Post quiz immediately
    /help     - Help and command list
"""

import asyncio
import signal
import sys
from datetime import datetime, timezone, timedelta

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
)

from config import Config
from logger import log
from database import init_database
from topic_manager import TopicManager
from scheduler import QuizScheduler
from telegram_poll import post_immediate_session
from utils import escape_html, parse_chat_id

IST = timezone(timedelta(hours=5, minutes=30))


# ── Global instances ────────────────────────────────────────────
topic_manager: TopicManager | None = None
quiz_scheduler: QuizScheduler | None = None


def is_admin(user_id: int) -> bool:
    """Check if a user ID is in the admin list."""
    if not Config.ADMIN_CHAT_IDS:
        # If no admins configured, allow all users (useful for development)
        return True
    return user_id in Config.ADMIN_CHAT_IDS


# ── Admin Command Handlers ────────────────────────────────────

async def cmd_start(update: Update, context: CallbackContext) -> None:
    """Handle /start command."""
    if not is_admin(update.effective_user.id):
        return

    welcome = (
        "<b>NORCET AI Quiz Bot</b>\n\n"
        "🤖 AI-powered NORCET preparation quizzes\n"
        "📚 AIIMS NORCET Previous Year Question style\n"
        "⏰ Automated sessions at 7 AM & 7 PM IST\n"
        "📊 Detailed explanations for every question\n\n"
        "Use /help to see available commands."
    )
    try:
        await update.message.reply_text(welcome, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to send start message: {e}")


async def cmd_help(update: Update, context: CallbackContext) -> None:
    """Handle /help command."""
    if not is_admin(update.effective_user.id):
        return

    help_text = (
        "<b>📋 NORCET AI Bot — Command List</b>\n\n"
        "<b>Admin Commands:</b>\n\n"
        "<code>/status</code> — View bot status, topic progress, and statistics\n\n"
        "<code>/nexttopic</code> — Complete current topic and move to next\n\n"
        "<code>/skip</code> — Skip current topic without marking complete\n\n"
        "<code>/postnow</code> — Post a quiz session immediately\n\n"
        "<code>/help</code> — Show this help message\n\n"
        "<code>/stats today</code> — Today's statistics\n\n"
        "<code>/stats week</code> — This week's statistics\n\n"
        "<code>/stats month</code> — This month's statistics\n\n"
        "<code>/topics</code> — View all topics and their status\n\n"
        "<code>/schedule</code> — View upcoming scheduled sessions\n\n"
        "<b>Admin Chat IDs:</b>\n"
        f"<code>{', '.join(map(str, Config.ADMIN_CHAT_IDS)) if Config.ADMIN_CHAT_IDS else 'All users (dev mode)'}</code>"
    )
    try:
        await update.message.reply_text(help_text, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to send help message: {e}")


async def cmd_status(update: Update, context: CallbackContext) -> None:
    """Handle /status command."""
    if not is_admin(update.effective_user.id):
        return

    try:
        progress = topic_manager.get_progress_info()
        from database import (
            get_total_questions_posted,
            get_questions_count_by_difficulty,
            get_topics_covered_count,
        )

        total_questions = get_total_questions_posted()
        difficulty_counts = get_questions_count_by_difficulty()
        topics_covered = get_topics_covered_count()

        scheduler_status = "Running ✅" if quiz_scheduler and quiz_scheduler.is_running() else "Stopped ❌"

        status_text = (
            "<b>📊 NORCET Bot Status</b>\n\n"
            f"<b>Bot:</b> {scheduler_status}\n"
            f"<b>Current Topic:</b> <i>{escape_html(progress['current_topic'])}</i>\n"
            f"<b>Topic Progress:</b> {progress['current_index'] + 1}/{progress['total_topics']}\n"
            f"<b>Topic Completion:</b> {progress['completion_percentage']}%\n"
            f"<b>Questions (this topic):</b> {progress['questions_asked']}\n\n"
            f"<b>📈 Overall Statistics:</b>\n"
            f"• Total Questions Posted: <b>{total_questions}</b>\n"
            f"• Topics Covered: <b>{topics_covered}</b>\n"
            f"• Easy: {difficulty_counts.get('Easy', 0)} | "
            f"Moderate: {difficulty_counts.get('Moderate', 0)} | "
            f"Hard: {difficulty_counts.get('Hard', 0)}\n\n"
            f"<b>⏰ Schedule:</b>\n"
            f"• Morning: {Config.MORNING_HOUR:02d}:{Config.MORNING_MINUTE:02d} IST ({Config.QUESTIONS_PER_SESSION} MCQs)\n"
            f"• Evening: {Config.EVENING_HOUR:02d}:{Config.EVENING_MINUTE:02d} IST ({Config.QUESTIONS_PER_SESSION} MCQs)\n\n"
            f"<b>💻 Gemini Model:</b> {Config.GEMINI_MODEL}\n"
            f"<b>🕐 Current Time:</b> {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}"
        )

        await update.message.reply_text(status_text, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to send status: {e}")
        await update.message.reply_text(f"Error getting status: {e}")


async def cmd_next_topic(update: Update, context: CallbackContext) -> None:
    """Handle /nexttopic command."""
    if not is_admin(update.effective_user.id):
        return

    try:
        old_topic = topic_manager.current_topic
        new_topic = topic_manager.advance_to_next_topic()

        msg = (
            f"<b>✅ Topic Advanced</b>\n\n"
            f"Previous: <i>{escape_html(old_topic)}</i>\n"
            f"Current: <i>{escape_html(new_topic)}</i>\n"
            f"Progress: {topic_manager.current_index + 1}/{topic_manager.total_topics}\n"
            f"Completion: {topic_manager.get_progress_info()['completion_percentage']}%"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to advance topic: {e}")
        await update.message.reply_text(f"Error: {e}")


async def cmd_skip(update: Update, context: CallbackContext) -> None:
    """Handle /skip command."""
    if not is_admin(update.effective_user.id):
        return

    try:
        old_topic = topic_manager.current_topic
        new_topic = topic_manager.skip_to_next_topic()

        msg = (
            f"<b>⏭️ Topic Skipped</b>\n\n"
            f"Skipped: <i>{escape_html(old_topic)}</i>\n"
            f"Current: <i>{escape_html(new_topic)}</i>\n"
            f"Progress: {topic_manager.current_index + 1}/{topic_manager.total_topics}"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to skip topic: {e}")
        await update.message.reply_text(f"Error: {e}")


async def cmd_post_now(update: Update, context: CallbackContext) -> None:
    """Handle /postnow command."""
    if not is_admin(update.effective_user.id):
        return

    try:
        await update.message.reply_text(
            "<b>🚀 Starting immediate quiz session...</b>",
            parse_mode="HTML",
        )

        bot = context.bot
        result = await post_immediate_session(bot, topic_manager)

        if result.get("success"):
            msg = (
                f"<b>✅ Session Complete</b>\n"
                f"Topic: <i>{escape_html(result['topic'])}</i>\n"
                f"Type: {result['session_type']}\n"
                f"Questions posted: <b>{result['questions_posted']}</b>\n"
                f"Failed: {result.get('failed', 0)}"
            )
        else:
            msg = (
                f"<b>❌ Session Failed</b>\n"
                f"Error: {escape_html(str(result.get('error', 'Unknown error')))}"
            )

        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.error(f"Post now failed: {e}")
        await update.message.reply_text(f"Error: {e}")


async def cmd_stats(update: Update, context: CallbackContext) -> None:
    """Handle /stats command with sub-commands: today, week, month."""
    if not is_admin(update.effective_user.id):
        return

    from database import get_daily_stats, get_weekly_stats, get_monthly_stats

    try:
        args = context.args if context.args else []
        period = args[0].lower() if args else "today"

        if period == "today":
            date_str = datetime.now(IST).strftime("%Y-%m-%d")
            stats = get_daily_stats(date_str)
            if not stats:
                await update.message.reply_text(
                    f"No statistics for today ({date_str}).",
                    parse_mode="HTML",
                )
                return

            msg = (
                f"<b>📊 Today's Statistics ({date_str})</b>\n\n"
                f"Total Questions: <b>{stats['questions_posted']}</b>\n"
                f"Morning Sessions: {stats['morning_session']}\n"
                f"Evening Sessions: {stats['evening_session']}\n"
                f"Topics: <i>{', '.join(stats['topics_covered']) or 'None'}</i>\n\n"
                f"<b>Difficulty Breakdown:</b>\n"
                f"🟢 Easy: {stats['easy_count']}\n"
                f"🟡 Moderate: {stats['moderate_count']}\n"
                f"🔴 Hard: {stats['hard_count']}"
            )
            await update.message.reply_text(msg, parse_mode="HTML")

        elif period == "week":
            week_start = datetime.now(IST).strftime("%Y-%m-%d")
            from datetime import timedelta
            week_start_date = datetime.now(IST) - timedelta(days=datetime.now(IST).weekday())
            week_start = week_start_date.strftime("%Y-%m-%d")
            stats_list = get_weekly_stats(week_start)

            total_q = sum(s["questions_posted"] for s in stats_list)
            total_easy = sum(s["easy_count"] for s in stats_list)
            total_moderate = sum(s["moderate_count"] for s in stats_list)
            total_hard = sum(s["hard_count"] for s in stats_list)

            all_topics = set()
            for s in stats_list:
                all_topics.update(s["topics_covered"])

            msg = (
                f"<b>📊 Weekly Statistics (from {week_start})</b>\n\n"
                f"Total Questions: <b>{total_q}</b>\n"
                f"Days active: {len(stats_list)}\n"
                f"Topics covered: <i>{', '.join(sorted(all_topics)) or 'None'}</i>\n\n"
                f"<b>Difficulty:</b>\n"
                f"🟢 Easy: {total_easy} | "
                f"🟡 Moderate: {total_moderate} | "
                f"🔴 Hard: {total_hard}\n\n"
                f"<b>Daily breakdown:</b>\n"
            )
            for s in stats_list:
                msg += f"  • {s['date']}: {s['questions_posted']} Qs\n"

            await update.message.reply_text(msg, parse_mode="HTML")

        elif period == "month":
            month = datetime.now(IST).strftime("%Y-%m")
            stats_list = get_monthly_stats(month)

            total_q = sum(s["questions_posted"] for s in stats_list)
            total_easy = sum(s["easy_count"] for s in stats_list)
            total_moderate = sum(s["moderate_count"] for s in stats_list)
            total_hard = sum(s["hard_count"] for s in stats_list)

            all_topics = set()
            for s in stats_list:
                all_topics.update(s["topics_covered"])

            msg = (
                f"<b>📊 Monthly Statistics ({month})</b>\n\n"
                f"Total Questions: <b>{total_q}</b>\n"
                f"Days active: {len(stats_list)}\n"
                f"Topics covered: <i>{', '.join(sorted(all_topics)) or 'None'}</i>\n\n"
                f"<b>Difficulty:</b>\n"
                f"🟢 Easy: {total_easy} | "
                f"🟡 Moderate: {total_moderate} | "
                f"🔴 Hard: {total_hard}"
            )
            await update.message.reply_text(msg, parse_mode="HTML")

        else:
            await update.message.reply_text(
                "Usage: <code>/stats today|week|month</code>",
                parse_mode="HTML",
            )

    except Exception as e:
        log.error(f"Failed to get stats: {e}")
        await update.message.reply_text(f"Error getting stats: {e}")


async def cmd_topics(update: Update, context: CallbackContext) -> None:
    """Handle /topics command - show all topics with status."""
    if not is_admin(update.effective_user.id):
        return

    try:
        all_topics = topic_manager.get_all_topics_with_status()
        if not all_topics:
            await update.message.reply_text("No topics configured.")
            return

        msg_parts = ["<b>📚 Topic List</b>\n"]
        for t in all_topics:
            idx = t["index"] + 1
            status_emoji = {
                "completed": "✅",
                "current": "📍",
                "upcoming": "⬜",
            }.get(t["status"], "⬜")

            status_text = t["status"].title()
            msg_parts.append(
                f"{status_emoji} <code>{idx:02d}</code>. "
                f"<i>{escape_html(t['topic'])}</i> "
                f"[{status_text}]"
            )

        msg_parts.append(
            f"\nTotal: {len(all_topics)} topics | "
            f"Completed: {sum(1 for t in all_topics if t['status'] == 'completed')}"
        )

        # Telegram has a 4096 char limit; split if needed
        full_msg = "\n".join(msg_parts)
        if len(full_msg) <= 4096:
            await update.message.reply_text(full_msg, parse_mode="HTML")
        else:
            # Send in chunks
            chunks = []
            current = ["<b>📚 Topic List</b>\n"]
            for part in msg_parts[1:]:
                if len("\n".join(current + [part])) > 4000:
                    chunks.append("\n".join(current))
                    current = [part]
                else:
                    current.append(part)
            if current:
                chunks.append("\n".join(current))

            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode="HTML")
                await asyncio.sleep(0.5)

    except Exception as e:
        log.error(f"Failed to list topics: {e}")
        await update.message.reply_text(f"Error: {e}")


async def cmd_schedule(update: Update, context: CallbackContext) -> None:
    """Handle /schedule command - show upcoming scheduled sessions."""
    if not is_admin(update.effective_user.id):
        return

    try:
        if not quiz_scheduler or not quiz_scheduler.is_running():
            await update.message.reply_text(
                "<b>❌ Scheduler is not running</b>",
                parse_mode="HTML",
            )
            return

        jobs = quiz_scheduler.get_jobs_info()
        msg = "<b>⏰ Scheduled Sessions</b>\n\n"
        for job in jobs:
            msg += (
                f"🔹 <b>{job['name']}</b>\n"
                f"   ID: <code>{job['id']}</code>\n"
                f"   Next run: {job['next_run']}\n\n"
            )

        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        log.error(f"Failed to get schedule: {e}")
        await update.message.reply_text(f"Error: {e}")


# ── Error Handlers ─────────────────────────────────────────────

async def error_handler(update: object, context: CallbackContext) -> None:
    """Handle errors from the Telegram bot application."""
    log.error(f"Bot error: {context.error}", exc_info=context.error)

    # Notify admins about critical errors
    if context.error:
        error_str = str(context.error)[:500]
        for admin_id in Config.ADMIN_CHAT_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ <b>Bot Error</b>\n\n{escape_html(error_str)}",
                    parse_mode="HTML",
                )
            except Exception:
                pass


# ── Application Lifecycle ──────────────────────────────────────

async def post_init(application: Application) -> None:
    """
    Called after the application is initialized.
    Sets up the topic manager, scheduler, and bot commands.
    """
    global topic_manager, quiz_scheduler

    log.info("Initializing NORCET AI Bot...")

    # Initialize database
    init_database()
    log.info("Database initialized")

    # Initialize topic manager
    topic_manager = TopicManager()
    log.info(f"Topic manager ready: {topic_manager.total_topics} topics loaded")

    # Set up bot commands
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help and commands"),
        BotCommand("status", "View bot status and statistics"),
        BotCommand("nexttopic", "Advance to next topic"),
        BotCommand("skip", "Skip current topic"),
        BotCommand("postnow", "Post quiz immediately"),
        BotCommand("stats", "View statistics (today/week/month)"),
        BotCommand("topics", "View all topics and status"),
        BotCommand("schedule", "View upcoming scheduled sessions"),
    ]
    await application.bot.set_my_commands(commands)
    log.info("Bot commands registered")

    # Initialize and start scheduler
    bot = application.bot
    quiz_scheduler = QuizScheduler(bot, topic_manager)
    quiz_scheduler.start()
    log.info("Scheduler started")

    # Send startup notification to admins
    progress = topic_manager.get_progress_info()
    startup_msg = (
        f"🟢 <b>NORCET AI Bot Started</b>\n\n"
        f"Topic: <i>{escape_html(progress['current_topic'])}</i>\n"
        f"Progress: {progress['current_index'] + 1}/{progress['total_topics']} "
        f"({progress['completion_percentage']}%)\n"
        f"Questions (this topic): {progress['questions_asked']}\n\n"
        f"Morning: {Config.MORNING_HOUR:02d}:{Config.MORNING_MINUTE:02d} IST\n"
        f"Evening: {Config.EVENING_HOUR:02d}:{Config.EVENING_MINUTE:02d} IST\n\n"
        f"🕐 {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}"
    )
    for admin_id in Config.ADMIN_CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=startup_msg,
                parse_mode="HTML",
                disable_notification=True,
            )
        except Exception as e:
            log.error(f"Failed to send startup notification to {admin_id}: {e}")

    log.info("NORCET AI Bot initialization complete")


async def post_shutdown(application: Application) -> None:
    """Called when the application is shutting down."""
    global quiz_scheduler

    log.info("NORCET AI Bot shutting down...")

    if quiz_scheduler:
        quiz_scheduler.stop()

    log.info("NORCET AI Bot shutdown complete")


def main() -> None:
    """
    Main entry point for the NORCET AI Bot.

    Validates configuration, creates the Telegram Application,
    registers handlers, and starts the bot with graceful shutdown support.
    """
    # Validate configuration
    errors = Config.validate()
    if errors:
        log.error("Configuration errors:")
        for err in errors:
            log.error(f"  - {err}")
        print("\n❌ Configuration errors detected. Please fix and restart.")
        print("\nErrors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    log.info("Configuration validated successfully")

    # Build the application
    application = (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("nexttopic", cmd_next_topic))
    application.add_handler(CommandHandler("skip", cmd_skip))
    application.add_handler(CommandHandler("postnow", cmd_post_now))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("topics", cmd_topics))
    application.add_handler(CommandHandler("schedule", cmd_schedule))

    # Register error handler
    application.add_error_handler(error_handler)

    # Set up graceful shutdown via signal handlers
    def signal_handler(sig, frame):
        log.info(f"Received signal {sig}. Initiating graceful shutdown...")
        asyncio.get_event_loop().create_task(application.shutdown())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the bot (polling mode)
    log.info("Starting NORCET AI Bot in polling mode...")
    print("\n🤖 NORCET AI Bot starting...")
    print(f"   Morning session: {Config.MORNING_HOUR:02d}:{Config.MORNING_MINUTE:02d} IST")
    print(f"   Evening session: {Config.EVENING_HOUR:02d}:{Config.EVENING_MINUTE:02d} IST")
    print(f"   Questions per session: {Config.QUESTIONS_PER_SESSION}")
    print(f"   Press Ctrl+C to stop.\n")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
