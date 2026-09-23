"""Small helper functions used across the project.

Everything here is plain Python (no Azure, no Streamlit), which makes it easy
to unit-test and easy to explain.
"""

import json
import re
from typing import Any, Dict, List, Optional

from models.schemas import DIFFICULTY_LEVELS, normalize_difficulty


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_environment() -> None:
    """Load variables from a local .env file, if python-dotenv is installed.

    Missing python-dotenv or a missing .env file is fine: the app simply
    continues (and will run in Demo Mode if no Azure variables are set).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


# ---------------------------------------------------------------------------
# Structured output parsing
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from an AI reply.

    Language models sometimes wrap JSON in ```json fences or add a sentence
    before/after it. This function handles those cases and raises ValueError
    if no valid JSON object can be found.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The AI response was empty")

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: take everything between the first "{" and the last "}".
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object found in the AI response")
        data = json.loads(cleaned[start:end + 1])  # may raise JSONDecodeError (a ValueError)

    if not isinstance(data, dict):
        raise ValueError("The AI response JSON is not an object")
    return data


# ---------------------------------------------------------------------------
# Scores and adaptive difficulty
# ---------------------------------------------------------------------------

def calculate_overall_score(scores: List[int]) -> float:
    """Average of the question scores, rounded to 1 decimal (0.0 if empty)."""
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 1)


def choose_next_difficulty(current: str, score: int, suggested: Optional[str] = None) -> str:
    """Decide the difficulty of the next question (the adaptive part).

    Default rule based on the score of the last answer:
        score 0-4  -> one level easier   (weak answer)
        score 5-7  -> same level         (okay answer)
        score 8-10 -> one level harder   (strong answer)

    The AI may *suggest* a difficulty, but the code double-checks it:
    a weak answer never leads to a harder question, a strong answer never
    leads to an easier one, and difficulty never jumps more than one level.
    Invalid suggestions are ignored and the default rule is used.
    """
    current = normalize_difficulty(current) or DIFFICULTY_LEVELS[0]
    index = DIFFICULTY_LEVELS.index(current)
    last = len(DIFFICULTY_LEVELS) - 1

    if score <= 4:
        default, allowed = max(index - 1, 0), {max(index - 1, 0), index}
    elif score >= 8:
        default, allowed = min(index + 1, last), {index, min(index + 1, last)}
    else:
        default, allowed = index, {index}

    suggested = normalize_difficulty(suggested)
    if suggested is not None and DIFFICULTY_LEVELS.index(suggested) in allowed:
        return suggested
    return DIFFICULTY_LEVELS[default]


def describe_adaptation(previous_score: int, old_difficulty: str, new_difficulty: str) -> str:
    """One-sentence, user-friendly explanation of how the interview adapted."""
    old_i = DIFFICULTY_LEVELS.index(old_difficulty)
    new_i = DIFFICULTY_LEVELS.index(new_difficulty)
    label = new_difficulty.title()
    if new_i > old_i:
        return f"You scored {previous_score}/10 on the last question, so this one is harder ({label})."
    if new_i < old_i:
        return (f"You scored {previous_score}/10 on the last question, so this one is easier "
                f"({label}) to help you rebuild the fundamentals.")
    if previous_score <= 4:
        return (f"You scored {previous_score}/10 on the last question. Difficulty is already at the lowest "
                f"level ({label}), so this question revisits the basics.")
    return f"You scored {previous_score}/10 on the last question, so the difficulty stays at {label}."


# ---------------------------------------------------------------------------
# Rule-based summary (used by Demo Mode and as the fallback if the AI fails)
# ---------------------------------------------------------------------------

def _unique(items: List[str], limit: int) -> List[str]:
    """Remove duplicates (case-insensitive) while keeping order; keep `limit` items."""
    seen, result = set(), []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result[:limit]


def build_rule_based_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the final summary from per-question results using simple rules.

    `results` is a list of dicts with the keys: score, strengths,
    weaknesses, missing_concepts.
    """
    scores = [r["score"] for r in results]
    average = calculate_overall_score(scores)

    # Strengths: the first strength of the best-scoring answers.
    best_first = sorted(results, key=lambda r: r["score"], reverse=True)
    strengths = _unique([r["strengths"][0] for r in best_first if r.get("strengths")], 3)
    if not strengths:
        strengths = ["You completed the full practice interview."]

    # Areas to improve: missing concepts of the weakest answers.
    worst_first = sorted(results, key=lambda r: r["score"])
    concepts: List[str] = []
    for r in worst_first:
        if r["score"] <= 7:
            concepts.extend(r.get("missing_concepts") or [])
    areas = [f"Review and practise: {c}" for c in _unique(concepts, 4)]
    if not areas:
        areas = ["Keep practising with more detailed, example-backed answers."]

    if average >= 8:
        recommendation = ("Strong practice performance. Keep sharpening your answers with concrete "
                          "examples and try a higher difficulty next time.")
    elif average >= 6:
        recommendation = ("Good foundation. Focus on the areas above, add real examples to your answers, "
                          "and repeat the interview to track your progress.")
    elif average >= 4:
        recommendation = ("You are building the basics. Revisit the concepts listed above, then practise "
                          "again at the same difficulty before moving up.")
    else:
        recommendation = ("More preparation is needed. Start with beginner-level fundamentals, study the "
                          "suggested stronger answers, and try the interview again.")
    recommendation += " Remember: this is practice feedback, not a hiring decision."

    return {"strengths": strengths, "areas_to_improve": areas, "recommendation": recommendation}


def word_count(text: str) -> int:
    """Number of words in a piece of text."""
    return len(text.split())
