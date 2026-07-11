"""
NORCET AI Bot - Google Gemini API Module
======================================
Handles communication with the Google Gemini 3.5 Flash API.

Architecture (designed for Gemini Free Tier: 5 RPM limit):
    - Every question is generated via ONE independent API call.
    - Every explanation is generated via ONE independent API call.
    - No batching, no preloading, no caching of questions.
    - A rolling-window rate limiter guarantees at most 4 API calls
      in any 60-second window, with a 1-request safety margin.
    - HTTP 429 responses are parsed for retry_delay and handled
      automatically without canceling the session.

Session cycle (per question, 30 seconds):
    00s  -> generate_single_question()   [API call]
    15s  -> generate_explanation()       [API call]
    30s  -> generate_single_question()  [API call, next Q]
    45s  -> generate_explanation()       [API call, next Q]
"""

import json
import asyncio
import time
from typing import Optional
from collections import deque

import google.generativeai as genai

from config import Config
from logger import log
from database import generate_question_hash


# ── Rate Limiter ──────────────────────────────────────────────

class GeminiRateLimiter:
    """
    Rolling-window rate limiter.

    Guarantee: NEVER more than max_requests API calls within any
    rolling window_seconds window.  If a request would breach the
    limit, acquire() blocks until a slot opens.
    """

    def __init__(
        self,
        max_requests: int = 4,
        window_seconds: int = 60,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: deque[float] = deque()

    async def acquire(self) -> None:
        """Block until a request slot is available, then record it."""
        while True:
            now = time.monotonic()
            # Prune timestamps that have fallen outside the window
            while (
                self._timestamps
                and (now - self._timestamps[0]) >= self._window
            ):
                self._timestamps.popleft()

            if len(self._timestamps) < self._max:
                self._timestamps.append(time.monotonic())
                return

            # Window full — wait for the oldest slot to expire
            wait = self._window - (now - self._timestamps[0]) + 0.15
            log.info(
                f"Gemini rate limiter: {self._max}/{self._window}s "
                f"window full. Sleeping {wait:.1f}s …"
            )
            await asyncio.sleep(wait)

    @property
    def available_slots(self) -> int:
        """Number of requests that can fire right now without waiting."""
        now = time.monotonic()
        while (
            self._timestamps
            and (now - self._timestamps[0]) >= self._window
        ):
            self._timestamps.popleft()
        return self._max - len(self._timestamps)

    def record_429(self) -> None:
        """
        Record an external 429 event.  Adds an extra timestamp so
        the limiter backs off even if the 429 came from a call
        that was already tracked.
        """
        self._timestamps.append(time.monotonic())


# Module-level singleton
gemini_rate_limiter = GeminiRateLimiter(
    max_requests=Config.GEMINI_RATE_LIMIT_MAX,
    window_seconds=Config.GEMINI_RATE_LIMIT_WINDOW,
)


# ── Prompt Templates ──────────────────────────────────────────

SYSTEM_INSTRUCTION = (
    "You are a senior nursing professor and NORCET question paper setter "
    "at AIIMS New Delhi. You have 20+ years of experience setting "
    "competitive examination questions for B.Sc Nursing, Post Basic "
    "B.Sc Nursing, and M.Sc Nursing entrance examinations (NORCET).\n\n"
    "Rules:\n"
    "- Resemble AIIMS NORCET Previous Year Questions.\n"
    "- Test clinical application, not mere recall.\n"
    "- Be factually accurate and evidence-based.\n"
    "- Use ONLY genuine references: Robbins, KDT, Apurba Sastry, "
    "Brunner, AIIMS Protocol, WHO, CDC.\n"
    "- Never fabricate references.\n"
    "- Questions must be original and unique.\n"
    "- Use proper medical terminology.\n"
    "- Every question must have exactly ONE correct answer.\n"
)


SINGLE_MCQ_PROMPT = """
Generate exactly ONE NORCET-level Multiple Choice Question on the topic: "{topic}"

Difficulty level: {difficulty}

Return a single JSON object (NOT an array) with EXACTLY these fields:
{{
  "question": "The question text",
  "optionA": "First option",
  "optionB": "Second option",
  "optionC": "Third option",
  "optionD": "Fourth option",
  "correct_answer": "The correct option letter — exactly A, B, C, or D",
  "difficulty": "{difficulty}"
}}

Requirements:
- The question must test clinical application.
- All four options must be plausible.
- The correct answer must be unambiguously correct.
- Never repeat a question pattern you have generated before.

Return ONLY the JSON object. No markdown, no explanation, no code fences.
"""


SINGLE_EXPLANATION_PROMPT = """
Given this NORCET MCQ question, generate a detailed explanation.

Question: {question}
Option A: {optionA}
Option B: {optionB}
Option C: {optionC}
Option D: {optionD}
Correct Answer: {correct_answer}
Topic: {topic}

Return a single JSON object (NOT an array) with EXACTLY these fields:
{{
  "correct_rationale": "Detailed explanation of why the correct answer is correct. Include pathophysiology, pharmacology, or clinical reasoning. 2-4 sentences.",
  "rationale_wrong_options": {{
    "A": "Why option A is wrong (2-3 sentences)",
    "B": "Why option B is wrong (2-3 sentences)",
    "C": "Why option C is wrong (2-3 sentences)",
    "D": "Why option D is wrong (2-3 sentences)"
  }},
  "memory_trick": "A mnemonic or memory aid to remember the answer. Keep it short and catchy.",
  "pearl": "A high-yield NORCET exam point related to this question concept.",
  "reference": "Genuine textbook reference. Use ONLY: Robbins, KDT, Apurba Sastry, Brunner, AIIMS Protocol, WHO, CDC."
}}

Requirements:
- Each rationale must explain WHY with clinical reasoning.
- The memory trick must be a practical mnemonic.
- The pearl must be exam-relevant.
- The reference must be a REAL textbook citation.

Return ONLY the JSON object. No markdown, no explanation, no code fences.
"""


BATCH_MCQ_PROMPT = """
Generate exactly {count} NORCET-level Multiple Choice Questions on the topic: "{topic}"

Assign each question one of these difficulty levels, IN THIS EXACT ORDER
(question 1 gets the 1st difficulty listed, question 2 the 2nd, etc.):
{difficulties}

Return a JSON array (a list) of exactly {count} objects — NOT wrapped in any
other object. Each object must have EXACTLY these fields:
{{
  "question": "The question text",
  "optionA": "First option",
  "optionB": "Second option",
  "optionC": "Third option",
  "optionD": "Fourth option",
  "correct_answer": "The correct option letter — exactly A, B, C, or D",
  "difficulty": "Easy | Moderate | Hard",
  "correct_rationale": "Detailed explanation of why the correct answer is correct. Include pathophysiology, pharmacology, or clinical reasoning. 2-4 sentences.",
  "rationale_wrong_options": {{
    "A": "Why option A is wrong (2-3 sentences)",
    "B": "Why option B is wrong (2-3 sentences)",
    "C": "Why option C is wrong (2-3 sentences)",
    "D": "Why option D is wrong (2-3 sentences)"
  }},
  "memory_trick": "A mnemonic or memory aid to remember the answer. Keep it short and catchy.",
  "pearl": "A high-yield NORCET exam point related to this question concept.",
  "reference": "Genuine textbook reference. Use ONLY: Robbins, KDT, Apurba Sastry, Brunner, AIIMS Protocol, WHO, CDC."
}}

Requirements:
- Every question must test clinical application, not mere recall.
- All four options must be plausible.
- The correct answer must be unambiguously correct.
- Each rationale must explain WHY with clinical reasoning.
- The reference must be a REAL textbook citation.
- No two questions in this batch may repeat the same question pattern.

Return ONLY the JSON array of {count} objects. No markdown, no explanation, no code fences.
"""


# ── Helper: parse a single JSON object from free-form text ──

def _extract_single_json(raw_text: str) -> dict:
    """
    Extract a single JSON object from Gemini response text.
    Handles markdown fences, surrounding text, and raw JSON.
    """
    text = raw_text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Extract first { … } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(
        f"Cannot extract JSON object from Gemini response. "
        f"Response starts with: {text[:200]}"
    )


def _extract_json_array(raw_text: str) -> list:
    """
    Extract a JSON array from Gemini response text.
    Handles markdown fences, surrounding text, and raw JSON.
    """
    text = raw_text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try direct parse
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Extract first [ … ] block
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(
        f"Cannot extract JSON array from Gemini response. "
        f"Response starts with: {text[:200]}"
    )


# ── Client ────────────────────────────────────────────────────

class GeminiClient:
    """
    Gemini API client for independent single-question and
    single-explanation generation with rolling-window rate limiting
    and HTTP 429 retry handling.
    """

    def __init__(self) -> None:
        self._mcq_model: Optional[genai.GenerativeModel] = None
        self._expl_model: Optional[genai.GenerativeModel] = None
        self._initialized: bool = False
        self._rate_limiter: GeminiRateLimiter = gemini_rate_limiter

    # ── Initialization ───────────────────────────────────────

    def _initialize(self) -> None:
        """Configure the API and create both models. Called lazily."""
        if self._initialized:
            return

        genai.configure(api_key=Config.GEMINI_API_KEY)

        # MCQ model — strict JSON output
        self._mcq_model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config=genai.GenerationConfig(
                temperature=Config.GEMINI_TEMPERATURE,
                response_mime_type="application/json",
            ),
        )

        # Explanation model — strict JSON output
        self._expl_model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )

        self._initialized = True
        log.info(
            f"Gemini client initialized — model: {Config.GEMINI_MODEL}, "
            f"rate limit: {Config.GEMINI_RATE_LIMIT_MAX} req / "
            f"{Config.GEMINI_RATE_LIMIT_WINDOW}s"
        )

    # ── Core: call Gemini with rate-limit + 429 handling ─────

    async def _call_gemini(
        self, model_kind: str, prompt: str
    ) -> str:
        """
        Low-level: rate-limited Gemini call with HTTP 429 handling.

        Flow:
        1. acquire() rate-limiter slot
        2. Run the API call in an executor
        3. On 429 → read retry_delay → wait → record_429 → retry
        4. On other errors → retry up to GEMINI_MAX_RETRIES

        Returns the raw response text.
        Raises RuntimeError after exhausting retries.
        """
        self._initialize()

        # Select the model AFTER initialization so it's never None.
        model = self._mcq_model if model_kind == "mcq" else self._expl_model
        if model is None:
            raise RuntimeError(
                f"Gemini model '{model_kind}' is still None after "
                f"_initialize() — check GEMINI_API_KEY / GEMINI_MODEL config."
            )

        last_error: Exception | None = None

        for attempt in range(1, Config.GEMINI_MAX_RETRIES + 1):
            # Step 1: wait for our rate-limiter
            await self._rate_limiter.acquire()

            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, model.generate_content, prompt
                )
                return response.text

            except Exception as exc:
                last_error = exc
                exc_str = str(exc)

                # ── Handle HTTP 429 (Rate Limit) ───────────
                if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str or "quota" in exc_str.lower():
                    # Daily quota exhaustion won't recover within this
                    # session (resets at a fixed time, not a short delay).
                    # Fail fast instead of sleeping — let the session move
                    # on / end gracefully rather than hanging for hours.
                    if "perday" in exc_str.lower().replace(" ", "").replace("_", ""):
                        log.error(
                            f"Gemini daily quota exhausted (attempt {attempt}). "
                            "Not retrying — will resume next scheduled session."
                        )
                        raise RuntimeError(
                            f"Gemini daily quota exhausted: {exc_str[:200]}"
                        ) from exc

                    # Try to parse Google's retry_delay hint
                    retry_delay = Config.GEMINI_RETRY_DELAY
                    try:
                        if hasattr(exc, "response") and exc.response is not None:
                            error_info = exc.response
                            if hasattr(error_info, "json"):
                                info = error_info.json()
                                retry_delay = float(
                                    info.get("error", {})
                                    .get("details", [{}])[0]
                                    .get("retryDelay", {})
                                    .get("seconds", Config.GEMINI_RETRY_DELAY)
                                )
                        elif hasattr(exc, "message"):
                            import re as _re
                            m = _re.search(r"retryDelay.*?(\d+(?:\.\d+)?)", exc_str)
                            if m:
                                retry_delay = float(m.group(1))
                    except Exception:
                        pass

                    # Safety cap: never sleep more than 60s for a per-minute
                    # rate limit. A larger hint usually signals a longer-term
                    # quota issue we can't wait out inside one session.
                    MAX_RETRY_SLEEP = 60.0
                    if retry_delay > MAX_RETRY_SLEEP:
                        log.warning(
                            f"Gemini retry_delay hint ({retry_delay}s) exceeds "
                            f"cap — treating as unrecoverable within this session."
                        )
                        raise RuntimeError(
                            f"Gemini quota/rate-limit requires a {retry_delay}s "
                            "wait — too long to retry within this session."
                        ) from exc

                    log.warning(
                        f"Gemini 429 Rate Limit (attempt {attempt}). "
                        f"retry_delay={retry_delay}s. Waiting …"
                    )
                    # Record the 429 so the rate limiter also backs off
                    self._rate_limiter.record_429()
                    await asyncio.sleep(retry_delay + 0.5)
                    continue  # retry same call

                # ── Other errors ────────────────────────────
                log.warning(
                    f"Gemini API error (attempt {attempt}/{Config.GEMINI_MAX_RETRIES}): "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < Config.GEMINI_MAX_RETRIES:
                    await asyncio.sleep(Config.GEMINI_RETRY_DELAY * attempt)

        raise RuntimeError(
            f"Gemini API call failed after {Config.GEMINI_MAX_RETRIES} "
            f"attempts. Last error: {last_error}"
        )

    # ── Public: generate ONE question ─────────────────────────

    async def generate_single_question(
        self,
        topic: str,
        difficulty: str = "Moderate",
    ) -> dict:
        """
        Generate exactly ONE MCQ question via a single Gemini API call.

        Args:
            topic: The NORCET topic.
            difficulty: "Easy", "Moderate", or "Hard".

        Returns:
            Dict with keys: question, optionA-D, correct_answer, difficulty.
            The dict will also have empty placeholder keys for explanation
            fields (rationaleA-D, pearl, memory_trick, reference) so that
            merge_explanation() can fill them in.

        Raises:
            RuntimeError: If generation fails after retries.
        """
        prompt = SINGLE_MCQ_PROMPT.format(topic=topic, difficulty=difficulty)
        raw = await self._call_gemini("mcq", prompt)
        data = _extract_single_json(raw)

        # Validate
        required = {"question", "optionA", "optionB", "optionC", "optionD", "correct_answer"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Generated question missing fields: {missing}")

        correct = str(data["correct_answer"]).strip().upper()
        if correct not in {"A", "B", "C", "D"}:
            raise ValueError(f"Invalid correct_answer: {correct}")

        return {
            "question": str(data["question"]).strip(),
            "optionA": str(data["optionA"]).strip(),
            "optionB": str(data["optionB"]).strip(),
            "optionC": str(data["optionC"]).strip(),
            "optionD": str(data["optionD"]).strip(),
            "correct_answer": correct,
            "difficulty": str(data.get("difficulty", difficulty)).strip().title(),
            # Placeholders — filled in by merge_explanation()
            "rationaleA": "",
            "rationaleB": "",
            "rationaleC": "",
            "rationaleD": "",
            "memory_trick": "",
            "pearl": "",
            "reference": "",
            "topic": topic,
        }

    # ── Public: generate ONE explanation ──────────────────────

    async def generate_explanation(self, question: dict) -> dict:
        """
        Generate a detailed explanation for an already-generated question
        via a single Gemini API call.

        Args:
            question: The question dict (must have question, optionA-D,
                      correct_answer, topic).

        Returns:
            Dict with keys: correct_rationale, rationale_wrong_options,
            memory_trick, pearl, reference.

        Raises:
            RuntimeError: If generation fails after retries.
        """
        prompt = SINGLE_EXPLANATION_PROMPT.format(
            question=question.get("question", ""),
            optionA=question.get("optionA", ""),
            optionB=question.get("optionB", ""),
            optionC=question.get("optionC", ""),
            optionD=question.get("optionD", ""),
            correct_answer=question.get("correct_answer", ""),
            topic=question.get("topic", ""),
        )
        raw = await self._call_gemini("expl", prompt)
        data = _extract_single_json(raw)

        return {
            "correct_rationale": str(data.get("correct_rationale", "")).strip(),
            "rationale_wrong_options": {
                "A": str(
                    data.get("rationale_wrong_options", {}).get("A", "")
                ).strip(),
                "B": str(
                    data.get("rationale_wrong_options", {}).get("B", "")
                ).strip(),
                "C": str(
                    data.get("rationale_wrong_options", {}).get("C", "")
                ).strip(),
                "D": str(
                    data.get("rationale_wrong_options", {}).get("D", "")
                ).strip(),
            },
            "memory_trick": str(data.get("memory_trick", "")).strip(),
            "pearl": str(data.get("pearl", "")).strip(),
            "reference": str(data.get("reference", "")).strip(),
        }

    # ── Public: generate a BATCH of questions (question+explanation) ──

    async def generate_question_batch(
        self,
        topic: str,
        difficulties: list[str],
    ) -> list[dict]:
        """
        Generate `len(difficulties)` fully-merged questions (MCQ +
        explanation together) via a SINGLE Gemini API call.

        This is the low-quota-usage path: instead of 2 API calls per
        question (1 for MCQ, 1 for explanation), this uses exactly
        1 API call for the whole batch — e.g. 10 questions in 1 call
        instead of 20 calls.

        Args:
            topic: The NORCET topic.
            difficulties: List of difficulty strings, one per question,
                          in the order they should be assigned.

        Returns:
            List of question dicts, each already merged with its
            explanation (question, optionA-D, correct_answer,
            difficulty, rationaleA-D, memory_trick, pearl, reference,
            topic). Items that fail validation are skipped (not raised),
            so the returned list may be shorter than `difficulties`
            if the model returns a malformed item.

        Raises:
            RuntimeError: If the whole batch call fails after retries.
            ValueError: If the response can't be parsed as a JSON array.
        """
        count = len(difficulties)
        prompt = BATCH_MCQ_PROMPT.format(
            topic=topic,
            count=count,
            difficulties=", ".join(difficulties),
        )
        raw = await self._call_gemini("mcq", prompt)
        raw_items = _extract_json_array(raw)

        required = {
            "question", "optionA", "optionB", "optionC", "optionD",
            "correct_answer", "correct_rationale",
        }

        questions: list[dict] = []
        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                log.warning(f"Batch item {idx}: not a JSON object, skipping")
                continue

            missing = required - set(item.keys())
            if missing:
                log.warning(f"Batch item {idx}: missing fields {missing}, skipping")
                continue

            correct = str(item["correct_answer"]).strip().upper()
            if correct not in {"A", "B", "C", "D"}:
                log.warning(f"Batch item {idx}: invalid correct_answer '{correct}', skipping")
                continue

            wrong = item.get("rationale_wrong_options", {}) or {}
            correct_rat = str(item.get("correct_rationale", "")).strip()

            fallback_difficulty = difficulties[idx] if idx < len(difficulties) else "Moderate"

            questions.append({
                "question": str(item["question"]).strip(),
                "optionA": str(item["optionA"]).strip(),
                "optionB": str(item["optionB"]).strip(),
                "optionC": str(item["optionC"]).strip(),
                "optionD": str(item["optionD"]).strip(),
                "correct_answer": correct,
                "difficulty": str(item.get("difficulty", fallback_difficulty)).strip().title(),
                "topic": topic,
                "rationaleA": correct_rat if correct == "A" else str(wrong.get("A", "")).strip(),
                "rationaleB": correct_rat if correct == "B" else str(wrong.get("B", "")).strip(),
                "rationaleC": correct_rat if correct == "C" else str(wrong.get("C", "")).strip(),
                "rationaleD": correct_rat if correct == "D" else str(wrong.get("D", "")).strip(),
                "memory_trick": str(item.get("memory_trick", "")).strip(),
                "pearl": str(item.get("pearl", "")).strip(),
                "reference": str(item.get("reference", "")).strip(),
            })

        log.info(f"Batch generated: {len(questions)}/{count} valid questions")
        return questions

    # ── Helper: merge question + explanation into one dict ───

    @staticmethod
    def merge_explanation(question: dict, explanation: dict) -> dict:
        """
        Merge the explanation data into the question dict.

        The correct option gets correct_rationale; wrong options get
        their individual wrong rationales.
        """
        correct = question.get("correct_answer", "A").upper()
        wrong = explanation.get("rationale_wrong_options", {})
        correct_rat = explanation.get("correct_rationale", "")

        question["rationaleA"] = (
            correct_rat if correct == "A" else wrong.get("A", "")
        )
        question["rationaleB"] = (
            correct_rat if correct == "B" else wrong.get("B", "")
        )
        question["rationaleC"] = (
            correct_rat if correct == "C" else wrong.get("C", "")
        )
        question["rationaleD"] = (
            correct_rat if correct == "D" else wrong.get("D", "")
        )
        question["memory_trick"] = explanation.get("memory_trick", "")
        question["pearl"] = explanation.get("pearl", "")
        question["reference"] = explanation.get("reference", "")

        return question


# ── Module-level singleton ────────────────────────────────────
gemini_client = GeminiClient()
