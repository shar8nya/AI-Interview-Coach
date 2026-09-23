"""AI prompt templates.

Keeping every prompt in one file (instead of scattering f-strings through the
agent code) makes the "prompt engineering" part of the project easy to find,
read and explain during the presentation.

Every prompt instructs the model to reply with ONLY a JSON object matching a
fixed schema ("structured AI output"). services/ai_provider.py parses that
JSON with utils/helpers.extract_json and models/schemas validates it.
"""

from typing import List, Optional

# Shared instruction: keeps evaluation criteria fair (Responsible AI) and the
# tone constructive, on every single prompt.
RESPONSIBLE_AI_RULES = (
    "You are an interview practice tool, not a real recruiter. Evaluate only the "
    "content of the answer: accuracy, relevance, technical understanding, "
    "communication and completeness. Never consider or mention the candidate's "
    "gender, race, ethnicity, religion, age, accent, name, or any other protected "
    "characteristic. Be constructive and encouraging, never mocking or harsh."
)

SYSTEM_PROMPT = (
    "You are an experienced, friendly technical interviewer running a mock interview "
    "practice session. " + RESPONSIBLE_AI_RULES + " "
    "Always reply with ONLY a single valid JSON object and no other text, no markdown "
    "code fences, and no explanation outside the JSON."
)


def question_prompt(job_role: str, interview_type: str, difficulty: str,
                     question_number: int, num_questions: int,
                     topics_covered: List[str], previous_questions: List[str]) -> str:
    """Prompt for generating the next interview question."""
    covered = ", ".join(topics_covered) if topics_covered else "none yet"
    asked = "\n".join(f"- {q}" for q in previous_questions) if previous_questions else "(none yet)"
    return f"""Generate interview question {question_number} of {num_questions}.

Job role: {job_role}
Interview type: {interview_type} (Technical = coding/CS concepts, Behavioral = past
experience using the STAR method, HR = culture fit, motivation, career goals; Mixed = a balanced combination)
Difficulty level: {difficulty}
Topics already covered this interview: {covered}
Questions already asked (do NOT repeat these or ask something near-identical):
{asked}

Write ONE new, clear, self-contained interview question appropriate for the role,
type and difficulty above. Prefer a topic that has not been covered yet.

Reply with ONLY this JSON object:
{{
  "question": "the interview question text",
  "topic": "short topic label, e.g. 'Data Structures' or 'Teamwork'"
}}"""


def evaluation_prompt(job_role: str, interview_type: str, difficulty: str,
                       question: str, answer: str) -> str:
    """Prompt for evaluating the candidate's answer to one question."""
    return f"""Evaluate this mock interview answer.

Job role: {job_role}
Interview type: {interview_type}
Difficulty: {difficulty}
Question: {question}
Candidate's answer: {answer}

Score the answer from 0 to 10 based on accuracy, relevance, technical understanding,
communication and completeness. Then suggest whether the next question should be
"beginner", "intermediate" or "advanced": pick a level EASIER than the current one if
the answer was weak, HARDER if it was strong, or the SAME level otherwise.

Reply with ONLY this JSON object:
{{
  "score": 7,
  "strengths": ["short point", "short point"],
  "weaknesses": ["short point"],
  "missing_concepts": ["concept the answer should have mentioned"],
  "improvement": "one or two sentences of specific, actionable advice",
  "better_answer": "a short example of a stronger answer to this exact question",
  "next_difficulty": "beginner | intermediate | advanced"
}}"""


def summary_prompt(job_role: str, interview_type: str, qa_pairs: List[dict],
                    overall_score: float) -> str:
    """Prompt for the final end-of-interview summary.

    `qa_pairs` is a list of {"question": str, "score": int} dicts. The overall
    score is calculated by our own code (not the AI) and passed in for context.
    """
    lines = "\n".join(f"- Q{i+1} ({p['score']}/10): {p['question']}" for i, p in enumerate(qa_pairs))
    return f"""The mock interview is complete.

Job role: {job_role}
Interview type: {interview_type}
Overall score: {overall_score}/10
Questions and per-question scores:
{lines}

Write a short overall performance summary for the candidate.

Reply with ONLY this JSON object:
{{
  "strengths": ["overall strength across the interview", "another strength"],
  "areas_to_improve": ["concrete area to work on", "another area"],
  "recommendation": "two or three sentences of encouraging, specific next-step advice"
}}"""


def build_messages(system_extra: Optional[str], user_prompt: str) -> List[dict]:
    """Build the OpenAI/Azure-style messages list for one request."""
    system_content = SYSTEM_PROMPT if not system_extra else f"{SYSTEM_PROMPT} {system_extra}"
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]
