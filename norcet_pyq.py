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
    """
    return (
        "NORCET PYQ QUESTION STYLE GUIDE (based on NORCET-10 Prelims & Mains analysis):\n\n"
        "VARIETY REQUIREMENT - Every batch MUST include a MIX of these question types. "
        "Do NOT generate all questions in the same format. Rotate through:\n\n"
        "1. CLINICAL SCENARIO + NURSING ACTION (highest weight ~20%):\n"
        "   Describe patient, setting, vitals/findings. Ask: 'What should the nurse do FIRST?' "
        "or 'Which nursing intervention is correct?'\n"
        "   Example: 'A 45-year-old patient is rushed into the emergency department with "
        "severe abdominal pain... blood glucose 520 mg/dL... What should be the first nursing action?'\n\n"
        "2. FACTUAL RECALL (~15%):\n"
        "   Direct factual question: lab cutoff, drug dosage, normal range, definition.\n"
        "   Example: 'The fasting blood glucose (FBS) cut-off value for diagnosis of diabetes mellitus is?'\n\n"
        "3. NEGATIVE FRAMING - NOT / EXCEPT (~8%):\n"
        "   'All of the following are correct EXCEPT' or 'Which is NOT a sign of...'\n"
        "   Three correct options, one wrong (or vice versa).\n\n"
        "4. PRIORITY / FIRST ACTION (~10%):\n"
        "   'What should the nurse do FIRST?' or 'IMMEDIATE action'\n"
        "   Use ABC framework, Maslow hierarchy, or nursing process.\n\n"
        "5. SUPERLATIVE - MOST / BEST / LEAST (~8%):\n"
        "   'MOST important benefit', 'BEST approach', 'LEAST likely'\n"
        "   All options plausible but one clearly superior.\n\n"
        "6. LAB VALUE INTERPRETATION (~8%):\n"
        "   Provide specific lab values with units. Ask for interpretation or staging.\n"
        "   Example: 'Urine output 20 mL/hr, serum creatinine 3.6 mg/dL. RIFLE stage?'\n\n"
        "7. DRUG / PHARMACOLOGY (~8%):\n"
        "   Drug action, contraindication, side effect, administration route, nursing consideration.\n\n"
        "8. ANATOMY / STRUCTURE (~5%):\n"
        "   Anatomical landmarks, injection sites, nerves, vessels.\n\n"
        "9. SEQUENCING / ORDERING (~3%):\n"
        "   List 3-5 steps. Ask to arrange in correct order.\n"
        "   Present options as sequences like '4>3>1>2'.\n\n"
        "10. PROGRAM / POLICY (~5%):\n"
        "   LaQshya, RCH, NHM, JSSK, PMSMA, ASHA, ANM norms.\n\n"
        "11. DIFFERENTIATION / COMPARISON (~5%):\n"
        "   'What differentiates Condition A from Condition B?'\n\n"
        "12. EMERGENCY / CRITICAL CARE (~5%):\n"
        "   DKA, shock, hemorrhage, cardiac arrest, CPR, burns, poisoning.\n\n"
        "13. GROWTH & DEVELOPMENT MILESTONES (~3%):\n"
        "   Pregnancy milestones, developmental norms, immunization schedule.\n\n"
        "14. VITAL SIGN TREND INTERPRETATION (~2%):\n"
        "   Series of vital signs over time. Ask what condition the trend indicates.\n\n"
        "15. CAUSE / REASON (~3%):\n"
        "   'This symptom is due to which cause?' - pathophysiology reasoning.\n\n"
        "16. MENTAL HEALTH / PSYCHIATRY (~3%):\n"
        "   Therapeutic communication, treatment approach, coping mechanisms.\n\n"
        "17. PROCEDURE / SKILL (~3%):\n"
        "   Nursing procedure technique, equipment, patient preparation.\n\n"
        "18. COMMUNITY HEALTH / STATISTICS (~2%):\n"
        "   Epidemiological rates, survey methods, vital statistics.\n\n"
        "19. INFECTION CONTROL (~2%):\n"
        "   Asepsis, isolation precautions, PPE, sterilisation.\n\n"
        "20. NUTRITION / METABOLIC (~2%):\n"
        "   BMI, malnutrition, vitamin deficiencies, diet recommendations.\n\n"
        "STYLE RULES:\n"
        "- Questions should be concise (1-3 sentences for stem)\n"
        "- Options should be plausible and similar in length\n"
        "- Avoid 'All of the above' as an option\n"
        "- Use proper medical terminology\n"
        "- Include specific values/numbers when testing factual knowledge\n"
        "- Clinical scenarios should specify age, gender, setting, and key findings\n"
        "- Question difficulty should match the assigned level (Easy/Moderate/Hard)\n"
    )
