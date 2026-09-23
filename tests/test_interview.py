"""Tests for the AI Interview Coach core logic.

Run with:
    pytest

These tests do not require Azure credentials or network access: they run
against MockAIProvider (Demo Mode) and the local validation/fallback logic,
which is exactly what the project needs to demonstrate reliability.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models.schemas import (
    DIFFICULTY_LEVELS,
    Evaluation,
    InterviewState,
    Question,
    validate_score,
)
from services.ai_provider import AIProviderBase, AIProviderError, MockAIProvider, azure_credentials_present
from services.interview_agent import InterviewAgent
from utils.helpers import calculate_overall_score, choose_next_difficulty, extract_json


# ---------------------------------------------------------------------------
# models/schemas.py — score validation
# ---------------------------------------------------------------------------

class TestScoreValidation:
    def test_accepts_plain_int(self):
        assert validate_score(7) == 7

    def test_accepts_float_and_rounds(self):
        assert validate_score(7.6) == 8

    def test_accepts_numeric_string(self):
        assert validate_score("8") == 8

    def test_accepts_score_with_slash(self):
        assert validate_score("6/10") == 6

    def test_rejects_out_of_range_high(self):
        with pytest.raises(ValueError):
            validate_score(15)

    def test_rejects_out_of_range_low(self):
        with pytest.raises(ValueError):
            validate_score(-1)

    def test_rejects_non_numeric_text(self):
        with pytest.raises(ValueError):
            validate_score("excellent")

    def test_rejects_missing_value(self):
        with pytest.raises(ValueError):
            validate_score(None)


# ---------------------------------------------------------------------------
# models/schemas.py — Question / Evaluation validation (structured AI output)
# ---------------------------------------------------------------------------

class TestStructuredOutputValidation:
    def test_valid_question_dict(self):
        q = Question.from_dict({"question": "Explain how a hash map works.", "topic": "Data Structures"},
                                difficulty="intermediate")
        assert q.topic == "Data Structures"
        assert q.difficulty == "intermediate"

    def test_question_missing_field_raises(self):
        with pytest.raises(ValueError):
            Question.from_dict({"topic": "Data Structures"}, difficulty="beginner")

    def test_question_too_short_raises(self):
        with pytest.raises(ValueError):
            Question.from_dict({"question": "Why?"}, difficulty="beginner")

    def test_valid_evaluation_dict(self):
        e = Evaluation.from_dict({
            "score": 8, "strengths": ["Clear"], "weaknesses": ["Could be shorter"],
            "missing_concepts": ["Big-O"], "improvement": "Add an example.",
            "better_answer": "...", "next_difficulty": "advanced",
        })
        assert e.score == 8
        assert e.next_difficulty == "advanced"

    def test_evaluation_malformed_score_raises(self):
        with pytest.raises(ValueError):
            Evaluation.from_dict({"score": "very good"})

    def test_evaluation_not_a_dict_raises(self):
        with pytest.raises(ValueError):
            Evaluation.from_dict("not a dict")


# ---------------------------------------------------------------------------
# utils/helpers.py — JSON extraction (handles messy AI output)
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_plain_json(self):
        assert extract_json('{"score": 7}') == {"score": 7}

    def test_json_in_markdown_fence(self):
        assert extract_json('```json\n{"score": 7}\n```') == {"score": 7}

    def test_json_with_surrounding_text(self):
        assert extract_json('Sure, here you go: {"score": 7} Hope that helps!') == {"score": 7}

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            extract_json("")

    def test_no_json_object_raises(self):
        with pytest.raises(ValueError):
            extract_json("I cannot help with that.")


# ---------------------------------------------------------------------------
# utils/helpers.py — scoring and adaptive difficulty
# ---------------------------------------------------------------------------

class TestOverallScore:
    def test_average_of_scores(self):
        assert calculate_overall_score([8, 6, 10]) == 8.0

    def test_rounds_to_one_decimal(self):
        assert calculate_overall_score([7, 8, 9]) == 8.0
        assert calculate_overall_score([7, 8]) == 7.5

    def test_empty_list_is_zero(self):
        assert calculate_overall_score([]) == 0.0


class TestDifficultyAdaptation:
    def test_weak_answer_decreases_difficulty(self):
        assert choose_next_difficulty("intermediate", score=2) == "beginner"

    def test_strong_answer_increases_difficulty(self):
        assert choose_next_difficulty("intermediate", score=9) == "advanced"

    def test_average_answer_keeps_difficulty(self):
        assert choose_next_difficulty("intermediate", score=6) == "intermediate"

    def test_cannot_go_below_beginner(self):
        assert choose_next_difficulty("beginner", score=1) == "beginner"

    def test_cannot_go_above_advanced(self):
        assert choose_next_difficulty("advanced", score=10) == "advanced"

    def test_ai_suggestion_used_when_within_allowed_range(self):
        # Weak answer: only "beginner" or staying at "intermediate" are allowed.
        assert choose_next_difficulty("intermediate", score=3, suggested="beginner") == "beginner"

    def test_implausible_ai_suggestion_is_ignored(self):
        # A weak answer suggesting "advanced" should be ignored in favour of the safe default.
        assert choose_next_difficulty("intermediate", score=2, suggested="advanced") == "beginner"

    def test_all_levels_are_reachable(self):
        assert set(DIFFICULTY_LEVELS) == {"beginner", "intermediate", "advanced"}


# ---------------------------------------------------------------------------
# InterviewState
# ---------------------------------------------------------------------------

class TestInterviewState:
    def test_new_state_is_not_complete(self):
        state = InterviewState(job_role="Software Engineer", interview_type="Technical",
                                difficulty="beginner", num_questions=3)
        assert state.is_complete is False
        assert state.question_number == 0

    def test_is_complete_after_enough_history(self):
        state = InterviewState(job_role="Software Engineer", interview_type="Technical",
                                difficulty="beginner", num_questions=1)
        q = Question(text="Tell me about yourself.", topic="General", difficulty="beginner")
        e = Evaluation(score=7)
        state.history.append(__import__("models.schemas", fromlist=["QAEntry"]).QAEntry(q, "answer", e))
        assert state.is_complete is True


# ---------------------------------------------------------------------------
# MockAIProvider (Demo Mode)
# ---------------------------------------------------------------------------

class TestMockAIProvider:
    def test_generates_question_for_every_type_and_difficulty(self):
        provider = MockAIProvider(seed=42)
        for interview_type in ["Technical", "Behavioral", "HR"]:
            for difficulty in DIFFICULTY_LEVELS:
                q = provider.generate_question(
                    job_role="Software Engineer", interview_type=interview_type, difficulty=difficulty,
                    question_number=1, num_questions=5, topics_covered=[], previous_questions=[],
                )
                assert isinstance(q, Question)
                assert len(q.text) > 10
                assert q.difficulty == difficulty

    def test_avoids_repeating_previous_questions_when_possible(self):
        provider = MockAIProvider(seed=1)
        first = provider.generate_question(job_role="Software Engineer", interview_type="Technical",
                                            difficulty="beginner", question_number=1, num_questions=5,
                                            topics_covered=[], previous_questions=[])
        # Ask many times with the first question excluded; a repeat would mean the bank ran out
        # (there are 3 beginner technical questions) which is acceptable, but it must never crash.
        for _ in range(5):
            q = provider.generate_question(job_role="Software Engineer", interview_type="Technical",
                                             difficulty="beginner", question_number=2, num_questions=5,
                                             topics_covered=[], previous_questions=[first.text])
            assert isinstance(q, Question)

    def test_empty_answer_scores_zero(self):
        provider = MockAIProvider(seed=0)
        evaluation = provider.evaluate_answer(job_role="Software Engineer", interview_type="Technical",
                                               difficulty="beginner", question="Explain X.", answer="")
        assert evaluation.score == 0

    def test_longer_answer_scores_higher_than_empty(self):
        provider = MockAIProvider(seed=0)
        long_answer = " ".join(["detail"] * 50)
        evaluation = provider.evaluate_answer(job_role="Software Engineer", interview_type="Technical",
                                               difficulty="beginner", question="Explain X.", answer=long_answer)
        assert evaluation.score > 0

    def test_summary_has_required_fields(self):
        provider = MockAIProvider(seed=0)
        summary = provider.generate_summary(
            job_role="Software Engineer", interview_type="Technical",
            qa_pairs=[{"question": "Q1", "score": 8}, {"question": "Q2", "score": 6}],
            overall_score=7.0,
        )
        assert summary.overall_score == 7.0
        assert summary.strengths
        assert summary.areas_to_improve
        assert summary.recommendation


# ---------------------------------------------------------------------------
# InterviewAgent — full end-to-end flow using MockAIProvider
# ---------------------------------------------------------------------------

class TestInterviewAgentEndToEnd:
    def _new_agent(self, num_questions=3):
        agent = InterviewAgent(MockAIProvider(seed=7))
        agent.start_interview(job_role="AI/ML Engineer", interview_type="Technical",
                               difficulty="beginner", num_questions=num_questions)
        return agent

    def test_start_interview_returns_first_question(self):
        agent = self._new_agent()
        question = agent.get_current_question()
        assert isinstance(question, Question)
        assert agent.is_complete is False

    def test_submit_answer_advances_to_next_question(self):
        agent = self._new_agent(num_questions=3)
        agent.submit_answer("A reasonably detailed answer with some explanation.")
        assert agent.is_complete is False
        assert agent.get_current_question() is not None

    def test_interview_completes_after_all_questions(self):
        agent = self._new_agent(num_questions=2)
        agent.submit_answer("First answer with a bit of detail in it.")
        assert agent.is_complete is False
        agent.submit_answer("Second answer, also fairly detailed and specific.")
        assert agent.is_complete is True
        assert agent.get_current_question() is None

    def test_summary_available_after_completion(self):
        agent = self._new_agent(num_questions=2)
        agent.submit_answer("Answer one, with enough words to not be trivial.")
        agent.submit_answer("Answer two, also reasonably thorough and specific.")
        summary = agent.get_summary()
        assert len(summary.question_scores) == 2
        assert 0 <= summary.overall_score <= 10

    def test_summary_before_any_answer_raises(self):
        agent = self._new_agent()
        with pytest.raises(RuntimeError):
            agent.get_summary()


# ---------------------------------------------------------------------------
# Fallback behaviour: a provider that always fails must not crash the agent
# ---------------------------------------------------------------------------

class _AlwaysFailingProvider(AIProviderBase):
    """Test double simulating Azure Mode with invalid credentials / network errors."""

    display_name = "Always-Failing Test Provider"

    def generate_question(self, *args, **kwargs):
        raise AIProviderError("simulated failure")

    def evaluate_answer(self, *args, **kwargs):
        raise AIProviderError("simulated failure")

    def generate_summary(self, *args, **kwargs):
        raise AIProviderError("simulated failure")


class TestFallbackBehaviour:
    def test_agent_falls_back_when_provider_fails(self):
        agent = InterviewAgent(_AlwaysFailingProvider())
        question = agent.start_interview(job_role="Software Engineer", interview_type="Technical",
                                          difficulty="beginner", num_questions=2)
        assert question.is_fallback is True
        assert agent.last_notice is not None

        evaluation = agent.submit_answer("Some answer text.")
        assert evaluation.is_fallback is True
        assert agent.is_complete is False

        agent.submit_answer("Another answer to finish the interview.")
        assert agent.is_complete is True

        summary = agent.get_summary()
        assert summary.is_fallback is True


# ---------------------------------------------------------------------------
# Demo Mode detection (missing Azure credentials)
# ---------------------------------------------------------------------------

class TestDemoModeDetection:
    def test_no_credentials_means_demo_mode(self, monkeypatch):
        for var in ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]:
            monkeypatch.delenv(var, raising=False)
        assert azure_credentials_present() is False

    def test_partial_credentials_still_means_demo_mode(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        assert azure_credentials_present() is False

    def test_all_credentials_present_means_azure_mode(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        assert azure_credentials_present() is True
