# 1. Project Title

**AI Interview Coach**

An adaptive, AI-powered mock interview simulator built for the Microsoft AI-103 (Developing AI Apps and Agents on Azure) course project.

---

# 2. Team Members

- Sharanya
- Priyal
- Shaivi Vats
- Pushkar
- Rohan Pathania

---

# 3. Problem Statement

Students and job seekers preparing for technical interviews rarely have access to realistic, on-demand practice. Mock interviews with peers or mentors are hard to schedule, static question banks don't adjust to how well someone is actually doing, and generic "practice question" websites give no personalized feedback on *why* an answer was weak or how to improve it. As a result, candidates often walk into real interviews having practiced answering questions, but never having been evaluated or coached on their answers.

# 4. Solution

**AI Interview Coach** is a Streamlit web application that simulates a one-on-one interview. The candidate picks a job role, an interview type (Technical, Behavioral, or HR) and a starting difficulty. An AI interview agent then asks a question, evaluates the candidate's answer (by typing or, optionally, by speaking it), and gives structured feedback: a score out of 10, what was done well, what was missing, and an example of a stronger answer. Crucially, the **next question adapts** to the previous answer's quality — a weak answer is followed by an easier or more fundamentals-focused question, and a strong answer is followed by a harder one. After the full round, the candidate gets an overall performance summary.

## Key Differentiator: Adaptive Questioning

Question 1 → weak answer → Question 2 is easier / targets the missing concept.
Question 1 → strong answer → Question 2 is more difficult.

This makes the tool feel like an actual interviewer reacting to the candidate, not a static list of questions read out in order.

---

# 5. Key Features

