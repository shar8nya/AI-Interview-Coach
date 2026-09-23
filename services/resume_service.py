import re

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

TECH = ["Python", "Java", "C++", "JavaScript", "SQL", "HTML", "CSS", "React", "Flask", "Django", "Streamlit", "Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch", "Machine Learning", "Deep Learning", "Azure", "Git", "Docker", "AWS", "Power BI"]


def extract_text(uploaded_file):
    if PdfReader is None:
        raise RuntimeError("PDF support is not installed. Run: python -m pip install pypdf")
    reader = PdfReader(uploaded_file)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def analyze_resume(text):
    low = text.lower()
    skills = [s for s in TECH if s.lower() in low]
    sections = {
        "Education": bool(re.search(r"education|university|college|degree|bachelor", low)),
        "Projects": bool(re.search(r"projects?|project experience", low)),
        "Experience": bool(re.search(r"experience|internship|employment", low)),
        "Certifications": bool(re.search(r"certif|course|credential", low)),
    }
    return {"skills": skills, "sections": sections, "word_count": len(text.split())}
