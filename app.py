import streamlit as st
import fitz
import google.generativeai as genai
import time
import json
import re

# --- 1. SETUP & REFINED CSS ---
st.set_page_config(page_title="AI Professional Recruiter", layout="centered")

st.markdown("""
    <style>
    /* Hide Deploy button but keep menu/running icon */
    .stDeployButton {display:none;}
    
    /* Standard Blue Buttons */
    div.stButton > button:first-child {
        background-color: #0066cc !important;
        color: white !important;
        border-radius: 6px;
        border: none;
    }

    /* Professional Skill Tags (Category View) */
    .skill-tag {
        color: #0066cc;
        border: 1px solid #0066cc;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        margin-right: 5px;
        display: inline-block;
        margin-bottom: 8px;
        font-weight: 500;
    }

    /* Normal Ideal Answer Box - No white-out */
    .ideal-answer-box {
        padding: 15px;
        border: 1px solid #444;
        border-radius: 8px;
        margin-top: 10px;
        background-color: rgba(255, 255, 255, 0.03);
        color: inherit;
        line-height: 1.5;
    }
    
    .theme-label {
        color: #0066cc;
        font-weight: bold;
        font-size: 1.1rem;
        margin-top: 15px;
        margin-bottom: 5px;
        display: block;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MODEL CONFIGURATION ---
genai.configure(api_key="AIzaSyAXjbGAMe71CUPlmRN2ROKj9-xFGL1xYxs")

SYSTEM_INSTRUCTION = "You are a Senior Lead Interviewer. You extract skill themes and generate difficult technical questions with precise, numbered answers."
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash-lite', #, # Using stable high-performance model
    system_instruction=SYSTEM_INSTRUCTION
)

if 'screen' not in st.session_state:
    st.session_state.update({
        'screen': "upload",
        'questions': [],
        'current_q': 0,
        'user_answers': {},
        'themed_skills': {},
        'flat_skills': [],
        'review_data': {}, # Changed to dict for exact mapping
        'final_report': ""
    })

def go_home():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def safe_ai_call(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"AI Service Error: {e}")
        return None

# --- SCREEN 1: UPLOAD & CATEGORY VIEW ---
if st.session_state.screen == "upload":
    st.title("AI RESUME ANALYZER 🤖")
    st.markdown("### Profile Skill Extraction")
    
    uploaded_file = st.file_uploader("Upload PDF Resume", type="pdf")

    if uploaded_file:
        if not st.session_state.themed_skills:
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                resume_text = "".join([page.get_text() for page in doc])
            
            with st.spinner("Categorizing Skills..."):
                extraction_prompt = f"Analyze resume and extract technical skills grouped by theme. Return ONLY JSON: {{'Theme': ['Skill1', 'Skill2']}}. Resume: {resume_text}"
                res = safe_ai_call(extraction_prompt)
                try:
                    clean_json = res.strip().replace("```json", "").replace("```", "")
                    skills_dict = json.loads(clean_json)
                    st.session_state.themed_skills = skills_dict
                    # Take only 5-6 total skills to keep interview focused
                    flat = [s for s_list in skills_dict.values() for s in s_list]
                    st.session_state.flat_skills = flat[:6] 
                except:
                    st.session_state.themed_skills = {"Detected Skills": ["Re-upload for better categorization"]}

        if st.session_state.themed_skills:
            # Normal category-wise view
            for theme, skills in st.session_state.themed_skills.items():
                st.markdown(f"<span class='theme-label'>{theme}</span>", unsafe_allow_html=True)
                tags_html = "".join([f"<span class='skill-tag'>{s}</span>" for s in skills])
                st.markdown(f"<div>{tags_html}</div>", unsafe_allow_html=True)

            st.success("Resume Loaded! Skills categorized above.")
            
            _, col_center, _ = st.columns([1, 2, 1])
            if col_center.button("Begin Deep-Dive Interview ➡️", use_container_width=True):
                with st.spinner("Generating 10 questions per skill..."):
                    q_prompt = f"For each skill in {st.session_state.flat_skills}, generate 10 questions (mix of code, logic, and theory). Separate ALL questions with '|' only. No headers."
                    questions_res = safe_ai_call(q_prompt)
                    if questions_res:
                        st.session_state.questions = [q.strip() for q in questions_res.split('|') if len(q.strip()) > 15]
                        st.session_state.screen = "interview"
                        st.rerun()

# --- SCREEN 2: INTERVIEW ---
elif st.session_state.screen == "interview":
    st.button("↩️ Exit", on_click=go_home)
    st.title("Technical Assessment")
    
    qs = st.session_state.questions
    idx = st.session_state.current_q

    st.progress((idx + 1) / len(qs))
    st.write(f"**Question {idx + 1} of {len(qs)}**")
    st.info(qs[idx])

    ans_key = f"ans_{idx}"
    st.session_state.user_answers[idx] = st.text_area("Your Response:", 
                                                   value=st.session_state.user_answers.get(idx, ""), 
                                                   key=ans_key, height=180)

    nav_left, nav_mid, nav_right = st.columns([1, 1, 1])
    with nav_left:
        if idx > 0:
            st.button("⬅️ Previous", on_click=lambda: st.session_state.update({"current_q": idx-1}))
    with nav_right:
        if idx < len(qs) - 1:
            st.button("Next Question ➡️", on_click=lambda: st.session_state.update({"current_q": idx+1}))
        else:
            if st.button("Complete Interview 📝"):
                st.session_state.screen = "review"
                st.rerun()

# --- SCREEN 3: REVIEW (RECTIFIED FOR CORRECT ANSWERS) ---
elif st.session_state.screen == "review":
    st.button("↩️ Restart", on_click=go_home)
    st.title("Review & Ideal Answers")
    
    if not st.session_state.review_data:
        with st.spinner("Fetching Correct Answers..."):
            # Requesting AI to provide a clear, numbered list for parsing
            qa_summary = "\n".join([f"{i+1}. Q: {q}" for i, q in enumerate(st.session_state.questions)])
            raw_review = safe_ai_call(f"Provide a short technical ideal answer for each question. Use format 'Answer X: [content]'. Questions:\n{qa_summary}")
            
            if raw_review:
                # Parsing logic to extract answers correctly regardless of extra AI talk
                for i in range(len(st.session_state.questions)):
                    pattern = rf"Answer {i+1}:(.*?)(?=Answer {i+2}:|$)"
                    match = re.search(pattern, raw_review, re.DOTALL | re.IGNORECASE)
                    if match:
                        st.session_state.review_data[i] = match.group(1).strip()
                    else:
                        st.session_state.review_data[i] = "Solution available in final report."

    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Question {i+1}: {q[:80]}..."):
            st.write(f"**Your Answer:** {st.session_state.user_answers.get(i, 'N/A')}")
            # Displaying the parsed correct answer
            sol = st.session_state.review_data.get(i, "Generating correct solution...")
            st.markdown(f"<div class='ideal-answer-box'><b>Correct Technical Solution:</b><br>{sol}</div>", unsafe_allow_html=True)

    if st.button("Generate Final Report 📊", use_container_width=True):
        st.session_state.screen = "feedback"
        st.rerun()

# --- SCREEN 4: FEEDBACK & DOWNLOAD ---
elif st.session_state.screen == "feedback":
    st.button("↩️ Home", on_click=go_home)
    st.title("Final Performance Report")

    if not st.session_state.final_report:
        with st.spinner("Analyzing performance..."):
            f_prompt = f"Analyze: {str(st.session_state.user_answers)}. Format: 1. Total Marks: [X/100] 2. Skill-wise Rating (1-10) 3. Suggestions 4. Final Verdict: (Hire/No Hire)"
            st.session_state.final_report = safe_ai_call(f_prompt)
    
    st.markdown(st.session_state.final_report)

    st.download_button(
        label="📥 Download Technical Report",
        data=st.session_state.final_report,
        file_name="Interview_Verdict.txt",
        mime="text/plain",
        use_container_width=True
    )
    
    st.button("Start New Assessment 🔄", on_click=go_home)
