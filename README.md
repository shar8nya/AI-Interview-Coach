# ✦ InterviewAI — AI Interview Preparation Platform

A presentation-ready Streamlit project built on the original AI Interview Coach engine. The existing adaptive `InterviewAgent`, Azure OpenAI provider and Azure Speech integration are preserved, while the UI adds a polished dashboard, interview room, resume analysis, job matching, analytics, history, preparation planning and profile settings.

## Run locally

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open `http://localhost:8501`.

## Demo Mode

The app works without API credentials. It automatically uses the local MockAIProvider when Azure OpenAI variables are missing.

## Azure Mode

Copy `.env.example` to `.env` and fill in your own Azure credentials. Never commit `.env` to source control.

## Main product flow

Dashboard → New Interview → Adaptive Interview Room → AI Feedback → Final Report → Analytics / History → Personalized Preparation

## Added presentation features

- Premium dark AI SaaS-style UI
- Dashboard metrics and performance trend
- Adaptive interview room with progress and voice support
- AI feedback cards and stronger-answer examples
- Resume PDF analyzer
- Job description skill-match analyzer
- Performance analytics
- Persistent SQLite interview history
- Personalized 7-day preparation plan
- Profile/settings page
- JSON report download
- Graceful Demo Mode and voice fallback

## Responsible AI

Scores are practice feedback, not hiring decisions. The existing provider prompts explicitly instruct the evaluator to judge answer content rather than protected personal characteristics.
