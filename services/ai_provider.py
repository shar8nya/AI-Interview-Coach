"""AI provider abstraction.

This is the one place in the project that talks to an AI model. Everything
else (the interview agent, the Streamlit UI) calls the same three methods
regardless of which provider is active:

    generate_question(...)   -> models.schemas.Question
    evaluate_answer(...)     -> models.schemas.Evaluation
    generate_summary(...)    -> models.schemas.InterviewSummary

Two providers implement that interface:

    AzureAIProvider  - calls Azure OpenAI (Microsoft Foundry-compatible).
    MockAIProvider   - local, offline "Demo Mode" provider used when Azure
                       credentials are not configured. It is clearly labelled
                       as Demo Mode everywhere in the UI; it never claims to
                       be Azure AI.

get_ai_provider() picks the right one automatically by checking environment
variables, so the rest of the app never has to know which one is running.
"""

import os
import random
from abc import ABC, abstractmethod
from typing import List, Optional

from models.schemas import Evaluation, InterviewSummary, Question
from services import prompts
from utils.helpers import build_rule_based_summary, extract_json


class AIProviderError(Exception):
    """Raised when a provider cannot produce a usable, valid response.

    The interview agent catches this and falls back to local, rule-based
    logic instead of crashing the app (see interview_agent.py).
    """


class AIProviderBase(ABC):
    """Interface every AI provider must implement."""

    #: Human-readable name shown in the Streamlit UI (e.g. "Azure AI (gpt-4o-mini)").
    display_name: str = "Unknown Provider"

    @abstractmethod
    def generate_question(self, job_role: str, interview_type: str, difficulty: str,
                           question_number: int, num_questions: int,
                           topics_covered: List[str], previous_questions: List[str]) -> Question:
        ...

    @abstractmethod
    def evaluate_answer(self, job_role: str, interview_type: str, difficulty: str,
                         question: str, answer: str) -> Evaluation:
        ...

    @abstractmethod
    def generate_summary(self, job_role: str, interview_type: str,
                          qa_pairs: List[dict], overall_score: float) -> InterviewSummary:
        ...


# ---------------------------------------------------------------------------
# Azure OpenAI provider
# ---------------------------------------------------------------------------

