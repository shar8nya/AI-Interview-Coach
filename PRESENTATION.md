# AI Interview Coach — Presentation Guide

A speaking script and evaluator Q&A prep for the 5-minute demo.

---

## 5-Minute Presentation Structure

### 0:00–0:30 — Introduction

> "Hi, we're [team name], and we built AI Interview Coach — an adaptive AI interviewer that gives job seekers realistic, personalized interview practice. It's built on Azure AI as our AI-103 course project."

Keep it short: name, one-line description, done.

### 0:30–1:00 — Problem

> "Most interview practice is either practicing alone with a static list of questions, or scheduling mock interviews with a friend — which is hard to arrange and doesn't scale. Static question banks never adapt to how well you're actually doing, and you rarely get specific, structured feedback on *why* an answer was weak. That leaves candidates under-prepared for the part of an interview that matters most: how they actually respond under questioning."

### 1:00–2:00 — AI Solution + Architecture

> "AI Interview Coach simulates a real interview. You pick a job role, an interview type — Technical, Behavioral or HR — and a starting difficulty. An AI interview agent asks a question, you answer by typing or speaking, and the AI evaluates your answer: a score out of 10, what you did well, what was missing, and an example of a stronger answer.
>
> The key part is *adaptive questioning* — if you answer weakly, the next question gets easier or revisits the missing concept. If you answer strongly, it gets harder. That's the agentic behavior: the interview agent tracks your history and difficulty, and decides what to ask next.
>
> Architecturally, the Streamlit UI talks to our interview agent, which talks to an AI provider — either Azure OpenAI for real AI-generated questions and evaluation, or a local mock provider for offline demos. We also layered in optional voice mode using Azure AI Speech: you can listen to a question read aloud, record your answer, and it's transcribed automatically before going through the exact same evaluation pipeline."

*(Show the architecture diagram from the README here if presenting slides.)*

### 2:00–4:00 — Live Demonstration

Suggested demo flow:
1. Show the setup screen — pick "Software Engineer," "Technical," start at "Beginner," 3 questions.
2. Answer the first question **badly** (very short, one sentence) → point out the low score and the feedback.
3. Show that the next question is now **easier / revisits the missing concept** — read the adaptation note out loud.
4. Answer the next question **well** (detailed, with an example) → point out the higher score and that the difficulty goes back up.
5. (If Azure AI Speech is configured) Demonstrate voice mode: click "Listen to question," then record a spoken answer and show it get transcribed into the text box.
6. Finish the interview and show the final summary: overall score, strengths, areas to improve, per-question breakdown.
7. Briefly show the Demo Mode / Azure Mode badge and mention both modes exist for reliability.

### 4:00–5:00 — Impact, Limitations and Future Scope

> "This gives candidates unlimited, on-demand interview practice with structured, specific feedback instead of a static question list. It's built responsibly: it evaluates only the content of your answer, never personal characteristics, and it's explicit that it's a practice tool, not a hiring decision.
>
> Current limitations: Demo Mode uses simplified scoring, difficulty adapts on a single score signal rather than a full skill model, and there's no persistence between sessions yet. Future scope includes resume-based questioning, interview history and progress tracking, and a fully hands-free conversational voice mode."

---

## Likely Evaluator Questions and Concise Answers

**Q: Why did you use an AI agent?**
A: An agent lets the system remember interview state — previous questions, scores, topics covered, current difficulty — and decide the next question based on that history, rather than just generating one question in isolation. That's what makes it feel like an interviewer instead of a quiz generator.

**Q: Where is AI being used?**
A: In three places, all through Azure OpenAI: generating each interview question, evaluating each answer against structured criteria, and generating the final performance summary. All three use prompt templates that require the model to return structured JSON.

**Q: How does adaptive questioning work?**
A: After each answer is scored, our own code (not the AI) applies a simple, auditable rule: score 0–4 moves difficulty down one level, 5–7 keeps it the same, 8–10 moves it up one level, bounded between beginner and advanced. The AI can *suggest* a next difficulty in its evaluation, but our code only accepts that suggestion if it agrees with the rule — so a weak answer can never accidentally jump to a harder question.

**Q: What Azure services are being used?**
A: Azure OpenAI (Microsoft Foundry-compatible) for the generative AI — question generation, evaluation, summarization — and, optionally, Azure AI Speech for speech-to-text and text-to-speech in voice mode.

**Q: How is responsible AI handled?**
A: Every prompt explicitly restricts evaluation to answer content — accuracy, relevance, technical understanding, communication, completeness — and explicitly forbids considering protected characteristics. The UI states clearly that this is a practice tool, not a hiring decision, and answers aren't persisted anywhere.

**Q: How do you prevent biased interview evaluation?**
A: The evaluation prompt hard-codes the allowed criteria and explicitly lists what must never factor into scoring (gender, race, religion, accent, name, etc.). The AI only ever sees the question and the answer text — never any information about the candidate as a person.

**Q: What happens if the AI produces invalid output?**
A: Every AI response is parsed as JSON and validated against our schema (`models/schemas.py`) — for example, a score must be a number between 0 and 10. If parsing or validation fails, or the request itself fails (network, auth), the interview agent catches that and falls back to a small local rule-based question/evaluation instead of crashing, and shows a short notice in the UI.

**Q: Why is this better than a static question bank?**
A: A static bank asks the same questions regardless of performance and gives no feedback beyond right/wrong. This system adapts question difficulty to the candidate in real time and gives structured, specific feedback — strengths, gaps, and a model answer — after every single question.

**Q: What are the limitations?**
A: Demo Mode's scoring is a simplified heuristic, not real language understanding. Difficulty adapts on one score signal per question rather than a full per-topic skill model. There's no persistence between sessions, and voice mode's accuracy depends on Azure AI Speech and audio quality.

**Q: How would you scale it?**
A: Deploy the Streamlit app to Azure App Service or Azure Container Apps, move interview state to a lightweight store (e.g. Azure Cosmos DB or Table Storage) so history and progress persist across sessions, and move prompt evaluation to a proper multi-signal skill model per topic rather than a single running difficulty.
