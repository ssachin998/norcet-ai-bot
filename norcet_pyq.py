"""
NORCET AI Bot - Previous Year Question Reference Module
======================================================
Stores extracted NORCET PYQ patterns, sample questions, and
question-type definitions used by the Gemini prompt to generate
exam-realistic questions.

Sources:
    - NORCET-10 Prelims Paper (Memory Based, 11 April 2026)
    - NORCET-10 Mains Paper (Memory Based, 30 April 2026)

Question Types Identified from PYQ Analysis:
    1. Clinical Scenario + Nursing Action    - Patient presents with X, nurse should Y
    2. Factual Recall                         - Definition, lab value, drug dosage
    3. Negative Framing (NOT/EXCEPT)          - "All are correct EXCEPT"
    4. Priority / First Action               - "What should the nurse do FIRST?"
    5. Superlative (MOST/BEST/LEAST)        - "MOST important", "BEST approach"
    6. Lab Value Interpretation              - Given lab results, identify condition
    7. Drug / Pharmacology                   - Drug action, contraindication, side effect
    8. Anatomy / Structure                  - anatomical landmark, nerve, vessel
    9. Sequencing / Ordering                 - Arrange steps in correct order
   10. Program / Policy                     - LaQshya, NHM, JSSK, RCH, ASHA, etc.
   11. Procedure / Skill                    - Injection site, suctioning, catheterisation
   12. Emergency / Critical Care            - DKA, shock, hemorrhage, cardiac arrest
   13. Differentiation / Comparison        - Condition A vs Condition B
   14. Growth & Development Milestones     - Infant, toddler, pregnancy milestones
   15. Community Health / Statistics        - Rate, ratio, survey, epidemiology
   16. Mental Health / Psychiatry           - Anxiety, OCD, schizophrenia, coping
   17. Nursing Diagnosis                    - NANDA-based diagnosis selection
   18. Nutrition / Metabolic               - BMI, malnutrition, vitamins, diet
   19. Infection Control                    - Asepsis, isolation, PPE, hand washing
   20. Cause / Reason (Assertion-Reason)    - "X happens because Y"
"""

# ── Question Type Definitions ──────────────────────────────

