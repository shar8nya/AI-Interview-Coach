import streamlit as st


def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root { --bg:#0b1020; --panel:#11182b; --panel2:#151e35; --text:#f4f7ff; --muted:#9aa6bd; --accent:#7c5cff; --accent2:#20c9a6; --border:rgba(255,255,255,.09); }
    .stApp { background: radial-gradient(circle at 10% 0%, rgba(124,92,255,.16), transparent 30%), radial-gradient(circle at 90% 10%, rgba(32,201,166,.10), transparent 25%), var(--bg); color:var(--text); font-family:'Inter',sans-serif; }
    [data-testid="stSidebar"] { background:rgba(9,14,28,.96); border-right:1px solid var(--border); }
    [data-testid="stSidebar"] * { font-family:'Inter',sans-serif; }
    .block-container { max-width:1250px; padding-top:2rem; padding-bottom:4rem; }
    h1,h2,h3 { letter-spacing:-.03em; }
    .hero { padding:2rem; border:1px solid var(--border); border-radius:24px; background:linear-gradient(135deg,rgba(124,92,255,.18),rgba(17,24,43,.88)); box-shadow:0 20px 60px rgba(0,0,0,.22); margin-bottom:1.2rem; }
    .hero h1 { font-size:2.7rem; margin:0; }
    .hero p { color:var(--muted); font-size:1.05rem; margin:.45rem 0 0; }
    .eyebrow { color:#b9adff; font-weight:700; text-transform:uppercase; font-size:.76rem; letter-spacing:.13em; }
    .card { background:rgba(17,24,43,.78); border:1px solid var(--border); border-radius:18px; padding:1.1rem; height:100%; box-shadow:0 10px 30px rgba(0,0,0,.12); }
    .metric-card { background:linear-gradient(145deg,rgba(21,30,53,.95),rgba(17,24,43,.8)); border:1px solid var(--border); border-radius:18px; padding:1rem 1.1rem; }
    .metric-label { color:var(--muted); font-size:.8rem; }
    .metric-value { font-size:1.8rem; font-weight:800; margin-top:.15rem; }
    .metric-sub { color:#7f8ca6; font-size:.75rem; margin-top:.2rem; }
    .pill { display:inline-block; padding:.3rem .65rem; border-radius:999px; background:rgba(124,92,255,.15); color:#c9c0ff; border:1px solid rgba(124,92,255,.25); font-size:.78rem; font-weight:600; }
    .question-card { padding:1.6rem; border-radius:22px; background:linear-gradient(145deg,rgba(21,30,53,.96),rgba(13,18,34,.94)); border:1px solid rgba(124,92,255,.24); }
    .question-text { font-size:1.45rem; line-height:1.45; font-weight:700; }
    .score-ring { font-size:3rem; font-weight:800; text-align:center; padding:1rem; }
    .small-muted { color:var(--muted); font-size:.86rem; }
    .success-box { border:1px solid rgba(32,201,166,.25); background:rgba(32,201,166,.08); padding:1rem; border-radius:14px; }
    .warning-box { border:1px solid rgba(255,190,92,.25); background:rgba(255,190,92,.08); padding:1rem; border-radius:14px; }
    .stButton > button { border-radius:12px; min-height:2.6rem; font-weight:700; border:1px solid var(--border); }
    .stButton > button[kind="primary"] { background:linear-gradient(135deg,#7c5cff,#5e45db); border:0; }
    .stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"] > div,.stNumberInput input { border-radius:12px; }
    div[data-testid="stMetric"] { background:rgba(17,24,43,.72); border:1px solid var(--border); padding:1rem; border-radius:16px; }
    .footer { color:#6f7b93; font-size:.75rem; text-align:center; margin-top:2rem; }
    </style>
    """, unsafe_allow_html=True)


def hero(title, subtitle, eyebrow="INTERVIEWAI"):
    st.markdown(f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def metric_card(label, value, sub=""):
    st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-sub">{sub}</div></div>', unsafe_allow_html=True)


def card(title, body):
    st.markdown(f'<div class="card"><h3 style="margin-top:0">{title}</h3>{body}</div>', unsafe_allow_html=True)
