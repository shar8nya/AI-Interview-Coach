"""InterviewAI — presentation-ready AI interview preparation platform.

The original InterviewAgent/Azure provider remain the core interview engine.
This UI layer adds a polished dashboard, local history, analytics, resume/job
matching, preparation planning and a settings/profile experience.
"""
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from database.db import init_db, get_profile, save_profile, save_interview, get_interviews, get_interview
from models.schemas import DEFAULT_QUESTIONS, DIFFICULTY_LEVELS, INTERVIEW_TYPES, JOB_ROLES, MAX_QUESTIONS, MIN_QUESTIONS
from services.ai_provider import get_ai_provider
from services.interview_agent import InterviewAgent
from services.speech_provider import SpeechError, get_speech_service
from services.resume_service import analyze_resume, extract_text
from utils.helpers import load_environment
from utils.ui import inject_css, hero, metric_card

load_environment()
init_db()
st.set_page_config(page_title="InterviewAI", page_icon="✦", layout="wide", initial_sidebar_state="expanded")
inject_css()

# ---------- session ----------
if "provider" not in st.session_state:
    st.session_state.provider = get_ai_provider()
if "speech" not in st.session_state:
    st.session_state.speech = get_speech_service()
if "agent" not in st.session_state:
    st.session_state.agent = InterviewAgent(st.session_state.provider)
if "stage" not in st.session_state:
    st.session_state.stage = "setup"
if "last_evaluation" not in st.session_state:
    st.session_state.last_evaluation = None
if "spoken_answer" not in st.session_state:
    st.session_state.spoken_answer = ""
if "profile" not in st.session_state:
    st.session_state.profile = get_profile()
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "resume_analysis" not in st.session_state:
    st.session_state.resume_analysis = None
if "saved_current" not in st.session_state:
    st.session_state.saved_current = False


def mode_text():
    p = st.session_state.provider
    return ("Azure AI" if p.display_name.startswith("Azure") else "Demo Mode")


def sidebar():
    p = st.session_state.profile
    with st.sidebar:
        st.markdown("# ✦ InterviewAI")
        st.caption("AI-powered interview preparation")
        st.markdown(f"**{p.get('name','Candidate')}**")
        st.caption(p.get("role", "Candidate"))
        st.divider()
        pages = [
            ("⌂", "Dashboard"), ("◎", "New Interview"), ("◈", "Resume AI"),
            ("⌁", "Job Match AI"), ("◒", "Analytics"), ("▣", "History"),
            ("✓", "Preparation"), ("⚙", "Settings"),
        ]
        current = st.session_state.get("page", "Dashboard")
        for icon, label in pages:
            if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True,
                         type="primary" if current == label else "secondary"):
                st.session_state.page = label
                st.rerun()
        st.divider()
        if mode_text() == "Azure AI":
            st.success("● Azure AI connected")
        else:
            st.warning("● Demo Mode")
        if st.session_state.speech.is_available:
            st.caption("🎙 Voice enabled")
        else:
            st.caption("🎙 Text mode")
        st.markdown('<div class="footer">Practice tool only · Not a hiring decision</div>', unsafe_allow_html=True)


