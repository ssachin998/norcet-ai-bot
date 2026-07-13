"""
NORCET AI Bot - Topic Manager Module
======================================
Manages the list of NORCET topics, tracks progress through them,
handles automatic topic rotation, and persists state across restarts.

Reads topics from topics.txt and maintains position in the SQLite database.
"""

import os
import re
from typing import Optional

from config import Config
from logger import log
from database import (
    get_topic_progress,
    set_topic_progress,
    mark_topic_completed,
    get_topic_completion_percentage,
)


class TopicManager:
    """
    Manages topic rotation for NORCET quiz generation.

    Reads topics from topics.txt, tracks current position,
    and provides the next topic when the current one is exhausted.
    """

    def __init__(self, topics_file: Optional[str] = None) -> None:
        self._topics_file = topics_file or Config.TOPICS_FILE
        self._topics: list[str] = []
        self._load_topics()
        self._restore_progress()

    def _load_topics(self) -> None:
        """
        Load topics from the topics.txt file, then append any topics
        added at runtime via /addtopic (persisted in the DB's
        custom_topics table, not the file — so they survive a redeploy
        even if topics.txt itself isn't on the persistent volume).
        Each line is a separate topic. Blank lines and comments are ignored.
        """
        if not os.path.exists(self._topics_file):
            log.error(f"Topics file not found: {self._topics_file}")
            raise FileNotFoundError(
                f"Topics file not found: {self._topics_file}. "
                "Please create a topics.txt file with one topic per line."
            )

        with open(self._topics_file, "r", encoding="utf-8") as f:
            raw_topics = f.readlines()

        self._topics = []
        for line in raw_topics:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                self._topics.append(line)

        from database import get_custom_topics
        for extra in get_custom_topics():
            if extra not in self._topics:
                self._topics.append(extra)

        log.info(f"Loaded {len(self._topics)} topics from {self._topics_file} + DB")

    def _restore_progress(self) -> None:
        """
        Restore topic progress from the database.
        Ensures the bot continues from where it left off after restart.

        Fix #4: the stored topic NAME is the source of truth, not the
        stored index. If topics.txt was edited/reordered/had a topic
        inserted since the last run, the same numeric index would now
        point at a different topic — silently derailing progress onto
        the wrong subject. Looking the name up in the freshly-loaded
        list avoids that: as long as the topic's name is unchanged, the
        bot keeps following IT, regardless of where it now sits in the
        file.
        """
        progress = get_topic_progress()
        stored_name = progress.get("current_topic_name", "")
        stored_index = progress.get("current_topic_index", 0)

        if not self._topics:
            log.warning("Topics list is empty — nothing to restore.")
            return

        if stored_name and stored_name in self._topics:
            current_index = self._topics.index(stored_name)
            if current_index != stored_index:
                log.info(
                    f"topics.txt order changed — '{stored_name}' is now at "
                    f"position {current_index + 1} (was {stored_index + 1}). "
                    "Continuing with the same topic by name, not position."
                )
                set_topic_progress(
                    index=current_index,
                    topic_name=stored_name,
                    questions_asked=progress.get("questions_asked", 0),
                    questions_total=progress.get("questions_total", 0),
                )
            topic_name = stored_name
        else:
            # First-ever run, or the stored topic no longer exists in
            # topics.txt (renamed/removed) — fall back to the first topic.
            if stored_name:
                log.warning(
                    f"Stored topic '{stored_name}' not found in "
                    f"{self._topics_file} — falling back to the first topic. "
                    "If you renamed a topic rather than removing it, "
                    "progress for it won't carry over automatically."
                )
            current_index = 0
            topic_name = self._topics[0]
            set_topic_progress(
                index=current_index,
                topic_name=topic_name,
                questions_asked=0,
                questions_total=0,
            )

        log.info(
            f"Progress restored: Topic {current_index + 1}/{len(self._topics)} "
            f"- '{topic_name}'"
        )

    @property
    def topics(self) -> list[str]:
        """Get the full list of topics."""
        return list(self._topics)

    @property
    def total_topics(self) -> int:
        """Get the total number of topics."""
        return len(self._topics)

    @property
    def current_index(self) -> int:
        """Get the current topic index."""
        progress = get_topic_progress()
        return progress.get("current_topic_index", 0)

    @property
    def current_topic(self) -> str:
        """Get the current topic name."""
        progress = get_topic_progress()
        return progress.get("current_topic_name", "")

    def is_fresh_start(self) -> bool:
        """
        Fix #2: heuristic used at startup to detect a suspicious
        'reset to zero' state — topic 1, 0 questions asked — which is
        exactly what happens when the DB got wiped (e.g. no persistent
        volume mounted on Railway). Can't distinguish this perfectly
        from a genuine first-ever run, so bot.py uses this to show a
        loud warning rather than silently continuing either way.
        """
        progress = self.get_progress_info()
        return (
            progress["current_index"] == 0
            and progress["questions_asked"] == 0
            and progress["total_topics"] > 1
        )

    def get_progress_info(self) -> dict:
        """
        Get comprehensive progress information.

        Returns:
            Dict with current_topic, current_index, total_topics,
            completion_percentage, questions_asked, questions_total.
        """
        progress = get_topic_progress()
        completion_pct = get_topic_completion_percentage(
            progress.get("current_topic_index", 0),
            len(self._topics),
        )

        return {
            "current_topic": progress.get("current_topic_name", ""),
            "current_index": progress.get("current_topic_index", 0),
            "total_topics": len(self._topics),
            "completion_percentage": completion_pct,
            "questions_asked": progress.get("questions_asked", 0),
            "questions_total": progress.get("questions_total", 0),
            "topic_completed": progress.get("topic_completed", 0),
        }

    def advance_to_next_topic(self) -> str:
        """
        Mark the current topic as completed and move to the next one.

        Returns:
            The name of the new current topic.

        Raises:
            IndexError: If all topics are exhausted.
        """
        from database import get_setting, set_setting, log_topic_completion

        current_idx = self.current_index

        # Mark current topic as completed
        mark_topic_completed(current_idx)

        cycle = int(get_setting("current_cycle", "1"))
        log_topic_completion(current_idx, self._topics[current_idx], cycle)

        # Move to next topic
        next_idx = current_idx + 1
        if next_idx >= len(self._topics):
            cycle += 1
            set_setting("current_cycle", str(cycle))
            log.info(
                f"All topics completed for cycle {cycle - 1}! "
                f"Starting cycle {cycle} from topic 1."
            )
            next_idx = 0

        next_topic = self._topics[next_idx]
        set_topic_progress(
            index=next_idx,
            topic_name=next_topic,
            questions_asked=0,
            questions_total=0,
            topic_completed=0,
        )

        log.info(
            f"Advanced to topic {next_idx + 1}/{len(self._topics)}: '{next_topic}'"
        )
        return next_topic

    def skip_to_next_topic(self) -> str:
        """
        Skip the current topic and move to the next one without marking as completed.

        Returns:
            The name of the new current topic.
        """
        current_idx = self.current_index
        next_idx = current_idx + 1

        if next_idx >= len(self._topics):
            next_idx = 0

        next_topic = self._topics[next_idx]
        set_topic_progress(
            index=next_idx,
            topic_name=next_topic,
            questions_asked=0,
            questions_total=0,
            topic_completed=0,
        )

        log.info(
            f"Skipped to topic {next_idx + 1}/{len(self._topics)}: '{next_topic}'"
        )
        return next_topic

    def jump_to_topic(self, index: int) -> str:
        """
        Jump to a specific topic by index (0-based).

        Args:
            index: Target topic index.

        Returns:
            The name of the new current topic.

        Raises:
            IndexError: If index is out of range.
        """
        if index < 0 or index >= len(self._topics):
            raise IndexError(
                f"Topic index {index} out of range (0-{len(self._topics) - 1})"
            )

        target_topic = self._topics[index]
        set_topic_progress(
            index=index,
            topic_name=target_topic,
            questions_asked=0,
            questions_total=0,
            topic_completed=0,
        )

        log.info(
            f"Jumped to topic {index + 1}/{len(self._topics)}: '{target_topic}'"
        )
        return target_topic

    def search_topics(self, query: str) -> list[tuple[int, str]]:
        """
        Search topics by query, returning ALL matches as (index, name)
        pairs — unlike jump_to_topic_by_name(), this never raises on
        an ambiguous query. Used by the /jumptopic picker
        (topic_picker.py) so the admin can tap-select from a list
        instead of needing to type an exact, unambiguous name.

        Same 3-tier strategy: exact > substring > word-set (ignores
        hyphens/punctuation/word order).
        """
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        # 1. Exact match
        for i, t in enumerate(self._topics):
            if t.lower() == query_lower:
                return [(i, t)]

        # 2. Substring match
        substring_matches = [
            (i, t) for i, t in enumerate(self._topics) if query_lower in t.lower()
        ]
        if substring_matches:
            return substring_matches

        # 3. Word-set match
        query_words = set(re.findall(r"[a-z0-9]+", query_lower))
        if not query_words:
            return []
        return [
            (i, t) for i, t in enumerate(self._topics)
            if query_words.issubset(set(re.findall(r"[a-z0-9]+", t.lower())))
        ]

    def jump_to_topic_by_name(self, name: str) -> str:
        """
        Jump to a topic by name — deliberately forgiving (see
        search_topics() for the matching strategy). Used for
        non-interactive callers; /jumptopic itself uses
        search_topics() directly via topic_picker.py so it can offer
        a tappable list instead of just erroring on ambiguity.

        Args:
            name: Topic name, or a distinctive word/phrase from it.

        Returns:
            The name of the new current topic.

        Raises:
            ValueError: If no topic matches, or more than one does.
        """
        matches = self.search_topics(name)
        if not matches:
            raise ValueError(f"No topic matches '{name}'.")
        if len(matches) > 1:
            shown = matches[:5]
            options = ", ".join(f"'{t}'" for _, t in shown)
            extra = f" (+{len(matches) - 5} more)" if len(matches) > 5 else ""
            raise ValueError(
                f"'{name}' matches multiple topics: {options}{extra}. "
                "Be more specific."
            )
        index, _ = matches[0]
        return self.jump_to_topic(index)

    def add_topic(self, name: str) -> bool:
        """
        Add a new topic at runtime (used by /addtopic).

        Persists to the DB's custom_topics table (survives restarts
        even if topics.txt isn't on a persistent volume) and appends
        to the in-memory list immediately so it's usable right away.

        Returns:
            True if added, False if it already exists.
        """
        from database import add_custom_topic

        name = name.strip()
        if not name or name in self._topics:
            return False

        if add_custom_topic(name):
            self._topics.append(name)
            log.info(f"Topic added at runtime: '{name}' (now {len(self._topics)} total)")
            return True
        return False

    def increment_questions_asked(self, count: int) -> None:
        """
        Increment the questions asked counter for the current topic.

        Args:
            count: Number of additional questions asked.
        """
        progress = get_topic_progress()
        new_count = progress.get("questions_asked", 0) + count
        set_topic_progress(
            index=progress.get("current_topic_index", 0),
            topic_name=progress.get("current_topic_name", ""),
            questions_asked=new_count,
            questions_total=progress.get("questions_total", 0),
        )

    def set_questions_total(self, total: int) -> None:
        """
        Set the estimated total questions for the current topic.

        Args:
            total: Estimated total questions.
        """
        progress = get_topic_progress()
        set_topic_progress(
            index=progress.get("current_topic_index", 0),
            topic_name=progress.get("current_topic_name", ""),
            questions_asked=progress.get("questions_asked", 0),
            questions_total=total,
        )

    def get_topics_remaining(self) -> list[str]:
        """Get the list of topics that haven't been completed yet."""
        progress = get_topic_progress()
        start_idx = progress.get("current_topic_index", 0)
        return self._topics[start_idx:]

    def get_all_topics_with_status(self) -> list[dict]:
        """
        Get all topics with their completion status.

        Returns:
            List of dicts with topic name, index, and completed status.
        """
        progress = get_topic_progress()
        current_idx = progress.get("current_topic_index", 0)
        topic_completed = progress.get("topic_completed", 0)

        result = []
        for i, topic in enumerate(self._topics):
            if i < current_idx:
                status = "completed"
            elif i == current_idx and topic_completed:
                status = "completed"
            elif i == current_idx:
                status = "current"
            else:
                status = "upcoming"
            result.append({
                "index": i,
                "topic": topic,
                "status": status,
            })
        return result
