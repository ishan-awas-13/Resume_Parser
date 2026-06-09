import streamlit as st
from extractor import get_clean_resume_text 
from parser_engine import parse_resume_text
import os

st.set_page_config(page_title="AI Resume parser", layout="wide")
st.title("AI Resume Parser (Phase 1)")
st.write("Submit your resume PDF/DOCX file here to automatically extract candidate insights via **Locally Hosted Mistral:7B**.")

# Inject CSS — moderate font sizes for 2-column layout
st.markdown("""
    <style>
    /* Moderate font size for st.write paragraphs */
    div[data-testid="stMarkdownContainer"] p {
        font-size: 0.95rem;
    }
    /* Moderate st.info alert text */
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div {
        font-size: 0.93rem !important;
    }
    /* Moderate expander body text */
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] p {
        font-size: 0.93rem;
    }
    /* Custom field card for personal info */
    .field-card {
        margin-bottom: 12px;
        line-height: 1.5;
    }
    .field-label {
        font-size: 0.75rem;
        color: #888;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .field-value {
        font-size: 0.95rem;
        color: inherit;
        word-break: break-word;
    }
    </style>
""", unsafe_allow_html=True)

#resume uploading
uploaded_file = st.file_uploader("Upload your Resume: ", type=["pdf", "docx"])

if uploaded_file is not None:
    st.success("Resume Received successfully! Starting backend pipeline processing...")

    with st.spinner("Local Model Mistral:7B is processing your resume... Please Wait..."):
        try:
            # 1. Extract raw text directly from the uploaded file buffer
            extracted_text = get_clean_resume_text(uploaded_file)

            # 2. Process via LLM & Pydantic schema
            parsed_profile = parse_resume_text(extracted_text)
            profile_data = parsed_profile.candidate_profile

            st.balloons()
            st.subheader("📊 Extracted Candidate Insights Report")
            st.divider()

            left, right = st.columns([1, 1])

            # ── LEFT COLUMN ──────────────────────────────────────────────
            with left:

                # Personal Information
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

                # Technical Competencies
                st.markdown("### 🛠️ Technical Competencies")
                skills = profile_data.skills
                st.write(f"**Languages:** {', '.join(skills.programming_languages or ['N/A'])}")
                st.write(f"**Frameworks & Tools:** {', '.join(skills.frameworks_and_tools or ['N/A'])}")
                st.write(f"**Soft Skills:** {', '.join(skills.soft_skills or ['N/A'])}")

                st.divider()

                # Certifications
                st.markdown("### 📜 Certifications")
                for cert in profile_data.certifications:
                    st.info(f"**{cert.name}** | {cert.issuing_organization} ({cert.issue_date})")

            # ── RIGHT COLUMN ─────────────────────────────────────────────
            with right:

                # Professional Summary
                st.markdown("### 📄 Professional Summary")
                st.write(profile_data.professional_summary or "N/A")

                st.divider()

                # Work Experience
                st.markdown("### 💼 Work Experience")
                for job in profile_data.work_experience:
                    with st.expander(f"{job.job_title} at {job.company_name} ({job.start_date} - {job.end_date or 'Present'})"):
                        st.write("**Responsibilities:**")
                        for resp in job.responsibilities:
                            st.write(f" - {resp}")

                st.divider()

                # Academic Background
                st.markdown("### 🎓 Academic Background")
                for edu in profile_data.education:
                    st.info(f"**{edu.degree} in {edu.major}** | {edu.institution_name} ({edu.start_date} - {edu.end_date}) | GPA: {edu.gpa}")

                st.divider()

                # Projects
                st.markdown("### 🚀 Projects")
                for project in profile_data.projects:
                    with st.expander(project.project_name):
                        st.write(project.description)
                        st.write(f"**Technologies:** {', '.join(project.technologies_used)}")

        except Exception as e:
            st.error(f"Error in Processing : {e}")

