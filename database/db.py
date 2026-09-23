import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent / "interviewai.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            job_role TEXT NOT NULL,
            interview_type TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            num_questions INTEGER NOT NULL,
            overall_score REAL NOT NULL,
            duration_seconds INTEGER DEFAULT 0,
            data_json TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT DEFAULT 'Candidate',
            role TEXT DEFAULT 'AI/ML Engineer',
            experience TEXT DEFAULT 'Student'
        )""")
        conn.execute("INSERT OR IGNORE INTO profile(id) VALUES (1)")


def save_profile(name, role, experience):
    with connect() as conn:
        conn.execute("UPDATE profile SET name=?, role=?, experience=? WHERE id=1", (name, role, experience))


def get_profile():
    with connect() as conn:
        row = conn.execute("SELECT * FROM profile WHERE id=1").fetchone()
        return dict(row) if row else {"name": "Candidate", "role": "AI/ML Engineer", "experience": "Student"}


def save_interview(state):
    payload = []
    for entry in state.history:
        payload.append({
            "question": entry.question.text,
            "topic": entry.question.topic,
            "difficulty": entry.question.difficulty,
            "answer": entry.answer,
            "score": entry.evaluation.score,
            "strengths": entry.evaluation.strengths,
            "weaknesses": entry.evaluation.weaknesses,
            "missing_concepts": entry.evaluation.missing_concepts,
            "improvement": entry.evaluation.improvement,
            "better_answer": entry.evaluation.better_answer,
        })
    overall = sum(x["score"] for x in payload) / len(payload) if payload else 0
    with connect() as conn:
        conn.execute(
            "INSERT INTO interviews(created_at,job_role,interview_type,difficulty,num_questions,overall_score,data_json) VALUES(?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), state.job_role, state.interview_type,
             state.difficulty, state.num_questions, overall, json.dumps(payload))
        )


def get_interviews(limit=50):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM interviews ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_interview(interview_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM interviews WHERE id=?", (interview_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["data"] = json.loads(data.pop("data_json"))
        return data
