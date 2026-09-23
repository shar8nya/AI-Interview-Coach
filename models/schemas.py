"""Data structures (schemas) used by the AI Interview Coach.

Nothing in this file talks to Azure or Streamlit. It contains:

1. App-wide constants (job roles, interview types, difficulty levels).
2. Small dataclasses that hold the interview state.
3. Validation code that checks the JSON returned by the AI model
   ("structured output"). If the AI returns something invalid, these
   functions raise ValueError so the agent can retry or use a fallback.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JOB_ROLES = [
    "Software Engineer",
    "AI/ML Engineer",
    "Data Analyst",
    "Frontend Developer",
    "Backend Developer",
    "Product Manager",
]

INTERVIEW_TYPES = ["Technical", "Behavioral", "HR", "Mixed"]

# Ordered from easiest to hardest. Internally we always use lower case.
DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced"]

MIN_QUESTIONS = 3
MAX_QUESTIONS = 8
DEFAULT_QUESTIONS = 5

MIN_SCORE = 0
MAX_SCORE = 10

# Longest answer we accept. Keeps prompts small and limits what is sent to the AI.
MAX_ANSWER_CHARS = 3000


# ---------------------------------------------------------------------------
# Small cleaning / validation helpers
# ---------------------------------------------------------------------------

def _clean_text(value: Any) -> str:
    """Return a stripped string, or '' if the value is not a string."""
    return value.strip() if isinstance(value, str) else ""


def _clean_list(value: Any) -> List[str]:
    """Turn whatever the model returned into a clean list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    items = [str(item).strip() for item in value]
    return [item for item in items if item]


def normalize_difficulty(value: Any) -> Optional[str]:
    """Return 'beginner' / 'intermediate' / 'advanced', or None if invalid."""
    if isinstance(value, str) and value.strip().lower() in DIFFICULTY_LEVELS:
        return value.strip().lower()
    return None


def validate_score(value: Any) -> int:
    """Convert a score from the AI into an int between 0 and 10.

    Accepts 7, 7.6, "8" and "8/10". Anything else (missing, text, or outside
    0-10) raises ValueError, because a wrong score is worse than no score.
    """
    if isinstance(value, bool):  # True/False are technically ints in Python
        raise ValueError("Score must be a number, not a boolean")
    if isinstance(value, str) and "/" in value:
        value = value.split("/")[0]  # "8/10" -> "8"
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Score is not a number: {value!r}")
    if not (MIN_SCORE <= number <= MAX_SCORE):  # also rejects NaN
        raise ValueError(f"Score must be between {MIN_SCORE} and {MAX_SCORE}, got {value!r}")
    return int(round(number))


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Question:
    """One interview question."""

    text: str
    topic: str = "General"
    difficulty: str = "beginner"
    adaptation_note: str = ""   # short explanation of why this question was chosen
    is_fallback: bool = False   # True if the AI failed and a local fallback was used

    @classmethod
    def from_dict(cls, data: Dict[str, Any], difficulty: str) -> "Question":
        """Validate the AI's question JSON: {"question": "...", "topic": "..."}."""
        if not isinstance(data, dict):
            raise ValueError("Question response must be a JSON object")
        text = _clean_text(data.get("question"))
        if len(text) < 10:
            raise ValueError("Question text is missing or too short")
        topic = _clean_text(data.get("topic")) or "General"
        return cls(text=text, topic=topic, difficulty=difficulty)


@dataclass
class Evaluation:
    """The AI's evaluation of one answer (structured output)."""

    score: int
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    missing_concepts: List[str] = field(default_factory=list)
    improvement: str = ""
    better_answer: str = ""
    next_difficulty: Optional[str] = None  # the AI's suggestion (validated by the agent)
    is_fallback: bool = False              # True if a local fallback produced this

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evaluation":
        """Validate the AI's evaluation JSON. Raises ValueError if unusable."""
        if not isinstance(data, dict):
            raise ValueError("Evaluation response must be a JSON object")
        return cls(
            score=validate_score(data.get("score")),
            strengths=_clean_list(data.get("strengths")),
            weaknesses=_clean_list(data.get("weaknesses")),
            missing_concepts=_clean_list(data.get("missing_concepts")),
            improvement=_clean_text(data.get("improvement")),
            better_answer=_clean_text(data.get("better_answer")),
            next_difficulty=normalize_difficulty(data.get("next_difficulty")),
        )


@dataclass
class QAEntry:
    """One finished question: the question, the user's answer and the evaluation."""

    question: Question
    answer: str
    evaluation: Evaluation


@dataclass
class InterviewSummary:
    """Final report shown at the end of the interview."""

    overall_score: float
    question_scores: List[int]
    strengths: List[str]
    areas_to_improve: List[str]
    recommendation: str
    is_fallback: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any], overall_score: float,
                  question_scores: List[int]) -> "InterviewSummary":
        """Validate the AI's summary JSON.

        The numbers (overall score, per-question scores) are calculated by our
        own code, never by the AI, so they are passed in here.
        """
        if not isinstance(data, dict):
            raise ValueError("Summary response must be a JSON object")
        strengths = _clean_list(data.get("strengths"))
        areas = _clean_list(data.get("areas_to_improve"))
        recommendation = _clean_text(data.get("recommendation"))
        if not strengths or not areas or not recommendation:
            raise ValueError("Summary is missing strengths, areas_to_improve or recommendation")
        return cls(overall_score, list(question_scores), strengths, areas, recommendation)


@dataclass
class InterviewState:
    """Everything the interview agent remembers during one interview.

    The state only lives in memory (Streamlit session). Nothing is written
    to disk or to a database.
    """

    job_role: str
    interview_type: str
    difficulty: str                    # difficulty to use for the NEXT question
    num_questions: int
    question_number: int = 0           # 1-based number of the current question
    current_question: Optional[Question] = None
    history: List[QAEntry] = field(default_factory=list)
    topics_covered: List[str] = field(default_factory=list)

    @property
    def previous_questions(self) -> List[str]:
        """Text of every question asked so far (including the current one)."""
        asked = [entry.question.text for entry in self.history]
        if self.current_question is not None and self.current_question.text not in asked:
            asked.append(self.current_question.text)
        return asked

    @property
    def answers(self) -> List[str]:
        return [entry.answer for entry in self.history]

    @property
    def scores(self) -> List[int]:
        return [entry.evaluation.score for entry in self.history]

    @property
    def is_complete(self) -> bool:
        """True once every question has been answered."""
        return len(self.history) >= self.num_questions
