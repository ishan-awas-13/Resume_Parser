import streamlit as st
from extractor import get_clean_resume_text 
from parser_engine import parse_resume_text
import os
import time
import threading # <-- Essential addition for creating parallel execution lanes

st.set_page_config(page_title="AI Resume parser", layout="wide")
st.title("AI Resume Parser (Phase 1)")
st.write("Submit your resume PDF/DOCX file here to automatically extract candidate insights via **Locally Hosted SLMs**.")

MODEL_DICT = {
    "mistral:7b (7B parameters)": "mistral:7b",
    "phi4-mini:latest (3.8B parameters)": "phi4-mini:latest",
    "llama3.2:3b (3.2B parameters)": "llama3.2:3b",
    "qwen2.5:3b (3.1B parameters)": "qwen2.5:3b"
}
model_selected = st.selectbox(
    label="Select Model:",
    options=MODEL_DICT.keys(),
    index=0,
    key="model_select"
)

current_model = MODEL_DICT[model_selected]
st.write("Selected Model : ", current_model)

# Inject CSS — moderate font sizes for 2-column layout
st.markdown("""
    <style>
    div[data-testid="stMarkdownContainer"] p { font-size: 0.95rem; }
    div[data-testid="stAlert"] p, div[data-testid="stAlert"] div { font-size: 0.93rem !important; }
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] p { font-size: 0.93rem; }
    div[data-testid = "stColumn"]{
        border: 2px solid #444 !important;
        border-radius: 10px !important;
        padding: 15px !important;
        box-sizing: border-box !important;  
    }
    .field-card { margin-bottom: 12px; line-height: 1.5; }
    .field-label { font-size: 0.75rem; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
    .field-value { font-size: 0.95rem; color: inherit; word-break: break-word; }
    </style>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload your Resume: ", type=["pdf", "docx"])

if uploaded_file is not None:
    st.success("Resume Received successfully! Starting backend pipeline processing...")

    # Establish empty placeholders where our stopwatch and status boxes can animate live
    timer_placeholder = st.empty()
    status_placeholder = st.empty()

    status_placeholder.info(f"Preparing document text extraction...")

    try:
        # Step 1: Extract text from file buffer before handoff to keep thread logic light
        extracted_text = get_clean_resume_text(uploaded_file)

        # 1. Set up containers to pass data and errors safely across our parallel threads
        pipeline_container = {}  
        pipeline_error = []      
        processing_complete = threading.Event()  # The safe boolean toggle switch

        # 2. Define the precise extraction task that will run in our background lane
        def background_inference_worker():
            try:
                # This blocks inside the background thread, leaving the main thread free to animate
                result = parse_resume_text(current_model, extracted_text)
                pipeline_container["data"] = result
            except Exception as e:
                pipeline_error.append(e)
            finally:
                # Flip the switch to True, telling our main thread stopwatch to freeze immediately
                processing_complete.set()

        # 3. Initialize and trigger the parallel background track
        inference_thread = threading.Thread(target=background_inference_worker)
        start_marker = time.time()
        inference_thread.start()

        # 4. THE LIVE STOPWATCH: Updates on screen 10 times a second while the background thread processes
        status_placeholder.info(f"Local Model {current_model} is processing your resume... Please Wait...")
        
        while not processing_complete.is_set():
            current_elapsed = time.time() - start_marker
            timer_placeholder.metric(
                label=f"⏱️ Local Server Processing Stopwatch ({current_model})", 
                value=f"{current_elapsed:.1f} s"
            )
            time.sleep(0.1)  # Brief rest step to keep the CPU stable

        # 5. Capture precise final latency duration and wipe layout loaders
        total_latency = time.time() - start_marker
        status_placeholder.empty()

        # If the background execution crashed, catch the error and dump it safely to the UI
        if pipeline_error:
            raise pipeline_error[0]

        # Retrieve the validated data model out of our pipeline storage bucket
        parsed_profile = pipeline_container["data"]
        profile_data = parsed_profile.candidate_profile

        st.balloons()
        st.subheader("📊 Extracted Candidate Insights Report")
        
        # Overwrite your moving timer placeholder with your frozen finalized latency metric
        timer_placeholder.metric(label="⏱️ Final Execution Benchmark Latency", value=f"{total_latency:.2f} seconds")
        st.divider()

        # ── LEFT & RIGHT COLUMNS REPORT RENDERING (Your exact code matches below this line) ────
        left, right = st.columns([1, 1])

        with left:
            st.markdown("### 👤 Personal Information")
            p_info = profile_data.personal_information

            def field(label, value):
                st.markdown(f"""
                    <div class="field-card">
                        <div class="field-label">{label}</div>
                        <div class="field-value">{value or 'N/A'}</div>
                    </div>
                """, unsafe_allow_html=True)

            field("First Name", p_info.first_name)
            field("Last Name", p_info.last_name)
            field("✉️ Email", p_info.email)
            field("📞 Phone", p_info.phone_number)
            field("🏠 Location", p_info.location)
            field("👔 LinkedIn", p_info.linkedin_url)
            field("🤖 GitHub", p_info.github_url)
            field("🌐 Portfolio", p_info.portfolio_url)

            st.divider()

            st.markdown("### 🛠️ Technical Competencies")
            skills = profile_data.skills
            st.write(f"**Languages:** {', '.join(skills.programming_languages or ['N/A'])}")
            st.write(f"**Frameworks & Tools:** {', '.join(skills.frameworks_and_tools or ['N/A'])}")
            st.write(f"**Soft Skills:** {', '.join(skills.soft_skills or ['N/A'])}")

            st.divider()

            st.markdown("### 📜 Certifications")
            for cert in profile_data.certifications:
                st.info(f"**{cert.name}** | {cert.issuing_organization} ({cert.issue_date})")
                
        with right:
            st.markdown("### 📄 Professional Summary")
            st.write(profile_data.professional_summary or "N/A")

            st.divider()

            st.markdown("### 💼 Work Experience")
            for job in profile_data.work_experience:
                with st.expander(f"{job.job_title} at {job.company_name} ({job.start_date} - {job.end_date or 'Present'})"):
                    st.write("**Responsibilities:**")
                    for resp in job.responsibilities:
                        st.write(f" - {resp}")

            st.divider()

            st.markdown("### 🎓 Academic Background")
            for edu in profile_data.education:
                st.info(f"**{edu.degree} in {edu.major}** | {edu.institution_name} ({edu.start_date} - {edu.end_date}) | GPA: {edu.gpa}")

            st.divider()

            st.markdown("### 🚀 Projects")
            for project in profile_data.projects:
                with st.expander(project.project_name):
                    st.write(project.description)
                    st.write(f"**Technologies:** {', '.join(project.technologies_used)}")

    except Exception as e:
        timer_placeholder.empty()
        st.error(f"Error in Processing : {e}")