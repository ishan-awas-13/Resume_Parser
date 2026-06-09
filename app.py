import streamlit as st
from extractor import get_clean_resume_text 
from parser_engine import parse_resume_text
import os

st.set_page_config(page_title = "AI Resume parser", layout = "wide")
st.title("AI Resume Parser (Phase 1)")
st.write("Submit your resume PDF/DOCX file here to automatically extract candidate insights vis Locally Hosted Mistral:7B.")

#resume uploading
uploaded_file = st.file_uploader("Upload your Resume: ", type = ["pdf", "docx"])

if uploaded_file is not None:
    #save file temporarily to disk, to aid in extraction process
    #this lets the extraction  function read it path-wise
    temp_filename = f"temp_{uploaded_file.name}"
    
    with open(temp_filename, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success("Resume Recieved successfully! Starting backend pipeline processing...")

    with st.spinner("Local Model Mistral:7B is processing your resume... Please Wait..."):

        try:
            #1. Extract raw text.
            extracted_text = get_clean_resume_text(temp_filename)

            #2 Process via LLM & Pydantic schema
            parsed_profile = parse_resume_text(extracted_text)
            profile_data = parsed_profile.candidate_profile

            st.balloons()
            st.subheader("📊 Step 5: Exracted Candidate Insights Report")

            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown("### 👤 Personal Information")
                p_info = profile_data.personal_information

                st.metric("First Name, ", p_info.first_name or "N/A")
                st.metric("Last Name", p_info.last_name or "N/A")
                st.metric("✉️ Email", p_info.email or "N/A")
                st.metric("📞 Phone", p_info.phone_number or "N/A")
                st.metric("🏠 Location", p_info.location or "N/A")
                st.metric("👔 LinkedIn", p_info.linkedin_url or "N/A")
                st.metric("🤖 GitHub", p_info.github_url or "N/A")
                st.metric("🌐 Portfolio", p_info.portfolio_url  or "N/A")
            
            with col2:
                st.markdown("### 📄 Professional Summary")
                st.write(profile_data.professional_summary or "N/A")

                st.markdown("### 🛠️ Technical Competencies")
                skills = profile_data.skills 
                st.write(f"**Languages:** {', '.join(skills.programming_languages or ['N/A'])}")
                st.write(f"**Frameworks & Tools:** {', '.join(skills.frameworks_and_tools or ['N/A'])}")
                st.write(f"**Soft Skills:** {', '.join(skills.soft_skills or ['N/A'])}")
            
            #work experience
            st.markdown("### 💼 Work Experience")
            for job in profile_data.work_experience:
                with st.expander(f"{job.job_title} at {job.company_name} ({job.start_date} - {job.end_date or 'Present'})"):
                    st.write(f"**Location:** {job.location or "N/A"}")
                    st.write("**Core Responsiblities:**")            
                    for resp in job.responsibilities:
                        st.write(f"** - {resp}")

            st.markdown("### 🎓 Academic Foundations")                        
            for edu in profile_data.education:
                st.info(f"**{edu.degree} in {edu.major}** | {edu.institution_name} ({edu.start_date} - {edu.end_date}) | GPA: {edu.gpa}")
                
        except Exception as e:
            st.error(f"Error in Processing : {e}")
                
        finally:
            # cleanup temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
