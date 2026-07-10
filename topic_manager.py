"""
NORCET AI Bot - Topic Manager Module
======================================
Manages the list of NORCET topics, tracks progress through them,
handles automatic topic rotation, and persists state across restarts.

Reads topics from topics.txt and maintains position in the SQLite database.
"""

import os
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
        Load topics from the topics.txt file.
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

        log.info(f"Loaded {len(self._topics)} topics from {self._topics_file}")

    def _restore_progress(self) -> None:
        """
        Restore topic progress from the database.
        Ensures the bot continues from where it left off after restart.
        """
        progress = get_topic_progress()
        current_index = progress.get("current_topic_index", 0)
        topic_name = progress.get("current_topic_name", "")

        # Validate the stored index
        if current_index >= len(self._topics):
            log.warning(
                f"Stored topic index {current_index} exceeds topics count "
                f"{len(self._topics)}. Resetting to 0."
            )
            current_index = 0

        # If topic name doesn't match, update it
        if self._topics and (
            not topic_name
            or topic_name != self._topics[current_index]
        ):
            topic_name = self._topics[current_index]
            set_topic_progress(
                index=current_index,
                topic_name=topic_name,
                questions_asked=progress.get("questions_asked", 0),
                questions_total=progress.get("questions_total", 0),
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
        current_idx = self.current_index

        # Mark current topic as completed
        mark_topic_completed(current_idx)

        # Move to next topic
        next_idx = current_idx + 1
        if next_idx >= len(self._topics):
            log.info("All topics have been completed! Restarting from topic 1.")
            next_idx = 0

        next_topic = self._topics[next_idx]
        set_topic_progress(
            index=next_idx,
            topic_name=next_topic,
            questions_asked=0,
            questions_total=0,
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
        )

        log.info(
            f"Jumped to topic {index + 1}/{len(self._topics)}: '{target_topic}'"
        )
        return target_topic

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
