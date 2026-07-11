"""
NORCET AI Bot - Duplicate Checker Module
======================================
Handles detection and management of duplicate questions
using content hashing.

IMPORTANT: This module reuses database.generate_question_hash() for
ALL hashing — the in-memory cache and the database MUST use the exact
same normalization, or cache lookups will silently never hit (every
check falls through to a DB query, defeating the point of the cache).
"""

from typing import Optional

from logger import log
from database import (
    is_duplicate,
    generate_question_hash,
    get_all_question_hashes,
)


class DuplicateChecker:
    """
    Checks questions for duplicates before posting.

    Uses database.generate_question_hash() (SHA-256 of normalized text)
    for both the in-memory cache and the DB fallback, so they always agree.
    Maintains an in-memory cache of hashes for fast batch operations.
    """

    def __init__(self) -> None:
        self._hash_cache: Optional[set[str]] = None
        self._cache_loaded: bool = False

    def _ensure_cache(self) -> None:
        """Lazily load the hash cache from the database."""
        if not self._cache_loaded:
            try:
                self._hash_cache = get_all_question_hashes()
                self._cache_loaded = True
                log.info(f"Duplicate checker cache loaded: {len(self._hash_cache)} hashes")
            except Exception as e:
                log.error(f"Failed to load duplicate cache: {e}")
                self._hash_cache = set()
                self._cache_loaded = True

    def is_duplicate(self, question_text: str) -> bool:
        """
        Check if a question is a duplicate.

        First checks the in-memory cache, then falls back to database.

        Args:
            question_text: The question text to check.

        Returns:
            True if the question already exists.
        """
        question_hash = generate_question_hash(question_text)

        # Check in-memory cache first (now uses the SAME hash as the DB)
        self._ensure_cache()
        if question_hash in self._hash_cache:  # type: ignore
            return True

        # Fallback to database check (covers cache staleness across restarts)
        try:
            if is_duplicate(question_text):
                self._hash_cache.add(question_hash)  # type: ignore
                return True
        except Exception as e:
            log.warning(f"Database duplicate check failed: {e}")

        return False

    def add_to_cache(self, question_text: str) -> None:
        """
        Add a question's hash to the in-memory cache after it's stored.

        Args:
            question_text: The question text that was stored.
        """
        question_hash = generate_question_hash(question_text)
        self._ensure_cache()
        self._hash_cache.add(question_hash)  # type: ignore

    def filter_duplicates(self, questions: list[dict]) -> list[dict]:
        """
        Filter out duplicate questions from a list.

        Args:
            questions: List of question dicts to filter.

        Returns:
            List of non-duplicate question dicts.
        """
        unique_questions = []
        duplicates_removed = 0

        for q in questions:
            if self.is_duplicate(q.get("question", "")):
                duplicates_removed += 1
                log.debug(f"Filtered duplicate: {q.get('question', '')[:60]}...")
            else:
                unique_questions.append(q)

        if duplicates_removed > 0:
            log.info(f"Filtered {duplicates_removed} duplicate questions from batch")

        return unique_questions

    def refresh_cache(self) -> None:
        """Force refresh the in-memory hash cache from the database."""
        self._cache_loaded = False
        self._ensure_cache()
        log.info("Duplicate checker cache refreshed")

    def get_cache_size(self) -> int:
        """Get the number of hashes in the cache."""
        self._ensure_cache()
        return len(self._hash_cache)  # type: ignore


# Module-level singleton
duplicate_checker = DuplicateChecker()