QUESTION_TYPES = [
    {
        "type": "clinical_scenario_nursing_action",
        "description": (
            "Patient presents with signs/symptoms in a clinical setting "
            "(emergency, ward, ICU, OPD). The nurse must choose the correct "
            "nursing action, intervention, or assessment."
        ),
        "prompt_instruction": (
            "Frame as a clinical scenario: describe the patient, setting, "
            "vitals/findings, then ask for the correct nursing action or "
            "priority intervention."
        ),
        "pyq_example": (
            "Q9. A 45-year-old patient is rushed into the emergency department "
            "with complaints of severe abdominal pain, nausea, and vomiting. "
            "On examination, the patient is found to be dehydrated, breathing "
            "deeply with Kussmaul respirations, and appears lethargic. "
            "Laboratory investigations reveal a blood glucose level of 520 mg/dL. "
            "As the nurse prepares for immediate management, what should be "
            "the first nursing action?"
        ),
    },
    {
        "type": "factual_recall",
        "description": (
            "Direct recall of a fact: lab value cutoff, drug dosage, normal "
            "range, definition, classification criteria."
        ),
        "prompt_instruction": (
            "Ask for a specific factual value, definition, or classification "
            "that a NORCET aspirant must memorize."
        ),
        "pyq_example": (
            "Q2. According to guidelines, the fasting blood glucose (FBS) "
            "cut-off value for diagnosis of diabetes mellitus is?"
        ),
    },
    {
        "type": "negative_framing",
        "description": (
            "Question uses NOT, EXCEPT, or FALSE to reverse the logic. "
            "Three correct options and one wrong option (or vice versa)."
        ),
        "prompt_instruction": (
            "Use 'NOT', 'EXCEPT', or 'FALSE' in the question stem. "
            "Three options should be correct, one should be incorrect "
            "(or three incorrect and one correct)."
        ),
        "pyq_example": (
            "Q3. Which of the following data collection methods does NOT "
            "involve a group?"
        ),
    },
    {
        "type": "priority_first_action",
        "description": (
            "Ask what the nurse should do FIRST, IMMEDIATELY, or as the "
            "INITIAL action. Tests clinical prioritization using ABC, "
            "Maslow, or nursing process framework."
        ),
        "prompt_instruction": (
            "Create a scenario where the nurse must decide the FIRST or "
            "IMMEDIATE action. Include distractors that are valid but "
            "lower-priority actions."
        ),
        "pyq_example": (
            "Q9 (Prelims). ... As the nurse prepares for immediate "
            "management, what should be the first nursing action?"
        ),
    },
    {
        "type": "superlative_most_best_least",
        "description": (
            "Uses MOST, BEST, LEAST, MOST IMPORTANT, MOST EFFECTIVE to "
            "test the ability to identify the superior option among "
            "several plausible ones."
        ),
        "prompt_instruction": (
            "Frame the question using MOST, BEST, LEAST, or MOST IMPORTANT. "
            "All options should be somewhat relevant but one clearly stands "
            "out as the best answer."
        ),
        "pyq_example": (
            "Q42 (Mains). What is the most important benefit of Peritoneal "
            "Dialysis (PD) compared to Hemodialysis (HD)?"
        ),
    },
    {
        "type": "lab_value_interpretation",
        "description": (
            "Provides specific lab values (Hb, WBC, Na+, K+, glucose, "
            "creatinine, INR, etc.) and asks the nurse to interpret "
            "the finding or identify the condition/stage."
        ),
        "prompt_instruction": (
            "Include specific lab values with units in the question. "
            "Ask for interpretation, staging (e.g., RIFLE criteria), "
            "or the condition indicated."
        ),
        "pyq_example": (
            "Q3 (Prelims). A patient with diabetes mellitus and hypertension "
            "presents with acute kidney injury. The urine output is 20 mL/hour "
            "and serum creatinine is 3.6 mg/dL. According to RIFLE criteria, "
            "what stage is this?"
        ),
    },
    {
        "type": "drug_pharmacology",
        "description": (
            "Tests knowledge of drug actions, contraindications, side "
            "effects, drug interactions, or correct administration technique."
        ),
        "prompt_instruction": (
            "Focus on a specific drug or drug class. Ask about mechanism, "
            "contraindication, expected side effect, correct administration "
            "route, or nursing consideration."
        ),
        "pyq_example": (
            "Q1 (Prelims). A lactating mother is scheduled to receive "
            "radioactive iodine-131 therapy. What advice should the nurse give?"
        ),
    },
    {
        "type": "anatomy_structure",
        "description": (
            "Tests anatomical knowledge: landmarks, nerves, vessels, "
            "injection sites, anatomical relationships."
        ),
        "prompt_instruction": (
            "Ask about an anatomical structure, landmark, injection site, "
            "or anatomical relationship relevant to nursing practice."
        ),
        "pyq_example": (
            "Q11 (Mains). The nurse is preparing to give an IM injection. "
            "Which of the following sites has maximum chance of damage to "
            "the major sciatic nerve?"
        ),
    },
    {
        "type": "sequencing_ordering",
        "description": (
            "Requires arranging nursing actions or steps in the correct "
            "sequence/order. Tests understanding of procedural flow."
        ),
        "prompt_instruction": (
            "List 3-5 nursing actions/steps and ask the user to arrange "
            "them in the correct sequence. Present 4 options each with "
            "a different ordering (e.g., 4>3>1>2)."
        ),
        "pyq_example": (
            "Q10 (Mains). While performing airway suctioning in a patient, "
            "what is the correct sequence of nursing actions? "
            "1. Insert catheter  2. Apply suction  "
            "3. Provide oxygen  4. Place the patient in semi-Fowler position"
        ),
    },
    {
        "type": "program_policy",
        "description": (
            "Tests knowledge of Indian national health programs, policies, "
            "schemes: LaQshya, RCH, NHM, JSSK, PMSMA, ASHA, ANM, "
            "sub-centre norms, etc."
        ),
        "prompt_instruction": (
            "Ask about a specific national health program, its components, "
            "guidelines, target population, or key recommendations."
        ),
        "pyq_example": (
            "Q8 (Prelims). A labour room functioning under the LaQshya "
            "program focuses on improving the quality of intrapartum and "
            "immediate postpartum care. Which of the following practices "
            "is emphasized under this program?"
        ),
    },
    {
        "type": "procedure_skill",
        "description": (
            "Tests knowledge of nursing procedures, techniques, or "
            "equipment usage: catheterisation, suctioning, sterilisation, "
            "enema, wound care, etc."
        ),
        "prompt_instruction": (
            "Describe a nursing procedure and ask about the correct "
            "technique, equipment, patient preparation, or post-procedure "
            "care."
        ),
        "pyq_example": (
            "Q10 (Mains). While performing airway suctioning in a patient, "
            "what is the correct sequence of nursing actions?"
        ),
    },
    {
        "type": "differentiation_comparison",
        "description": (
            "Requires distinguishing between two similar conditions, "
            "findings, or procedures. Tests discriminative knowledge."
        ),
        "prompt_instruction": (
            "Present two similar conditions/findings and ask what "
            "differentiates them, or what finding is specific to one "
            "and not the other."
        ),
        "pyq_example": (
            "Q100 (Mains). A pregnant woman presents with vaginal bleeding "
            "in early pregnancy. Ultrasound shows a viable fetus. Which of "
            "the following findings best differentiates Threatened Abortion "
            "from Inevitable Abortion?"
        ),
    },
    {
        "type": "growth_development_milestones",
        "description": (
            "Tests knowledge of developmental milestones, pregnancy "
            "milestones, immunization schedules, anthropometric norms."
        ),
        "prompt_instruction": (
            "Ask about a specific developmental milestone, pregnancy "
            "milestone, expected weight/height, or immunization schedule."
        ),
        "pyq_example": (
            "Q106 (Mains). A pregnant mother asks the nurse: 'At how many "
            "weeks of gestation can fetal heart sounds (FHS) typically be "
            "heard using Doppler ultrasound?'"
        ),
    },
    {
        "type": "emergency_critical_care",
        "description": (
            "Tests knowledge of emergency nursing: DKA management, shock, "
            "hemorrhage, cardiac arrest, CPR, burns, poisoning, snake bite."
        ),
        "prompt_instruction": (
            "Create an emergency scenario with vital signs, presenting "
            "symptoms. Ask about the immediate/first action, correct "
            "management, or nursing priority."
        ),
        "pyq_example": (
            "Q9 (Prelims). A 45-year-old patient is rushed into the "
            "emergency department... blood glucose 520 mg/dL... DKA. "
            "What should be the first nursing action?"
        ),
    },
    {
        "type": "cause_reason_assertion",
        "description": (
            "Tests understanding of WHY something happens - pathophysiology, "
            "causation, reasoning. Can be framed as 'because', 'due to', "
            "'the reason is'."
        ),
        "prompt_instruction": (
            "Ask about the underlying cause, mechanism, or reason for "
            "a clinical finding, symptom, or nursing action."
        ),
        "pyq_example": (
            "Q2 (Prelims). A pregnant woman in her second trimester "
            "complains of frequent heartburn and acid reflux. The nurse "
            "understands that this symptom is most likely due to which of "
            "the following causes?"
        ),
    },
    {
        "type": "community_health_statistics",
        "description": (
            "Tests knowledge of epidemiological rates, ratios, definitions, "
            "survey methods, vital statistics, demographic indicators."
        ),
        "prompt_instruction": (
            "Ask about a specific epidemiological rate, ratio, survey "
            "method, or community health statistic."
        ),
        "pyq_example": (
            "Q3 (Mains). Which of the following data collection methods "
            "does NOT involve a group?"
        ),
    },
    {
        "type": "mental_health_psychiatry",
        "description": (
            "Tests knowledge of psychiatric conditions, therapeutic "
            "communication, treatment approaches, coping mechanisms."
        ),
        "prompt_instruction": (
            "Describe a patient with a psychiatric condition or behavioral "
            "pattern. Ask about the correct nursing approach, therapeutic "
            "communication, or treatment."
        ),
        "pyq_example": (
            "Q44 (Prelims). A patient with OCD repeatedly washes hands due "
            "to fear of contamination. What is the best treatment approach?"
        ),
    },
    {
        "type": "nutrition_metabolic",
        "description": (
            "Tests knowledge of nutrition: BMI calculation, malnutrition "
            "assessment, vitamin deficiencies, diet recommendations, "
            "metabolic disorders."
        ),
        "prompt_instruction": (
            "Ask about a nutritional assessment, diet recommendation, "
            "vitamin/mineral deficiency, or metabolic condition."
        ),
        "pyq_example": "",
    },
    {
        "type": "vital_sign_trend_interpretation",
        "description": (
            "Provides a series of vital sign measurements over time and "
            "asks the nurse to interpret the trend and identify the "
            "underlying condition."
        ),
        "prompt_instruction": (
            "Present vital signs at multiple time points in a table or "
            "list format. Ask what condition or complication the trend "
            "indicates."
        ),
        "pyq_example": (
            "Q126 (Mains). A patient is 3 hours post-operative. "
            "8 AM: 120/80, 78, 37C | 10 AM: 110/70, 102, 37.2C | "
            "11 AM: 96/60, 122, 37.5C. Based on these findings, "
            "what is the most likely cause?"
        ),
    },
    {
        "type": "infection_control",
        "description": (
            "Tests knowledge of infection prevention: asepsis, isolation "
            "precautions, PPE, hand hygiene, sterilisation methods, "
            "biomedical waste management."
        ),
        "prompt_instruction": (
            "Ask about infection control measures, correct PPE usage, "
            "isolation type, sterilisation method, or waste management."
        ),
        "pyq_example": "",
    },
    # ── General Aptitude / Reasoning section ──────────────────
    # NORCET papers include a non-clinical General Aptitude section
    # (logical reasoning, verbal reasoning, English, computer
    # awareness) alongside the nursing-subject questions above. These
    # types should ONLY be used for a topic that IS the aptitude
    # section (e.g. "General Aptitude & Reasoning") — mixing a seating
    # arrangement puzzle into a Cardiovascular System batch would be
    # thematically wrong. See BATCH_MCQ_PROMPT in gemini.py for how
    # this is gated by topic.
    {
        "type": "logical_reasoning",
        "description": (
            "Non-clinical logical/analytical reasoning: seating "
            "arrangements, blood relations, syllogisms, coding-decoding, "
            "direction sense, series completion."
        ),
        "prompt_instruction": (
            "Write a self-contained logic puzzle (seating arrangement, "
            "blood relation, coding-decoding, or series) with a single "
            "unambiguous correct answer."
        ),
        "pyq_example": (
            "P, Q, R, S, T, U are sitting in a circle. Q is sitting 2nd left to P. "
            "T is between Q and R. S is not the neighbour of P. Who is sitting right to R?"
        ),
    },
    {
        "type": "verbal_reasoning",
        "description": (
            "Word-based reasoning: jumbled words/letters, analogies, "
            "odd-one-out, word relationships."
        ),
        "prompt_instruction": (
            "Write a word-puzzle question — rearrange jumbled letters into "
            "a meaningful word, or an analogy/odd-one-out question."
        ),
        "pyq_example": "Rearrange the alphabet into a meaningful word: CIFIAPC",
    },
    {
        "type": "english_language",
        "description": (
            "Basic English usage: synonyms, antonyms, grammar, sentence "
            "correction, one-word substitution."
        ),
        "prompt_instruction": (
            "Ask for a synonym, antonym, correct grammatical form, or "
            "one-word substitution of a common English word."
        ),
        "pyq_example": "Choose the antonym of the word amicable.",
    },
    {
        "type": "computer_knowledge",
        "description": (
            "Basic computer/IT awareness: hardware, software, storage "
            "devices, internet/networking basics, MS Office basics."
        ),
        "prompt_instruction": (
            "Ask a basic computer-awareness fact question (hardware "
            "component, storage speed/type, common software function, "
            "or basic networking term)."
        ),
        "pyq_example": "Which of the following has the fastest data access speed?",
    },
]


