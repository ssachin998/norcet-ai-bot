"""
NORCET AI Bot - Google Gemini API Module
======================================
Handles communication with the Google Gemini 2.5 Flash API for
generating NORCET-level MCQ questions.

Features:
    - Structured JSON output
    - Batch question generation
    - Automatic retry with exponential backoff
    - Difficulty-aware generation
    - Duplicate-aware prompting
"""

import json
import asyncio
import time
from typing import Optional

import google.generativeai as genai

from config import Config
from logger import log
from database import get_all_question_hashes, generate_question_hash


# ── Gemini Prompt Templates ────────────────────────────────────

SYSTEM_INSTRUCTION = (
    "You are a senior nursing professor and NORCET question paper setter "
    "at AIIMS New Delhi. You have 20+ years of experience setting competitive "
    "examination questions for B.Sc Nursing, Post Basic B.Sc Nursing, and "
    "M.Sc Nursing entrance examinations (NORCET).\n\n"
    "Your questions MUST:\n"
    "- Resemble AIIMS NORCET Previous Year Questions in style and rigor\n"
    "- Test clinical application, not mere recall\n"
    "- Be factually accurate and evidence-based\n"
    "- Have ONLY genuine references from standard textbooks (Robbins, KDT, "
    "Apurba Sastry, Brunner, AIIMS Protocol, WHO guidelines, CDC guidelines)\n"
    "- Never fabricate references\n"
    "- Each option rationale must explain WHY it is correct or incorrect "
    "with specific pathophysiological or clinical reasoning\n"
    "- The 'pearl' field should contain a high-yield clinical pearl "
    "relevant to the question concept\n"
    "- Questions must be original and unique, never copied from any source\n"
    "- Use proper medical terminology\n"
    "- Avoid negative phrasing unless clinically necessary\n"
    "- Every question must have exactly ONE correct answer\n\n"
    "Return ONLY valid JSON array. No markdown, no explanation, no extra text."
)

MCQ_GENERATION_PROMPT = """
Generate {count} NORCET-level Multiple Choice Questions on the topic: "{topic}"

Difficulty distribution for this batch:
- Easy: {easy_pct}% (straightforward, tests basic knowledge)
- Moderate: {moderate_pct}% (requires clinical reasoning, application-level)
- Hard: {hard_pct}% (tests deep understanding, multi-concept integration)

IMPORTANT REQUIREMENTS:
1. Return a JSON array of exactly {count} question objects.
2. Each object must have EXACTLY these fields:
   - "question": The question text (string)
   - "optionA": First option (string)
   - "optionB": Second option (string)
   - "optionC": Third option (string)
   - "optionD": Fourth option (string)
   - "correct_answer": The correct option letter, exactly "A", "B", "C", or "D"
   - "rationaleA": Detailed explanation of why option A is correct or incorrect
   - "rationaleB": Detailed explanation of why option B is correct or incorrect
   - "rationaleC": Detailed explanation of why option C is correct or incorrect
   - "rationaleD": Detailed explanation of why option D is correct or incorrect
   - "pearl": A high-yield NORCET pearl/tip related to this question concept
   - "reference": Genuine textbook reference with edition and page if possible
     (Use ONLY: Robbins, KDT, Apurba Sastry, Brunner, AIIMS Protocol, WHO, CDC)
   - "difficulty": "Easy", "Moderate", or "Hard"

3. The rationales must be DETAILED clinical explanations, not one-liners.
4. Each rationale should be 2-4 sentences explaining the pathophysiology,
   pharmacology, or clinical reasoning.
5. References must be REAL. If you cite Robbins, cite the specific chapter/concept.
6. Never generate similar questions or questions you've generated before.

{existing_hashes_note}

Return ONLY the JSON array. No markdown fences, no commentary.
Example format:
[
  {{
    "question": "A 45-year-old patient...",
    "optionA": "...",
    "optionB": "...",
    "optionC": "...",
    "optionD": "...",
    "correct_answer": "B",
    "rationaleA": "...",
    "rationaleB": "...",
    "rationaleC": "...",
    "rationaleD": "...",
    "pearl": "...",
    "reference": "Robbins Basic Pathology, 10th Edition, Chapter 5",
    "difficulty": "Moderate"
  }}
]
"""


