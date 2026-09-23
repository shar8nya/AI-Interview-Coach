"""The interview agent.

This is the single "AI agent" in the project (the brief explicitly asks for
one clear agent, not a multi-agent system). It is responsible for:

* holding interview state (models.schemas.InterviewState),
* asking the AI provider for the next question,
* asking the AI provider to evaluate each answer,
* deciding the difficulty of the next question (the adaptive behaviour),
* falling back to safe, local logic if the AI provider fails or returns
  something invalid, instead of crashing the interview.

The agent never talks to Streamlit and never imports Azure directly -- it
only talks to an AIProviderBase (services/ai_provider.py), so it works
identically in Demo Mode and Azure Mode.
"""

from typing import List, Optional

from models.schemas import (
    DIFFICULTY_LEVELS,
    Evaluation,
    InterviewState,
    InterviewSummary,
    MAX_ANSWER_CHARS,
    QAEntry,
    Question,
)
from services.ai_provider import AIProviderBase, AIProviderError
from utils.helpers import build_rule_based_summary, calculate_overall_score, choose_next_difficulty, describe_adaptation


class InterviewAgent:
    """Runs one interview session from start to finish."""

    def __init__(self, provider: AIProviderBase):
        self.provider = provider
        self.state: Optional[InterviewState] = None
        #: Set to a short message whenever a fallback was used, so the UI can show a small notice.
        self.last_notice: Optional[str] = None

    # -- Lifecycle ----------------------------------------------------------

    def start_interview(self, job_role: str, interview_type: str, difficulty: str,
                         num_questions: int) -> Question:
        """Begin a new interview and return the first question."""
        self.state = InterviewState(
            job_role=job_role,
            interview_type=interview_type,
            difficulty=difficulty,
            num_questions=num_questions,
        )
        return self._generate_next_question()

    def submit_answer(self, answer: str) -> Evaluation:
        """Evaluate the current question's answer, then prepare the next question.

        Returns the Evaluation so the UI can display it immediately. Call
        `get_current_question()` afterwards to get the next question (or
        check `is_complete` to know the interview has ended).
        """
        if self.state is None or self.state.current_question is None:
            raise RuntimeError("No active question. Call start_interview() first.")

        answer = (answer or "").strip()[:MAX_ANSWER_CHARS]
        question = self.state.current_question
        self.last_notice = None

        try:
            evaluation = self.provider.evaluate_answer(
                job_role=self.state.job_role,
                interview_type=self.state.interview_type,
                difficulty=self.state.difficulty,
                question=question.text,
                answer=answer,
            )
        except AIProviderError as exc:
            evaluation = self._fallback_evaluation(answer)
            self.last_notice = f"AI evaluation had an issue ({exc}); used a local fallback score instead."

        self.state.history.append(QAEntry(question=question, answer=answer, evaluation=evaluation))
        if question.topic not in self.state.topics_covered:
            self.state.topics_covered.append(question.topic)

        # Adaptive step: decide the next question's difficulty from this answer's score.
        new_difficulty = choose_next_difficulty(self.state.difficulty, evaluation.score,
                                                 suggested=evaluation.next_difficulty)
        question.adaptation_note = describe_adaptation(evaluation.score, self.state.difficulty, new_difficulty)
        self.state.difficulty = new_difficulty
        self.state.current_question = None

        if not self.state.is_complete:
            self._generate_next_question()

        return evaluation

    def get_current_question(self) -> Optional[Question]:
        return self.state.current_question if self.state else None

    def get_summary(self) -> InterviewSummary:
        """Build the final interview summary. Call only once `is_complete` is True."""
        if self.state is None or not self.state.history:
            raise RuntimeError("Cannot summarize an interview with no answered questions.")

        scores = self.state.scores
        overall = calculate_overall_score(scores)
        qa_pairs = [{"question": e.question.text, "score": e.evaluation.score} for e in self.state.history]

        try:
            return self.provider.generate_summary(
                job_role=self.state.job_role,
                interview_type=self.state.interview_type,
                qa_pairs=qa_pairs,
                overall_score=overall,
            )
        except AIProviderError as exc:
            self.last_notice = f"AI summary had an issue ({exc}); used a local fallback summary instead."
            return self._fallback_summary(overall, scores)

    @property
    def is_complete(self) -> bool:
        return bool(self.state and self.state.is_complete)

    # -- Internal helpers -----------------------------------------------------

    def _generate_next_question(self) -> Question:
        state = self.state
        question_number = len(state.history) + 1
        try:
            question = self.provider.generate_question(
                job_role=state.job_role,
                interview_type=state.interview_type,
                difficulty=state.difficulty,
                question_number=question_number,
                num_questions=state.num_questions,
                topics_covered=state.topics_covered,
                previous_questions=state.previous_questions,
            )
        except AIProviderError as exc:
            question = self._fallback_question(state.difficulty)
            self.last_notice = f"AI question generation had an issue ({exc}); used a local fallback question."

        state.current_question = question
        return question

    @staticmethod
    def _fallback_question(difficulty: str) -> Question:
        """Used only if the AI provider itself fails (e.g. Azure Mode network error).

        A tiny built-in question bank so the interview can always continue.
        """
        level = difficulty if difficulty in DIFFICULTY_LEVELS else "beginner"
        bank = {
            "beginner": "Tell me about a project you've worked on and your role in it.",
            "intermediate": "Describe a technical challenge you solved recently and how you approached it.",
            "advanced": "How would you design a system to handle a sudden 10x increase in traffic?",
        }
        return Question(text=bank[level], topic="General", difficulty=level, is_fallback=True)

    @staticmethod
    def _fallback_evaluation(answer: str) -> Evaluation:
        """Simple rule-based evaluation used only when the AI provider fails."""
        words = len(answer.split())
        if words == 0:
            score, note = 0, "No answer was provided."
        elif words < 15:
            score, note = 3, "The answer was quite brief."
        elif words < 40:
            score, note = 6, "The answer covered the basics."
        else:
            score, note = 8, "The answer was detailed."
        return Evaluation(
            score=score,
            strengths=["Attempted the question"] if words else [],
            weaknesses=[note],
            missing_concepts=["more supporting detail"] if score < 8 else [],
            improvement="Add specific examples and explain your reasoning step by step.",
            better_answer="A stronger answer would define the concept clearly and back it up with an example.",
            next_difficulty=None,
            is_fallback=True,
        )

    def _fallback_summary(self, overall_score: float, scores: List[int]) -> InterviewSummary:
        results = [{"score": e.evaluation.score, "strengths": e.evaluation.strengths,
                    "weaknesses": e.evaluation.weaknesses, "missing_concepts": e.evaluation.missing_concepts}
                   for e in self.state.history]
        data = build_rule_based_summary(results)
        summary = InterviewSummary.from_dict(data, overall_score, scores)
        summary.is_fallback = True
        return summary
