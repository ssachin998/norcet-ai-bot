"""
NORCET AI Bot - Topic Picker Module
====================================
Interactive /jumptopic search. Instead of requiring the admin to type
a topic's exact name (which involves guessing exact punctuation/word
order), this shows a tappable list of matching topics as a Telegram
inline keyboard whenever the search text matches more than one topic.
Tapping a button jumps straight to that topic — no retyping needed.

Flow:
  1. Admin sends /jumptopic <search text>
  2. Exactly one topic matches -> jump immediately (fast path, same
     as before — no extra tap needed for an unambiguous search).
  3. Multiple topics match -> a message listing them (with the
     matched word(s) in bold) is sent, with one button per topic.
     Tapping a button fires handle_jump_topic_callback(), which jumps
     and edits the message to confirm.
  4. Nothing matches -> says so, same as before.

NOTE on Telegram limitations: button LABELS are always plain text —
Telegram does not support bold/HTML inside inline keyboard buttons.
The bold highlighting of matched words happens in the message TEXT
above the buttons, not on the buttons themselves.
"""

import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from config import Config
from logger import log
from utils import escape_html

CALLBACK_PREFIX = "jt:"
MAX_BUTTON_LEN = 60
MAX_SHOWN = 10  # cap how many buttons/list entries we show at once


def _is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_CHAT_IDS


def _bold_query_words(topic_name: str, query: str) -> str:
    """
    HTML-escape a topic name and wrap every word from `query` that
    appears in it with <b>...</b>, so the matched part stands out in
    the picker list. Longer words are bolded first so e.g. "nervous"
    doesn't partially clash with a longer overlapping match.
    """
    escaped = escape_html(topic_name)
    words = sorted(
        {w for w in re.findall(r"[A-Za-z0-9]+", query.lower()) if w},
        key=len,
        reverse=True,
    )
    for w in words:
        escaped = re.sub(rf"(?i)\b({re.escape(w)})\b", r"<b>\1</b>", escaped)
    return escaped


def _truncate_button_label(text: str, limit: int = MAX_BUTTON_LEN) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _confirm_text(old_topic: str, new_topic: str, topic_manager) -> str:
    return (
        f"<b>🎯 Jumped to Topic</b>\n\n"
        f"Previous: <i>{escape_html(old_topic)}</i>\n"
        f"Current: <i>{escape_html(new_topic)}</i>\n"
        f"Progress: {topic_manager.current_index + 1}/{topic_manager.total_topics}"
    )


async def cmd_jump_topic(update: Update, context: CallbackContext) -> None:
    """
    Handle /jumptopic <search text>.

    Unlike a plain exact-match command, this doesn't require the
    search text to resolve unambiguously — if it matches several
    topics, they're shown as tappable buttons instead of failing with
    "be more specific".
    """
    if not _is_admin(update.effective_user.id):
        return

    topic_manager = context.bot_data.get("topic_manager")
    if topic_manager is None:
        await update.message.reply_text("Bot is still starting up — try again in a moment.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/jumptopic &lt;search text&gt;</code>\n"
            "Example: <code>/jumptopic nervous</code>\n\n"
            "If more than one topic matches, you'll get a tappable list — "
            "no need to type the exact name.",
            parse_mode="HTML",
        )
        return

    query = " ".join(context.args)
    matches = topic_manager.search_topics(query)

    if not matches:
        await update.message.reply_text(
            f"❌ No topic matches '{escape_html(query)}'.", parse_mode="HTML"
        )
        return

    if len(matches) == 1:
        index, _ = matches[0]
        old_topic = topic_manager.current_topic
        new_topic = topic_manager.jump_to_topic(index)
        await update.message.reply_text(
            _confirm_text(old_topic, new_topic, topic_manager), parse_mode="HTML"
        )
        return

    # Multiple matches — show a tappable picker instead of erroring out.
    shown = matches[:MAX_SHOWN]
    lines = [f"🔍 <b>{len(matches)} topics match</b> '{escape_html(query)}':\n"]
    for i, (_, name) in enumerate(shown, 1):
        lines.append(f"{i}. {_bold_query_words(name, query)}")
    if len(matches) > MAX_SHOWN:
        lines.append(f"\n…and {len(matches) - MAX_SHOWN} more. Try a more specific search.")
    lines.append("\nTap one below to jump:")

    keyboard = [
        [InlineKeyboardButton(
            _truncate_button_label(f"{i}. {name}"),
            callback_data=f"{CALLBACK_PREFIX}{idx}",
        )]
        for i, (idx, name) in enumerate(shown, 1)
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"{CALLBACK_PREFIX}cancel")])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_jump_topic_callback(update: Update, context: CallbackContext) -> None:
    """Handle a button tap from the /jumptopic picker."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith(CALLBACK_PREFIX):
        return

    if not _is_admin(query.from_user.id):
        await query.answer("Not authorized.", show_alert=True)
        return

    payload = query.data[len(CALLBACK_PREFIX):]

    if payload == "cancel":
        await query.answer("Cancelled.")
        await query.edit_message_text("Cancelled — no topic change.")
        return

    topic_manager = context.bot_data.get("topic_manager")
    if topic_manager is None:
        await query.answer("Bot is still starting up.", show_alert=True)
        return

    try:
        index = int(payload)
        old_topic = topic_manager.current_topic
        new_topic = topic_manager.jump_to_topic(index)
        await query.answer(f"Jumped to: {new_topic}")
        await query.edit_message_text(
            _confirm_text(old_topic, new_topic, topic_manager), parse_mode="HTML"
        )
    except (ValueError, IndexError) as e:
        log.error(f"Topic picker callback failed: {e}")
        await query.answer("That topic is no longer valid — topics.txt may have changed.", show_alert=True)