# ── Representative PYQ Samples (for prompt injection) ─────

PRELIMS_PYQ_SAMPLES = [
    "A lactating mother is scheduled to receive radioactive iodine-131 therapy. What advice should the nurse give?",
    "A pregnant woman in her second trimester complains of frequent heartburn and acid reflux, especially after meals. The nurse understands that this symptom is most likely due to which of the following causes?",
    "A patient with diabetes mellitus and hypertension presents with acute kidney injury. The urine output is 20 mL/hour and serum creatinine is 3.6 mg/dL. According to RIFLE criteria, what stage is this?",
    "A labour room functioning under the LaQshya program focuses on improving the quality of intrapartum and immediate postpartum care. Which of the following practices is emphasized under this program?",
    "A 45-year-old patient is rushed into the emergency department with complaints of severe abdominal pain, nausea, and vomiting. On examination, the patient is found to be dehydrated, breathing deeply with Kussmaul respirations, and appears lethargic. Laboratory investigations reveal a blood glucose level of 520 mg/dL. As the nurse prepares for immediate management, what should be the first nursing action?",
    "A 2-year-old child is brought to the emergency department and diagnosed with an ear infection. Which nursing action is most appropriate?",
    "A patient with OCD repeatedly washes hands due to fear of contamination. What is the best treatment approach?",
    "A Cardiotocography (CTG) tracing shows a sinusoidal pattern. What does this indicate?",
    "A 46-year-old patient complains of flank pain and is scheduled for a pelvic ultrasound. What instruction should the nursing officer provide?",
    "A patient is being monitored in the post-anesthesia care unit (PACU) following coronary bypass surgery. Which is the correct nursing intervention?",
]