def dashboard():
    rows = get_interviews()
    hero("Welcome back, " + st.session_state.profile.get("name", "Candidate") + " 👋", "Build confidence, practice under pressure, and turn weak areas into strengths.")
    c1,c2,c3,c4 = st.columns(4)
    scores = [r["overall_score"] for r in rows]
    qcount = sum(r["num_questions"] for r in rows)
    vals = [("Interviews", len(rows), "Completed sessions"), ("Average score", f"{sum(scores)/len(scores):.1f}/10" if scores else "—", "Across saved attempts"), ("Best score", f"{max(scores):.1f}/10" if scores else "—", "Personal best"), ("Questions", qcount, "Practice questions")]
    for col, (a,b,c) in zip((c1,c2,c3,c4), vals):
        with col: metric_card(a,b,c)
    st.write("")
    left,right = st.columns([1.6,1])
    with left:
        st.markdown("### Performance trend")
        if rows:
            import plotly.express as px
            data = [{"Attempt": i+1, "Score": r["overall_score"], "Role": r["job_role"]} for i,r in enumerate(reversed(rows))]
            fig = px.line(data, x="Attempt", y="Score", markers=True, range_y=[0,10], template="plotly_dark")
            fig.update_layout(height=300, margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="card"><h3>Your first interview is waiting.</h3><p class="small-muted">Complete one interview to unlock performance charts and history.</p></div>', unsafe_allow_html=True)
    with right:
        st.markdown("### Quick start")
        st.markdown('<div class="card"><h3>🎯 Practice for your next interview</h3><p class="small-muted">Choose a role, difficulty and interview type. The adaptive agent changes difficulty based on your answers.</p></div>', unsafe_allow_html=True)
        if st.button("Start New Interview →", type="primary", use_container_width=True):
            st.session_state.page = "New Interview"; st.rerun()
    st.markdown("### What InterviewAI does")
    a,b,c = st.columns(3)
    with a: st.markdown('<div class="card"><h3>01 · Interview</h3><p class="small-muted">Adaptive questions that respond to your performance.</p></div>', unsafe_allow_html=True)
    with b: st.markdown('<div class="card"><h3>02 · Evaluate</h3><p class="small-muted">Actionable feedback on accuracy, relevance and answer quality.</p></div>', unsafe_allow_html=True)
    with c: st.markdown('<div class="card"><h3>03 · Improve</h3><p class="small-muted">Analytics and a personalized preparation plan for your next attempt.</p></div>', unsafe_allow_html=True)


def new_interview():
    if st.session_state.stage in {"question","feedback","summary"} and st.session_state.agent.state and not st.session_state.agent.state.is_complete:
        st.info("You have an interview in progress. Finish it or use Start Over below.")
    hero("New interview", "Configure a realistic practice session tailored to your target role.")
    a,b = st.columns([1.25,.75])
    with a:
        role = st.selectbox("Job role", JOB_ROLES)
        itype = st.selectbox("Interview type", INTERVIEW_TYPES, format_func=lambda x: "Mixed · Technical + Behavioral + HR" if x == "Mixed" else x)
        diff = st.select_slider("Starting difficulty", options=DIFFICULTY_LEVELS, value="intermediate", format_func=str.title)
        n = st.slider("Number of questions", MIN_QUESTIONS, MAX_QUESTIONS, DEFAULT_QUESTIONS)
        company = st.text_input("Target company (optional)", placeholder="e.g. Microsoft")
        jd = st.text_area("Job description (optional)", height=120, placeholder="Paste the role description for a more targeted practice session…")
    with b:
        st.markdown('<div class="card"><h3>Session preview</h3><p class="small-muted">Your AI interviewer will adapt the next question based on your previous score.</p><hr><span class="pill">Adaptive</span> <span class="pill">Voice-ready</span> <span class="pill">AI feedback</span><br><br><b>Mode</b><br>\n' + mode_text() + '<br><br><b>Estimated time</b><br>~' + str(n*3) + ' minutes</div>', unsafe_allow_html=True)
        if st.button("🚀 Start Interview", type="primary", use_container_width=True):
            st.session_state.agent = InterviewAgent(st.session_state.provider)
            st.session_state.agent.start_interview(role, itype, diff, n)
            st.session_state.stage = "question"; st.session_state.saved_current = False; st.session_state.spoken_answer = ""
            st.session_state.page = "Interview Room"; st.rerun()


def interview_room():
    agent = st.session_state.agent
    if not agent.state:
        st.session_state.page = "New Interview"; st.rerun()
    if st.session_state.stage == "feedback":
        feedback()
        return
    if st.session_state.stage == "summary":
        summary()
        return
    state = agent.state; q = agent.get_current_question(); qnum = len(state.history)+1
    hero(f"Interview Room · Q{qnum}/{state.num_questions}", f"{state.job_role} · {state.interview_type} · {state.difficulty.title()} difficulty")
    st.progress(qnum/state.num_questions)
    st.markdown(f'<div class="question-card"><div class="eyebrow">AI INTERVIEWER · {q.topic}</div><div class="question-text">{q.text}</div></div>', unsafe_allow_html=True)
    st.write("")
    speech = st.session_state.speech

    # Voice controls are intentionally shown even when Azure credentials are
    # not configured. Recording works directly in the browser, while Azure
    # is used for cloud transcription when configured. Question playback has
    # a browser SpeechSynthesis fallback so Demo Mode remains voice-friendly.
    l, r = st.columns([1, 1])
    with l:
        if speech.is_available:
            if st.button("🔊 Listen to question", use_container_width=True):
                try:
                    st.audio(speech.text_to_speech(q.text), format="audio/wav")
                except SpeechError as e:
                    st.error(str(e))
        else:
            if st.button("🔊 Listen to question", use_container_width=True):
                safe_text = json.dumps(q.text)
                components.html(f"""
                <script>
                    const text = {safe_text};
                    if ('speechSynthesis' in window) {{
                        window.speechSynthesis.cancel();
                        const utterance = new SpeechSynthesisUtterance(text);
                        utterance.lang = 'en-US';
                        utterance.rate = 0.95;
                        window.speechSynthesis.speak(utterance);
                    }} else {{
                        document.body.innerHTML += '<p>Browser speech is not supported.</p>';
                    }}
                </script>
                <div style="font-family:Arial,sans-serif;padding:8px;border-radius:10px;background:#eef2ff;">🔊 Playing question through your browser...</div>
                """, height=48)
    with r:
        if speech.is_available:
            st.caption("🎙 Azure Voice enabled · record and transcribe your answer")
        else:
            st.caption("🎙 Recording is available · Azure transcription can be enabled in Settings/.env")

    recording = st.audio_input("🎙 Record your answer")
    if recording:
        st.audio(recording.getvalue(), format="audio/wav")
        if speech.is_available:
            if st.button("✨ Transcribe recording", type="secondary"):
                try:
                    with st.spinner("Transcribing your answer…"):
                        st.session_state.spoken_answer = speech.speech_to_text(recording.getvalue())
                    st.rerun()
                except SpeechError as e:
                    st.error(str(e))
        else:
            st.info("Your recording is captured. Add AZURE_SPEECH_KEY and AZURE_SPEECH_REGION to enable automatic transcription.")
    answer = st.text_area("Your answer", value=st.session_state.spoken_answer, height=190, placeholder="Structure your answer clearly. For behavioral questions, try Situation → Task → Action → Result.")
    x,y = st.columns([3,1])
    with x:
        if st.button("Submit Answer →", type="primary", use_container_width=True):
            if not answer.strip(): st.warning("Please enter an answer before submitting.")
            else:
                with st.spinner("Evaluating your answer…"):
                    st.session_state.last_evaluation = agent.submit_answer(answer)
                st.session_state.spoken_answer = ""
                st.session_state.stage = "summary" if agent.is_complete else "feedback"
                st.rerun()
    with y:
        if st.button("Exit Interview", use_container_width=True):
            st.session_state.stage = "setup"; st.session_state.page = "New Interview"; st.rerun()


def feedback():
    agent = st.session_state.agent; e = st.session_state.last_evaluation; entry = agent.state.history[-1]
    hero("Answer feedback", "A quick debrief before your next adaptive question.")
    c1,c2,c3,c4 = st.columns(4)
    vals = [("Score",f"{e.score}/10","Overall answer"),("Relevance","✓","On topic"),("Structure","✓" if e.score>=6 else "↗","Keep improving"),("Next level",entry.question.difficulty.title(),"Adaptive difficulty")]
    for col,v in zip((c1,c2,c3,c4),vals):
        with col: metric_card(*v)
    a,b = st.columns(2)
    with a:
        st.markdown("### What went well")
        for s in e.strengths: st.markdown(f"- {s}")
        st.markdown("### Improve next")
        for w in e.weaknesses: st.markdown(f"- {w}")
    with b:
        st.markdown("### Missing concepts")
        for m in e.missing_concepts or ["No major gaps detected."]: st.markdown(f"- {m}")
        st.markdown("### Actionable tip")
        st.info(e.improvement or "Add a concrete example and explain the reasoning behind your answer.")
        if e.better_answer:
            with st.expander("View a stronger example"):
                st.write(e.better_answer)
    if st.button("Next Question →", type="primary", use_container_width=True):
        st.session_state.stage = "question"; st.session_state.page = "Interview Room"; st.rerun()


def summary():
    agent=st.session_state.agent; state=agent.state
    if not state: return
    if not st.session_state.saved_current:
        save_interview(state); st.session_state.saved_current=True
    summary_obj = agent.get_summary()
    hero("Interview complete 🎉", "Your practice report is ready. Use it as a roadmap for your next attempt.")
    c1,c2,c3 = st.columns(3)
    with c1: metric_card("Overall score", f"{summary_obj.overall_score:.1f}/10", "Calculated from your answers")
    with c2: metric_card("Questions", len(state.history), "Completed")
    with c3: metric_card("Mode", mode_text(), "AI provider")
    a,b = st.columns(2)
    with a:
        st.markdown("### Strengths")
        for s in summary_obj.strengths: st.markdown(f"- {s}")
    with b:
        st.markdown("### Areas to improve")
        for x in summary_obj.areas_to_improve: st.markdown(f"- {x}")
    st.markdown("### Question breakdown")
    for i,e in enumerate(state.history,1):
        with st.expander(f"Q{i} · {e.evaluation.score}/10 · {e.question.topic}"):
            st.write(e.question.text); st.caption("Your answer"); st.write(e.answer); st.caption(e.evaluation.improvement)
    report = {"created_at":datetime.now().isoformat(timespec="seconds"),"role":state.job_role,"type":state.interview_type,"score":summary_obj.overall_score,"questions":[{"question":e.question.text,"score":e.evaluation.score,"answer":e.answer} for e in state.history]}
    st.download_button("⬇ Download JSON report", json.dumps(report, indent=2), file_name="interview_report.json", mime="application/json")
    if st.button("Start Another Interview", type="primary", use_container_width=True):
        st.session_state.stage="setup"; st.session_state.saved_current=False; st.session_state.page="New Interview"; st.rerun()


def resume_ai():
    hero("Resume AI", "Turn your resume into a personalized interview preparation plan.")
    uploaded=st.file_uploader("Upload your resume (PDF)", type=["pdf"])
    if uploaded:
        try:
            text=extract_text(uploaded); result=analyze_resume(text); st.session_state.resume_text=text; st.session_state.resume_analysis=result
        except Exception as e: st.error(str(e))
    r=st.session_state.resume_analysis
    if r:
        c1,c2,c3=st.columns(3)
        with c1: metric_card("Detected skills",len(r["skills"]),"Technology keywords")
        with c2: metric_card("Resume words",r["word_count"],"Approximate")
        with c3: metric_card("Sections found",sum(r["sections"].values()),"Core sections")
        st.markdown("### Skills detected")
        st.write(" · ".join(r["skills"]) if r["skills"] else "No common technology keywords detected yet.")
        st.markdown("### Resume health")
        for section, found in r["sections"].items(): st.markdown(("✅ " if found else "⚠️ ") + section)
        st.markdown("### Resume-based practice")
        role=st.session_state.profile.get("role","AI/ML Engineer")
        if r["skills"]:
            for skill in r["skills"][:6]: st.markdown(f"- Explain a real project where you used **{skill}**.")
        else: st.info(f"Add your technical skills to your resume, then practice role-specific questions for {role}.")


def job_match():
    hero("Job Match AI", "Compare a job description with your resume and find what to practise next.")
    jd=st.text_area("Paste job description", height=250)
    resume=st.session_state.resume_text
    if not resume: st.caption("Tip: upload a resume in Resume AI first for a more useful comparison.")
    if st.button("Analyze Match", type="primary"):
        if not jd.strip(): st.warning("Paste a job description first."); return
        job_text=jd.lower(); skills=[s for s in ["Python","Java","C++","JavaScript","SQL","React","Flask","Django","Streamlit","Pandas","NumPy","scikit-learn","TensorFlow","PyTorch","Machine Learning","Deep Learning","Azure","Docker","Git","AWS"] if s.lower() in job_text]
        resume_low=resume.lower(); matched=[s for s in skills if s.lower() in resume_low]; missing=[s for s in skills if s not in matched]
        pct=round(len(matched)/len(skills)*100) if skills else 0
        a,b,c=st.columns(3)
        with a: metric_card("Skill match",f"{pct}%","Keyword-based estimate")
        with b: metric_card("Matched",len(matched),"Skills in both")
        with c: metric_card("Missing",len(missing),"Topics to practise")
        st.markdown("### Matched skills"); st.write(" · ".join(matched) if matched else "None detected")
        st.markdown("### Priority topics"); st.write(" · ".join(missing) if missing else "No obvious gaps from the detected keywords.")
        if missing: st.info("Next step: build interview questions around the missing topics and practise them in New Interview.")


def analytics():
    rows=get_interviews(); hero("Performance analytics", "See how your practice is changing over time.")
    if not rows: st.info("Complete an interview to unlock analytics."); return
    import plotly.express as px
    data=list(reversed(rows))
    c1,c2=st.columns(2)
    with c1:
        fig=px.line([{"Attempt":i+1,"Score":r["overall_score"]} for i,r in enumerate(data)],x="Attempt",y="Score",markers=True,range_y=[0,10],template="plotly_dark"); fig.update_layout(height=340,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig,use_container_width=True)
    with c2:
        roles={}
        for r in rows: roles.setdefault(r["job_role"],[]).append(r["overall_score"])
        bar=[{"Role":k,"Average":sum(v)/len(v)} for k,v in roles.items()]
        fig=px.bar(bar,x="Role",y="Average",range_y=[0,10],template="plotly_dark"); fig.update_layout(height=340,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig,use_container_width=True)
    latest=rows[0]["overall_score"]; previous=rows[1]["overall_score"] if len(rows)>1 else latest
    delta=latest-previous
    a,b,c=st.columns(3)
    with a: metric_card("Latest",f"{latest:.1f}/10","Most recent")
    with b: metric_card("Change",f"{delta:+.1f}","vs previous attempt")
    with c: metric_card("Best",f"{max(r['overall_score'] for r in rows):.1f}/10","Personal best")


def history():
    rows=get_interviews(); hero("Interview history", "Review previous sessions and compare your attempts.")
    if not rows: st.info("No saved interviews yet."); return
    for r in rows:
        with st.expander(f"{r['created_at']} · {r['job_role']} · {r['overall_score']:.1f}/10"):
            st.write(f"**Type:** {r['interview_type']} · **Difficulty:** {r['difficulty']} · **Questions:** {r['num_questions']}")
            for i,item in enumerate(json.loads(r["data_json"]),1):
                st.markdown(f"**Q{i} · {item['score']}/10 · {item['topic']}**")
                st.caption(item["question"]); st.write(item["answer"])
                if item.get("improvement"): st.info(item["improvement"])


def preparation():
    rows=get_interviews(); hero("Preparation plan", "A simple weekly roadmap built around your latest performance.")
    weak=[]
    if rows:
        latest=json.loads(rows[0]["data_json"])
        for x in sorted(latest,key=lambda z:z["score"])[:3]: weak += x.get("missing_concepts",[])
    topics=[]
    for x in weak:
        if x not in topics: topics.append(x)
    topics=topics[:4] or ["Core fundamentals","Problem solving","Communication","Behavioral storytelling"]
    days=[("Day 1","Review fundamentals",topics[0]),("Day 2","Targeted practice",topics[1%len(topics)]),("Day 3","Timed questions",topics[2%len(topics)]),("Day 4","Project deep dive","Explain one project end-to-end"),("Day 5","Behavioral practice","Use STAR structure"),("Day 6","Full mock interview","Mixed difficulty"),("Day 7","Final assessment","Repeat and compare")]
    for day,title,detail in days:
        st.markdown(f'<div class="card" style="margin-bottom:.7rem"><span class="pill">{day}</span><h3 style="margin:.5rem 0">{title}</h3><p class="small-muted">{detail}</p></div>',unsafe_allow_html=True)


def settings():
    hero("Settings", "Personalize your InterviewAI experience.")
    p=st.session_state.profile
    name=st.text_input("Name",p.get("name","Candidate")); role=st.selectbox("Preferred role",JOB_ROLES,index=JOB_ROLES.index(p.get("role")) if p.get("role") in JOB_ROLES else 0); exp=st.selectbox("Experience",["Student","0–1 years","1–3 years","3+ years"],index=0 if p.get("experience") not in ["Student","0–1 years","1–3 years","3+ years"] else ["Student","0–1 years","1–3 years","3+ years"].index(p.get("experience")))
    if st.button("Save profile",type="primary"):
        save_profile(name,role,exp); st.session_state.profile=get_profile(); st.success("Profile saved.")
    st.markdown("### Integrations")
    st.write("AI provider:", mode_text())
    st.write("Azure Speech:", "Connected" if st.session_state.speech.is_available else "Not configured — text mode remains available")
    st.caption("API keys are read from .env and are never displayed here.")


def route():
    sidebar(); page=st.session_state.get("page","Dashboard")
    if page == "Dashboard": dashboard()
    elif page == "New Interview": new_interview()
    elif page == "Interview Room": interview_room()
    elif page == "Resume AI": resume_ai()
    elif page == "Job Match AI": job_match()
    elif page == "Analytics": analytics()
    elif page == "History": history()
    elif page == "Preparation": preparation()
    elif page == "Settings": settings()

route()