class AzureAIProvider(AIProviderBase):
    """Real AI provider backed by Azure OpenAI (Microsoft Foundry-compatible).

    Demonstrates: Generative AI, prompt engineering and structured AI output
    against an actual Azure-hosted LLM deployment.
    """

    display_name = "Azure AI"

    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str):
        from openai import OpenAI

        self.deployment = deployment
        self.display_name = f"Azure AI ({deployment})"

        # Microsoft Foundry's /openai/v1 endpoint uses the OpenAI client.
        # Do NOT pass api_version with a /v1 endpoint.
        base_url = endpoint.rstrip("/")

        if not base_url.endswith("/openai/v1"):
            base_url += "/openai/v1"

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0,
            max_retries=1,
        )

    def _complete(self, user_prompt: str, system_extra: Optional[str] = None) -> dict:
        """Send one chat-completion request and parse the JSON it returns."""
        try:
            response = self._client.chat.completions.create(
                model=self.deployment,
                messages=prompts.build_messages(system_extra, user_prompt),
                temperature=0.7,
                max_tokens=700,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # network error, auth error, rate limit, etc.
            raise AIProviderError(f"Azure AI request failed: {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        try:
            return extract_json(content)
        except ValueError as exc:
            raise AIProviderError(f"Azure AI returned invalid JSON: {exc}") from exc

    def generate_question(self, job_role, interview_type, difficulty, question_number,
                           num_questions, topics_covered, previous_questions) -> Question:
        prompt = prompts.question_prompt(job_role, interview_type, difficulty, question_number,
                                          num_questions, topics_covered, previous_questions)
        data = self._complete(prompt)
        try:
            return Question.from_dict(data, difficulty=difficulty)
        except ValueError as exc:
            raise AIProviderError(str(exc)) from exc

    def evaluate_answer(self, job_role, interview_type, difficulty, question, answer) -> Evaluation:
        prompt = prompts.evaluation_prompt(job_role, interview_type, difficulty, question, answer)
        data = self._complete(prompt)
        try:
            return Evaluation.from_dict(data)
        except ValueError as exc:
            raise AIProviderError(str(exc)) from exc

    def generate_summary(self, job_role, interview_type, qa_pairs, overall_score) -> InterviewSummary:
        prompt = prompts.summary_prompt(job_role, interview_type, qa_pairs, overall_score)
        data = self._complete(prompt)
        scores = [p["score"] for p in qa_pairs]
        try:
            return InterviewSummary.from_dict(data, overall_score, scores)
        except ValueError as exc:
            raise AIProviderError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Mock / Demo Mode provider
# ---------------------------------------------------------------------------

# Small bank of realistic example questions, grouped by interview type and
# difficulty, so Demo Mode feels like a real interview without calling any API.
_MOCK_QUESTIONS = {
    "Technical": {
        "beginner": [
            ("Explain the difference between a list and a tuple in Python.", "Data Structures"),
            ("What is the difference between == and === (or equivalent) in your main language?", "Language Fundamentals"),
            ("What is a REST API, in your own words?", "Web Basics"),
        ],
        "intermediate": [
            ("How would you design a rate limiter for a public API?", "System Design"),
            ("Explain how a hash map works and its average time complexity for lookups.", "Data Structures"),
            ("Walk me through how you would debug a memory leak in a long-running service.", "Debugging"),
        ],
        "advanced": [
            ("Design a URL shortener that needs to handle 10,000 requests per second.", "System Design"),
            ("How would you shard a database that has outgrown a single instance?", "Databases"),
            ("Explain the CAP theorem and how it shapes a distributed system's design.", "Distributed Systems"),
        ],
    },
    "Behavioral": {
        "beginner": [
            ("Tell me about a project you are proud of and why.", "Self-awareness"),
            ("Describe a time you had to learn a new tool or technology quickly.", "Adaptability"),
        ],
        "intermediate": [
            ("Tell me about a time you disagreed with a teammate. How did you handle it?", "Teamwork"),
            ("Describe a time you missed a deadline. What happened and what did you learn?", "Accountability"),
        ],
        "advanced": [
            ("Tell me about a time you had to influence a decision without formal authority.", "Leadership"),
            ("Describe the most difficult trade-off you made under pressure and how you decided.", "Decision Making"),
        ],
    },
    "Mixed": {
        "beginner": [
            ("Tell me about a project you are proud of and the technical choices you made.", "Technical + Behavioral"),
            ("Explain a technical challenge you faced and how you solved it.", "Problem Solving"),
            ("Why are you interested in this role, and what skills would you bring?", "Motivation"),
        ],
        "intermediate": [
            ("Describe a difficult technical decision you made and how you communicated it to your team.", "Decision Making"),
            ("How would you design a scalable API, and what trade-offs would you consider?", "System Design"),
            ("Tell me about a time you received critical feedback and changed your approach.", "Adaptability"),
        ],
        "advanced": [
            ("Design a high-scale service and explain how you would balance reliability, cost and performance.", "System Design"),
            ("Describe a major engineering trade-off you would defend to a skeptical stakeholder.", "Leadership"),
            ("How would you diagnose a production incident while keeping stakeholders informed?", "Incident Management"),
        ],
    },
    "HR": {
        "beginner": [
            ("Why do you want to work for our company?", "Motivation"),
            ("Where do you see yourself in three to five years?", "Career Goals"),
        ],
        "intermediate": [
            ("Why are you looking to leave your current role or program?", "Motivation"),
            ("How do you handle a heavy workload with competing deadlines?", "Work Style"),
        ],
        "advanced": [
            ("How do you handle receiving critical feedback from a manager in front of others?", "Emotional Intelligence"),
            ("Walk me through how you'd negotiate an offer that came in below expectations.", "Negotiation"),
        ],
    },
}

_STRENGTH_POOL = [
    "Clear and structured explanation", "Used a relevant real-world example",
    "Good grasp of the core concept", "Answered the question directly",
    "Logical step-by-step reasoning",
]
_WEAKNESS_POOL = [
    "Could go deeper into the 'why', not just the 'what'",
    "Missing a concrete example to back up the point",
    "Answer could be more concise and structured",
    "Did not mention trade-offs or edge cases",
]
_CONCEPT_POOL = {
    "Data Structures": "time/space complexity", "System Design": "scalability and trade-offs",
    "Databases": "indexing strategy", "Teamwork": "specific, measurable outcome",
    "Distributed Systems": "consistency vs. availability trade-off", "Debugging": "root-cause analysis process",
    "Motivation": "connection between your goals and the role", "Leadership": "impact of the decision",
}


class MockAIProvider(AIProviderBase):
    """Offline provider used for local development and demos ("Demo Mode").

    Produces realistic-looking questions, evaluations and summaries using
    simple rules and a small text bank -- no network calls, no API key.
    Scoring is lightly heuristic (based on answer length) purely so the demo
    feels responsive; it is NOT a real AI model and the UI always says so.
    """

    display_name = "Demo Mode (Mock Provider)"

    def __init__(self, seed: Optional[int] = None):
        self._random = random.Random(seed)

    def generate_question(self, job_role, interview_type, difficulty, question_number,
                           num_questions, topics_covered, previous_questions) -> Question:
        bank = _MOCK_QUESTIONS.get(interview_type, _MOCK_QUESTIONS["Technical"])
        candidates = list(bank.get(difficulty, bank["beginner"]))
        unused = [q for q in candidates if q[0] not in previous_questions]
        text, topic = self._random.choice(unused or candidates)
        return Question(text=text, topic=topic, difficulty=difficulty)

    def evaluate_answer(self, job_role, interview_type, difficulty, question, answer) -> Evaluation:
        words = len(answer.split())
        # Very short or empty answers score low; longer, more developed answers score higher.
        # This is a simple heuristic for demo purposes only, not real language understanding.
        if words == 0:
            score = 0
        elif words < 15:
            score = self._random.randint(2, 4)
        elif words < 40:
            score = self._random.randint(5, 7)
        else:
            score = self._random.randint(7, 10)

        strengths = self._random.sample(_STRENGTH_POOL, k=2) if words > 0 else []
        weaknesses = [] if score >= 9 else self._random.sample(_WEAKNESS_POOL, k=1 if score >= 5 else 2)
        topic_guess = next((t for t in _CONCEPT_POOL if t.lower() in question.lower()), None)
        missing = [_CONCEPT_POOL[topic_guess]] if topic_guess and score < 9 else (
            ["a specific example"] if score < 9 else [])

        return Evaluation(
            score=score,
            strengths=strengths or ["Attempted the question"],
            weaknesses=weaknesses,
            missing_concepts=missing,
            improvement=("Try adding a concrete example or walking through your reasoning step by step."
                         if score < 8 else "Keep reinforcing this with real project examples."),
            better_answer=(f"A stronger answer would clearly define the concept, explain the reasoning, "
                            f"and back it up with a specific example relevant to a {job_role} role."),
            next_difficulty=None,  # the agent's own rule decides; Demo Mode does not override it
            is_fallback=False,
        )

    def generate_summary(self, job_role, interview_type, qa_pairs, overall_score) -> InterviewSummary:
        # Reuse the same rule-based logic used as the Azure fallback, so both
        # paths are tested by the same code (see utils/helpers.py).
        results = [{"score": p["score"], "strengths": ["Demo Mode summary"], "weaknesses": [],
                    "missing_concepts": []} for p in qa_pairs]
        data = build_rule_based_summary(results)
        scores = [p["score"] for p in qa_pairs]
        return InterviewSummary.from_dict(data, overall_score, scores)


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def azure_credentials_present() -> bool:
    """True if every Azure OpenAI environment variable needed is set."""
    required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
    return all(os.environ.get(name, "").strip() for name in required)


def get_ai_provider() -> AIProviderBase:
    """Return AzureAIProvider if fully configured, otherwise MockAIProvider.

    This is the single switch between Azure Mode and Demo Mode. If Azure
    credentials are present but invalid (e.g. wrong key), the provider is
    still AzureAIProvider -- errors surface per-request as AIProviderError,
    which the interview agent handles gracefully (see interview_agent.py).
    """
    if azure_credentials_present():
        try:
            return AzureAIProvider(
                endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
        except ImportError:
            # openai package not installed even though credentials are set: fall back safely.
            return MockAIProvider()
    return MockAIProvider()