MAINS_PYQ_SAMPLES = [
    "According to guidelines, the fasting blood glucose (FBS) cut-off value for diagnosis of diabetes mellitus is?",
    "Which of the following data collection methods does NOT involve a group?",
    "While performing airway suctioning in a patient, what is the correct sequence of nursing actions? 1. Insert catheter 2. Apply suction 3. Provide oxygen 4. Place the patient in semi-Fowler position",
    "The nurse is preparing to give an IM injection. Which of the following sites has maximum chance of damage to the major sciatic nerve?",
    "What is the most important benefit of Peritoneal Dialysis (PD) compared to Hemodialysis (HD)?",
    "Nurse Jeremy is evaluating a client's fluid intake and output. The client's intake is 1800 mL and output is 2200 mL over 8 hours. What nursing action is most appropriate?",
    "A child presents with vomiting. Laboratory results show a serum sodium level of 128 mEq/L. What condition does this indicate?",
    "A male adult patient diagnosed with COPD shows signs of dyspnea. Which nursing intervention is most appropriate?",
    "A pregnant woman presents with vaginal bleeding in early pregnancy. Ultrasound shows a viable fetus. Which of the following findings best differentiates Threatened Abortion from Inevitable Abortion?",
    "In a patient soon after mild activity, his heart rate rises from 80 beats/min to 130 beats/min. As the nurse evaluates this change, what is the most likely underlying cause?",
    "A pregnant mother asks the nurse: At how many weeks of gestation can fetal heart sounds (FHS) typically be heard using Doppler ultrasound?",
    "A woman in labor is undergoing Active Management of the Third Stage of Labor (AMTSL). The uterus is boggy, and the nursing officer is performing controlled cord traction to deliver the placenta. What complication should the nurse assess for?",
    "A patient is 3 hours post-operative. Vital signs: 8 AM 120/80 78bpm 37C | 10 AM 110/70 102bpm 37.2C | 11 AM 96/60 122bpm 37.5C. Based on these findings, what is the most likely cause?",
    "A 25-year-old female presents with amenorrhea for 2.5 months, abdominal pain, and vaginal bleeding for one day. On examination, vitals are stable, bleeding is seen from the OS, and the uterus is soft. What is the most likely diagnosis?",
]