class GeminiClient:
    """
    Client for Google Gemini API to generate NORCET MCQ questions.

    Handles API initialization, question generation with retry logic,
    JSON parsing, and validation of generated questions.
    """

    def __init__(self) -> None:
        self._model: Optional[genai.GenerativeModel] = None
        self._initialized: bool = False

    def _initialize(self) -> None:
        """Initialize the Gemini API client. Called lazily."""
        if self._initialized:
            return

        genai.configure(api_key=Config.GEMINI_API_KEY)

        generation_config = genai.GenerationConfig(
            temperature=Config.GEMINI_TEMPERATURE,
            response_mime_type="application/json",
        )

        self._model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config=generation_config,
        )
        self._initialized = True
        log.info(f"Gemini client initialized with model: {Config.GEMINI_MODEL}")

    def _generate_prompt(
        self,
        topic: str,
        count: int,
        difficulties: Optional[list[str]] = None,
    ) -> str:
        """
        Generate the full prompt for the Gemini API call.

        Args:
            topic: The NORCET topic to generate questions for.
            count: Number of questions to generate.
            difficulties: Optional list of difficulty labels for each question.

        Returns:
            The formatted prompt string.
        """
        if difficulties:
            easy_pct = round(difficulties.count("Easy") / count * 100)
            moderate_pct = round(difficulties.count("Moderate") / count * 100)
            hard_pct = round(difficulties.count("Hard") / count * 100)
        else:
            easy_pct = round(Config.DIFFICULTY_EASY * 100)
            moderate_pct = round(Config.DIFFICULTY_MODERATE * 100)
            hard_pct = round(Config.DIFFICULTY_HARD * 100)

        # Optionally include note about existing hashes
        existing_hashes_note = ""
        try:
            all_hashes = get_all_question_hashes()
            if all_hashes:
                existing_hashes_note = (
                    f"NOTE: The database already contains {len(all_hashes)} questions. "
                    "Generate completely NEW and UNIQUE questions. Do not repeat "
                    "any concepts or question patterns."
                )
        except Exception:
            pass

        return MCQ_GENERATION_PROMPT.format(
            count=count,
            topic=topic,
            easy_pct=easy_pct,
            moderate_pct=moderate_pct,
            hard_pct=hard_pct,
            existing_hashes_note=existing_hashes_note,
        )

    async def generate_questions(
        self,
        topic: str,
        count: int,
        difficulties: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Generate NORCET MCQ questions using the Gemini API.

        Args:
            topic: The topic to generate questions for.
            count: Number of questions to generate.
            difficulties: Optional list of difficulty labels.

        Returns:
            List of validated question dictionaries.

        Raises:
            RuntimeError: If generation fails after all retries.
            ValueError: If the API returns invalid data.
        """
        self._initialize()

        prompt = self._generate_prompt(topic, count, difficulties)
        last_error: Exception | None = None

        for attempt in range(1, Config.GEMINI_MAX_RETRIES + 1):
            try:
                log.info(
                    f"Generating {count} questions for topic '{topic}' "
                    f"(attempt {attempt}/{Config.GEMINI_MAX_RETRIES})"
                )

                # Run synchronous Gemini call in executor to avoid blocking
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    self._model.generate_content,  # type: ignore
                    prompt,
                )

                raw_text = response.text
                questions = self._parse_response(raw_text)
                validated = self._validate_questions(questions, topic)

                log.info(
                    f"Successfully generated {len(validated)} valid questions "
                    f"for topic '{topic}'"
                )
                return validated

            except json.JSONDecodeError as e:
                last_error = e
                log.warning(
                    f"JSON parse error on attempt {attempt}: {e}. "
                    "Attempting cleanup and retry..."
                )
                if attempt < Config.GEMINI_MAX_RETRIES:
                    await asyncio.sleep(Config.GEMINI_RETRY_DELAY * attempt)

            except Exception as e:
                last_error = e
                log.warning(
                    f"Gemini API error on attempt {attempt}: {type(e).__name__}: {e}"
                )
                if attempt < Config.GEMINI_MAX_RETRIES:
                    await asyncio.sleep(Config.GEMINI_RETRY_DELAY * attempt)

        raise RuntimeError(
            f"Failed to generate questions after {Config.GEMINI_MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    def _parse_response(self, raw_text: str) -> list[dict]:
        """
        Parse the Gemini API response text into a list of question dicts.

        Handles various response formats:
        - Clean JSON array
        - Markdown-wrapped JSON
        - Truncated responses with partial JSON

        Args:
            raw_text: Raw text response from Gemini.

        Returns:
            List of question dictionaries.

        Raises:
            json.JSONDecodeError: If the response cannot be parsed.
        """
        text = raw_text.strip()

        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
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
            elif isinstance(data, dict) and "questions" in data:
                return data["questions"]
            else:
                raise json.JSONDecodeError(
                    "Response is not a JSON array or object with 'questions' key",
                    text, 0
                )
        except json.JSONDecodeError:
            pass

        # Try to extract JSON array from surrounding text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError(
            f"Could not extract valid JSON from response. "
            f"Response starts with: {text[:200]}",
            text, 0,
        )

    def _validate_questions(
        self, questions: list[dict], topic: str
    ) -> list[dict]:
        """
        Validate and clean generated questions.

        Ensures each question has all required fields, valid values,
        and no duplicates in the database.

        Args:
            questions: Raw list of question dicts from Gemini.
            topic: Topic name for context.

        Returns:
            List of validated question dicts (duplicates removed).
        """
        required_fields = {
            "question", "optionA", "optionB", "optionC", "optionD",
            "correct_answer", "rationaleA", "rationaleB", "rationaleC",
            "rationaleD", "pearl", "reference", "difficulty",
        }

        valid_options = {"A", "B", "C", "D"}
        valid_difficulties = {"Easy", "Moderate", "Hard"}
        validated: list[dict] = []
        duplicate_count = 0

        for i, q in enumerate(questions):
            # Check required fields
            missing = required_fields - set(q.keys())
            if missing:
                log.warning(
                    f"Question {i + 1} missing fields: {missing}. Skipping."
                )
                continue

            # Validate correct_answer
            correct = str(q["correct_answer"]).strip().upper()
            if correct not in valid_options:
                log.warning(
                    f"Question {i + 1} has invalid correct_answer '{correct}'. Skipping."
                )
                continue

            # Validate difficulty
            difficulty = str(q.get("difficulty", "Moderate")).strip().title()
            if difficulty not in valid_difficulties:
                difficulty = "Moderate"

            # Check for empty question text
            if not q["question"].strip():
                log.warning(f"Question {i + 1} has empty question text. Skipping.")
                continue

            # Check for duplicate in database
            question_hash = generate_question_hash(q["question"])
            try:
                from database import is_duplicate
                if is_duplicate(q["question"]):
                    duplicate_count += 1
                    log.info(f"Question {i + 1} is a duplicate. Skipping.")
                    continue
            except Exception as e:
                log.warning(f"Duplicate check failed for question {i + 1}: {e}")

            # Build clean question dict
            clean_q = {
                "question": q["question"].strip(),
                "optionA": str(q["optionA"]).strip(),
                "optionB": str(q["optionB"]).strip(),
                "optionC": str(q["optionC"]).strip(),
                "optionD": str(q["optionD"]).strip(),
                "correct_answer": correct,
                "rationaleA": str(q["rationaleA"]).strip(),
                "rationaleB": str(q["rationaleB"]).strip(),
                "rationaleC": str(q["rationaleC"]).strip(),
                "rationaleD": str(q["rationaleD"]).strip(),
                "pearl": str(q["pearl"]).strip(),
                "reference": str(q["reference"]).strip(),
                "difficulty": difficulty,
                "topic": topic,
            }
            validated.append(clean_q)

        if duplicate_count > 0:
            log.info(
                f"Removed {duplicate_count} duplicate(s) from generated batch"
            )

        return validated

    async def generate_batch(
        self,
        topic: str,
        total_count: int,
    ) -> list[dict]:
        """
        Generate a large batch of questions by splitting into API calls
        of Config.BATCH_SIZE each.

        Args:
            topic: Topic to generate questions for.
            total_count: Total number of questions needed.

        Returns:
            Combined list of all validated question dicts.
        """
        all_questions: list[dict] = []
        batches_needed = (total_count + Config.BATCH_SIZE - 1) // Config.BATCH_SIZE
        questions_remaining = total_count

        for batch_num in range(batches_needed):
            batch_size = min(Config.BATCH_SIZE, questions_remaining)
            log.info(
                f"Batch {batch_num + 1}/{batches_needed}: "
                f"Generating {batch_size} questions"
            )

            try:
                batch = await self.generate_questions(
                    topic=topic,
                    count=batch_size,
                )
                all_questions.extend(batch)
                questions_remaining -= len(batch)

                if questions_remaining <= 0:
                    break

                # Small delay between batches to respect API limits
                if batch_num < batches_needed - 1:
                    await asyncio.sleep(2)

            except Exception as e:
                log.error(
                    f"Batch {batch_num + 1} failed: {e}. "
                    f"Continuing with {len(all_questions)} questions so far."
                )
                if len(all_questions) == 0:
                    raise RuntimeError(
                        f"Failed to generate any questions. Error: {e}"
                    )

        log.info(
            f"Batch generation complete: {len(all_questions)} questions "
            f"generated for topic '{topic}'"
        )
        return all_questions


# Module-level singleton
gemini_client = GeminiClient()