- **AI-generated interview questions**, tailored to job role, interview type and current difficulty
- **Answer evaluation** with a numeric score and structured, actionable feedback
- **Adaptive difficulty** — the agent adjusts difficulty after every answer
- **Personalized feedback**: strengths, weaknesses, missing concepts, an improvement tip, and an example of a stronger answer
- **Final interview summary**: overall score, per-question breakdown, strengths/areas to improve, and a recommendation
- **Technical / Behavioral / HR modes**, across six common job roles
- **Optional voice mode**: listen to each question read aloud and record a spoken answer, transcribed automatically — powered by Azure AI Speech (see [Architecture](#7-architecture))
- **Demo Mode**: the entire app, including voice, works offline/without any Azure account for local development and grading

---

# 6. AI-103 Concepts Used

| Concept | Where it appears |
|---|---|
| **Generative AI** | Azure OpenAI (Microsoft Foundry-compatible) generates each interview question, each evaluation, and the final summary. |
| **AI Agent** | `services/interview_agent.py` implements a single interview agent that holds state (role, difficulty, history, topics covered) and decides the next action — this is the "agentic interview flow." |
| **Prompt Engineering** | `services/prompts.py` centralizes every prompt template, with a shared Responsible-AI instruction injected into every request. |
| **Structured AI Output** | Every AI call is required to return a specific JSON schema, validated and parsed in `models/schemas.py` before use. |
| **Responsible AI** | Explicit evaluation-criteria constraints, bias-avoidance instructions, disclaimers in the UI, and no persistent storage of answers (see [Responsible AI](#14-responsible-ai)). |
| **Azure AI / Microsoft Foundry integration** | `AzureAIProvider` calls an Azure OpenAI chat-completion deployment; `SpeechService` calls Azure AI Speech for speech-to-text and text-to-speech. Both are optional and the app degrades gracefully without them. |

---

# 7. Architecture

```text
User
 ↓
Streamlit UI
 ↓
Interview Agent
 ↓
AI Provider
 ↓
Azure AI / Microsoft Foundry
 ↓
Question Generation / Evaluation
 ↓
Feedback
 ↓
User
```

## Voice mode ( layered on top of the same agent)

```text
Microphone (browser, st.audio_input)
    ↓  audio (WAV)
Azure AI Speech — Speech-to-Text
    ↓  transcribed answer text
Interview Agent  →  AI Provider  →  evaluation + adaptive next question
    ↓  next question text
Azure AI Speech — Text-to-Speech
    ↓  audio (WAV)
Browser playback
```

Voice mode never bypasses the interview agent: a spoken answer is transcribed into the same text box a typed answer would use, and goes through the exact same `submit_answer()` evaluation and adaptive-difficulty logic. The core interview flow does not depend on speech at all — it works with typed answers with no Azure Speech configuration.

## Demo Mode vs. Azure Mode

`services/ai_provider.py` exposes one function, `get_ai_provider()`, which checks whether `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_DEPLOYMENT` are all set:

- **All three set → Azure Mode**: `AzureAIProvider` calls your real Azure OpenAI deployment.
- **Any missing → Demo Mode**: `MockAIProvider` generates questions from a small built-in question bank and evaluates answers with a simple, transparent length-based heuristic. Demo Mode is clearly labelled in the UI and is never presented as if it were Azure AI.

The same pattern applies to voice: `SpeechService.is_available` checks `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`, and the UI only shows voice controls when they are present. Without them, the app runs as a text-only interview with no errors or crashes.

If the AI provider is configured but a single request fails (network issue, invalid credentials, malformed JSON from the model), the interview agent catches the error and falls back to small local rule-based logic instead of crashing the interview — see `InterviewAgent._fallback_question` / `_fallback_evaluation` / `_fallback_summary` in `services/interview_agent.py`. A short notice is shown in the UI whenever this happens.

---

# 8. Technology Stack

- **Python 3.10+**
- **Streamlit** — web UI, including `st.audio_input` for microphone capture
- **Azure OpenAI** (via the `openai` Python SDK's `AzureOpenAI` client) — Microsoft Foundry-compatible generative AI
- **Azure AI Speech** (via `azure-cognitiveservices-speech`) — optional speech-to-text and text-to-speech
- **python-dotenv** — loads `.env` configuration
- **pytest** — unit tests

---

# 9. Project Structure

```text
ai-interview-coach/
│
├── app.py                     # Streamlit UI and page flow
├── requirements.txt
├── .env.example                # Placeholder environment variables (no real secrets)
├── .gitignore
├── README.md
├── PRESENTATION.md             # 5-minute demo script + evaluator Q&A
│
├── services/
│   ├── interview_agent.py      # The AI agent: state, adaptive logic, fallback handling
│   ├── ai_provider.py          # AzureAIProvider + MockAIProvider (Demo Mode)
│   ├── speech_provider.py      # Optional Azure AI Speech STT/TTS wrapper
│   └── prompts.py              # All AI prompt templates in one place
│
├── models/
│   └── schemas.py              # Data classes + structured-output validation
│
├── utils/
│   └── helpers.py              # JSON extraction, scoring, adaptive-difficulty rules
│
├── tests/
│   └── test_interview.py       # pytest test suite (Demo Mode + fallback logic)
│
└── screenshots/                # For presentation screenshots
```

---

# 10. Installation

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501` and starts in **Demo Mode** by default — no Azure account is required to try it.

---

# 11. Environment Variables

Copy `.env.example` to `.env` and fill in the values you want to use:

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

| Variable | Required for | Notes |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Azure Mode | e.g. `https://<your-resource>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Azure Mode | Your Azure OpenAI resource key |
| `AZURE_OPENAI_DEPLOYMENT` | Azure Mode | The name of your chat-completion model deployment |
| `AZURE_OPENAI_API_VERSION` | Azure Mode | Defaults to `2024-10-21` if omitted |
| `AZURE_SPEECH_KEY` | Voice mode (optional) | Your Azure AI Speech resource key |
| `AZURE_SPEECH_REGION` | Voice mode (optional) | e.g. `eastus` |

Leaving the Azure OpenAI variables blank runs the app in Demo Mode. Leaving the Speech variables blank simply hides the voice controls — the rest of the app is unaffected. `.env` is listed in `.gitignore` and is never committed.

---

# 12. Running the Application

```bash
streamlit run app.py
```

- **Demo Mode** (no `.env`, or missing Azure OpenAI variables): the app starts immediately, shows a yellow "🟡 Demo Mode" badge, and uses `MockAIProvider` for questions, evaluation and the summary. Ideal for development, grading, or presenting without an active Azure subscription.
- **Azure Mode** (all three Azure OpenAI variables set): the app shows a green "🟢 Azure Mode" badge and every question, evaluation and summary is generated by your Azure OpenAI deployment.
- **Voice mode** (optional, either mode): appears automatically once `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are set — a "🔊 Listen to question" button and a "🎙️ Record your spoken answer" widget appear on the question screen.

---

# 13. Testing

```bash
pytest
```

The test suite (`tests/test_interview.py`) covers:

- Score validation (structured-output parsing of malformed/out-of-range scores)
- Question/evaluation JSON validation
- JSON extraction from messy AI responses (markdown fences, extra text)
- Overall-score calculation
- Adaptive-difficulty rules (weaker → easier, stronger → harder, bounds respected, implausible AI suggestions ignored)
- `InterviewState` initialization and completion
- `MockAIProvider` (Demo Mode) question generation and evaluation
- Full end-to-end interview flow through `InterviewAgent`
- Graceful fallback behaviour when the AI provider fails on every call
- Demo Mode vs. Azure Mode detection from environment variables

All tests run offline against `MockAIProvider` and local logic — no Azure credentials or network access are required to run or grade the test suite.

---

# 14. Responsible AI

- The app states clearly, in the UI, that it is an **AI practice tool**, not a real interviewer, and that scores are **AI-generated approximations for self-practice only**.
- Every evaluation prompt instructs the model to judge only **accuracy, relevance, technical understanding, communication and completeness**, and explicitly forbids considering protected characteristics (gender, race, religion, accent, name, etc.).
- The system should **not be used for actual hiring decisions** — human judgment must remain part of any real recruitment process.
- **No answers are persisted**: interview state lives only in the Streamlit session and is discarded when the session ends.
- **Structured-output validation and fallback logic** guard against the model producing an invalid, out-of-range, or malformed score, so a bad AI response can never silently mislead the candidate.

---

# 15. Limitations

- `MockAIProvider` (Demo Mode) uses a small, fixed question bank and a simple answer-length heuristic for scoring — it is a realistic stand-in for demos, not a real AI evaluation.
- Azure Mode quality depends entirely on the configured model deployment and prompt design; it can still occasionally produce an imperfect score or piece of feedback.
- Voice mode requires a working microphone, browser permissions, and a live Azure AI Speech connection; transcription accuracy depends on audio quality and accent.
- The adaptive difficulty logic uses a single signal (the previous answer's score) rather than a full skill model across the whole interview.
- No user accounts, interview history, or persistence between sessions.

---

# 16. Future Scope

- Interview history and progress tracking across multiple sessions
- Resume-based question generation (tailoring questions to a candidate's actual background)
- More advanced adaptive questioning (tracking mastery per topic, not just a single difficulty level)
- Fully hands-free, continuous voice conversation mode (rather than record-then-submit)
- Deployment to Azure App Service / Azure Container Apps for shared access
- Multi-language support for both questions and voice