def get_all_question_types() -> list[str]:
    """Return a list of all question type names."""
    return [qt["type"] for qt in QUESTION_TYPES]


def get_question_type_description(type_name: str) -> str:
    """Return the description for a given question type."""
    for qt in QUESTION_TYPES:
        if qt["type"] == type_name:
            return qt["description"]
    return ""


def get_random_type() -> dict:
    """Return a random question type definition."""
    import random
    return random.choice(QUESTION_TYPES)


def get_pyq_style_guidance() -> str:
    """
    Return a comprehensive style guide string for the Gemini prompt,
    compiled from PYQ analysis.

    FIX: this used to be a hand-typed string that only embedded a real
    pyq_example for ~3 of the 20 QUESTION_TYPES entries (the other 17
    had rich, genuine examples sitting in QUESTION_TYPES that never
    actually reached the prompt). This version builds itself FROM
    QUESTION_TYPES programmatically, so every type that has a real
    example includes it here.
    """
    lines = [
        "NORCET PYQ QUESTION STYLE GUIDE (based on NORCET-10 Prelims & Mains analysis):\n",
        "VARIETY REQUIREMENT - Every batch MUST include a MIX of these question types. "
        "Do NOT generate all questions in the same format. Rotate through:\n",
    ]
    for i, qt in enumerate(QUESTION_TYPES, 1):
        label = qt["type"].replace("_", " ").upper()
        lines.append(f"{i}. {label}:")
        lines.append(f"   {qt['prompt_instruction']}")
        if qt.get("pyq_example"):
            lines.append(f"   Real PYQ-style example: \"{qt['pyq_example']}\"")
        lines.append("")

    lines.append(
        "IMPORTANT — TOPIC GATING: the last 4 types above (Logical Reasoning, "
        "Verbal Reasoning, English Language, Computer Knowledge) are a separate "
        "General Aptitude section of NORCET, NOT nursing content. Use them ONLY "
        "if the topic given to you IS itself about general aptitude, reasoning, "
        "English, or computer knowledge. For any clinical/nursing topic "
        "(Anatomy, Pharmacology, Medical-Surgical Nursing, etc.), ignore these "
        "4 entirely and draw only from the clinical types above.\n"
    )
    lines.append(
        "NOTE: this list covers the most common NORCET patterns, but is not "
        "exhaustive — if the topic and difficulty naturally call for a valid "
        "question format not listed here (e.g. a numerical dosage calculation, "
        "match-the-following, or a short multi-statement assertion-reason "
        "question), use good judgment rather than forcing every question into "
        "one of the categories above.\n"
    )
    lines.append(
        "STYLE RULES:\n"
        "- Questions should be concise (1-3 sentences for stem)\n"
        "- Options should be plausible and similar in length\n"
        "- Avoid 'All of the above' as an option\n"
        "- Use proper medical terminology\n"
        "- Include specific values/numbers when testing factual knowledge\n"
        "- Clinical scenarios should specify age, gender, setting, and key findings\n"
        "- Question difficulty should match the assigned level (Easy/Moderate/Hard)\n"
    )
    return "\n".join(lines)


# Types that belong to NORCET's General Aptitude section, not nursing
# content — kept separate so random sampling doesn't leak a seating-
# arrangement or antonym example into a clinical topic's prompt.
_APTITUDE_TYPES = {"logical_reasoning", "verbal_reasoning", "english_language", "computer_knowledge"}

# Specific phrases, not bare single words — "computer" or "reasoning"
# alone are too loose (see _NURSING_CONTEXT_WORDS below for why).
_APTITUDE_POSITIVE_PHRASES = (
    "general aptitude",
    "logical reasoning",
    "verbal reasoning",
    "english language",
    "computer knowledge",
    "computer awareness",
    "computer fundamentals",
    "quantitative aptitude",
    "numerical ability",
    "reasoning ability",
    "reasoning & aptitude",
    "reasoning and aptitude",
    "general knowledge",
    " gk",
    "gk ",
)

# If a topic contains ANY of these, it's a real nursing/clinical
# subject no matter what else it mentions — overrides the positive
# phrases above. This is what correctly keeps "Computer Applications
# in Nursing" and "Clinical Reasoning in Nursing Practice" classified
# as clinical topics instead of General Aptitude, even though they
# contain "computer"/"reasoning".
_NURSING_CONTEXT_WORDS = (
    "nursing", "clinical", "patient", "health", "medical", "care",
    "informatics", "hospital", "disease", "therapy", "treatment",
    "diagnosis", "surgical", "pediatric", "obstetric", "psychiatric",
)


def _is_aptitude_topic(topic: str) -> bool:
    """
    Decide whether a topic belongs to NORCET's General Aptitude
    section (logical/verbal reasoning, English, computer knowledge)
    versus a nursing/clinical subject.

    Nursing-context words always win, even over a positive aptitude
    phrase match — a topic like "Computer Applications in Nursing" or
    "Clinical Reasoning in Nursing Practice" is real nursing content,
    not general computer-literacy or logic-puzzle material, despite
    containing "computer"/"reasoning".
    """
    topic_lower = topic.lower()
    if any(w in topic_lower for w in _NURSING_CONTEXT_WORDS):
        return False
    return any(phrase in topic_lower for phrase in _APTITUDE_POSITIVE_PHRASES)


def get_applicable_question_types(topic: str) -> list[str]:
    """
    Return the list of question-type ids applicable to a topic —
    clinical types for a nursing subject, or the 4 General Aptitude
    types if the topic itself is about aptitude/reasoning/English/
    computer knowledge. Same gating logic as get_random_pyq_samples(),
    exposed separately so callers (generate_question_batch,
    telegram_poll.py) can FORCE a specific type per question rather
    than just showing examples and hoping Gemini varies them.
    """
    if _is_aptitude_topic(topic):
        return [qt["type"] for qt in QUESTION_TYPES if qt["type"] in _APTITUDE_TYPES]
    return [qt["type"] for qt in QUESTION_TYPES if qt["type"] not in _APTITUDE_TYPES]


def get_random_pyq_samples(topic: str = "", n: int = 5) -> str:
    """
    Return n real PYQ-style examples, EACH FROM A DIFFERENT question
    type (picked randomly from QUESTION_TYPES, which is type-tagged).

    Topic-aware: if `topic` looks like a General Aptitude/Reasoning/
    English/Computer topic, samples are drawn ONLY from those 4 types.
    Otherwise (the normal nursing-subject case), those 4 are excluded
    entirely so a clinical topic never gets a stray reasoning-puzzle
    or antonym example mixed into its style guidance.

    FIX: this used to random.sample() from the flat, untagged
    PRELIMS_PYQ_SAMPLES + MAINS_PYQ_SAMPLES pool — nothing stopped it
    from picking 4 examples that were all "clinical scenario" style by
    chance, missing rarer types like sequencing or differentiation
    entirely in a given call. Sampling from QUESTION_TYPES instead
    guarantees the n examples shown are always n DIFFERENT types, and
    each is labeled with its type so Gemini sees a concrete example
    matching each style it's asked to vary across, not just an
    abstract instruction to "mix it up."

    Default n=5 roughly matches Config.BATCH_SIZE (5 questions/call),
    so there's about one type-example per question generated.
    """
    import random

    if _is_aptitude_topic(topic):
        typed = [qt for qt in QUESTION_TYPES if qt["type"] in _APTITUDE_TYPES and qt.get("pyq_example")]
    else:
        typed = [qt for qt in QUESTION_TYPES if qt["type"] not in _APTITUDE_TYPES and qt.get("pyq_example")]

    n = min(n, len(typed))
    picks = random.sample(typed, n)
    lines = [
        "REAL NORCET PYQ EXAMPLES — each a DIFFERENT question type "
        "(for style calibration only — do NOT copy these, write NEW "
        "original questions in this style):"
    ]
    for i, qt in enumerate(picks, 1):
        label = qt["type"].replace("_", " ").title()
        lines.append(f"{i}. [{label}] \"{qt['pyq_example']}\"")
    return "\n".join(lines)
