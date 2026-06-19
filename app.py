import streamlit as st
from extractor import get_clean_resume_text
from parser_engine import parse_resume_text
import time
import threading
import json

st.set_page_config(page_title="AI Resume Parser — Phase 2", layout="wide")
st.title("AI Resume Parser (Phase 2 — Batch Mode)")
st.write("Upload multiple resumes and run them all through a locally hosted SLM.")

# ── Model Dictionary ──────────────────────────────────────────────────────────
MODEL_DICT = {
    "qwen2.5:3b (3.1B parameters)":       "qwen2.5:3b",       # default — smaller & fast
    "llama3.2:3b (3.2B parameters)":       "llama3.2:3b",
    "phi4-mini:latest (3.8B parameters)":  "phi4-mini:latest",
    "mistral:7b (7B parameters)":          "mistral:7b",
}

# ── Session State ─────────────────────────────────────────────────────────────
if "parsed_resumes" not in st.session_state:
    # Each entry: { filename, profile, json_data, latency, error }
    st.session_state.parsed_resumes = []
if "parsing_complete" not in st.session_state:
    st.session_state.parsing_complete = False

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    div[data-testid="stMarkdownContainer"] p { font-size: 0.95rem; }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div { font-size: 0.93rem !important; }
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] p { font-size: 0.93rem; }
    div[data-testid="stColumn"] {
        border: 2px solid #444 !important;
        border-radius: 10px !important;
        padding: 15px !important;
        box-sizing: border-box !important;
    }
    .field-card  { margin-bottom: 12px; line-height: 1.5; }
    .field-label { font-size: 0.75rem; color: #888; font-weight: 600;
                   text-transform: uppercase; letter-spacing: 0.04em; }
    .field-value { font-size: 0.95rem; color: inherit; word-break: break-word; }

    /* Resume card header styling */
    .resume-header {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        border-left: 4px solid #4a90e2;
        padding: 12px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .resume-header h3 { margin: 0; color: #e0e0e0; font-size: 1.1rem; }
    .resume-meta { font-size: 0.8rem; color: #888; margin-top: 4px; }
    </style>
""", unsafe_allow_html=True)

# ── Controls (above tabs — always visible) ────────────────────────────────────
ctrl_col1, ctrl_col2 = st.columns([2, 1])

with ctrl_col1:
    uploaded_files = st.file_uploader(
        "📂 Upload Resume Files:",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="batch_uploader",
        help="Select one or more PDF / DOCX resume files to process."
    )

with ctrl_col2:
    model_label = st.selectbox(
        "🤖 Select Local Model:",
        options=list(MODEL_DICT.keys()),
        index=0,   # defaults to qwen2.5:3b (3.1B)
        key="batch_model_select"
    )
    current_model = MODEL_DICT[model_label]
    st.caption(f"Running on: `{current_model}`")

run_btn = st.button(
    "▶️ Parse All Resumes",
    type="primary",
    key="run_batch",
    disabled=(not uploaded_files)
)

# ── Batch Processing ──────────────────────────────────────────────────────────
if run_btn and uploaded_files:
    # Clear any previous run
    st.session_state.parsed_resumes = []
    st.session_state.parsing_complete = False

    st.divider()
    total = len(uploaded_files)
    st.info(f"Starting batch: **{total} file(s)** → model `{current_model}`")

    overall_progress = st.progress(0, text="Starting…")

    for idx, file in enumerate(uploaded_files):
        file_label = file.name
        st.markdown(
            f'<div class="resume-header">'
            f'<h3>📄 {file_label}</h3>'
            f'<div class="resume-meta">File {idx+1} of {total}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        timer_ph  = st.empty()
        status_ph = st.empty()
        status_ph.info("Extracting text…")

        try:
            file.seek(0)
            extracted_text = get_clean_resume_text(file)
            status_ph.info(f"Text extracted — sending to `{current_model}`…")

            # Thread + event pattern (keeps stopwatch ticking)
            result_box = {}
            error_box  = []
            done_event = threading.Event()

            def _worker(model=current_model, text=extracted_text):
                try:
                    result_box["data"] = parse_resume_text(model, text)
                except Exception as exc:
                    error_box.append(exc)
                finally:
                    done_event.set()

            t0 = time.time()
            threading.Thread(target=_worker, daemon=True).start()

            while not done_event.is_set():
                timer_ph.metric(f"⏱️ {file_label}", f"{time.time()-t0:.1f} s")
                time.sleep(0.1)

            latency = time.time() - t0
            status_ph.empty()

            if error_box:
                timer_ph.metric(f"⏱️ {file_label}", f"{latency:.2f} s  ✗")
                st.error(f"❌ Failed: {error_box[0]}")
                st.session_state.parsed_resumes.append({
                    "filename": file_label,
                    "profile":   None,
                    "json_data": None,
                    "latency":   latency,
                    "error":     str(error_box[0]),
                })
            else:
                timer_ph.metric(f"⏱️ {file_label}", f"{latency:.2f} s  ✓")
                parsed = result_box["data"]
                st.success(f"✅ Parsed in {latency:.2f}s")
                st.session_state.parsed_resumes.append({
                    "filename": file_label,
                    "profile":   parsed.candidate_profile,
                    "json_data": parsed.model_dump(),
                    "latency":   latency,
                    "error":     None,
                })

        except Exception as exc:
            st.error(f"❌ Text extraction failed: {exc}")
            st.session_state.parsed_resumes.append({
                "filename": file_label,
                "profile":   None,
                "json_data": None,
                "latency":   0,
                "error":     str(exc),
            })

        overall_progress.progress(
            (idx + 1) / total,
            text=f"Processed {idx+1}/{total} — {file_label}"
        )

    st.session_state.parsing_complete = True
    overall_progress.progress(1.0, text="All resumes processed!")
    st.balloons()


# ══════════════════════════════════════════════════════════════════════════════
#  TABS  (rendered after controls — data already in session_state)
# ══════════════════════════════════════════════════════════════════════════════
st.divider()

tab_results, tab_json = st.tabs([
    "📊 Parsed Resumes",
    "🗂️ Parsed Resume JSON"
])


# ── Helper: render one candidate profile (2-column layout) ───────────────────
def _render_profile(profile_data):
    def field(label, value):
        st.markdown(f"""
            <div class="field-card">
                <div class="field-label">{label}</div>
                <div class="field-value">{value or 'N/A'}</div>
            </div>
        """, unsafe_allow_html=True)

    left, right = st.columns([1, 1])

    with left:
        st.markdown("#### 👤 Personal Information")
        p = profile_data.personal_information
        field("First Name",  p.first_name)
        field("Last Name",   p.last_name)
        field("✉️ Email",    p.email)
        field("📞 Phone",    p.phone_number)
        field("🏠 Location", p.location)
        field("👔 LinkedIn", p.linkedin_url)
        field("🤖 GitHub",   p.github_url)
        field("🌐 Portfolio",p.portfolio_url)

        st.divider()
        st.markdown("#### 🛠️ Technical Competencies")
        skills = profile_data.skills
        st.write(f"**Languages:** {', '.join(skills.programming_languages or ['N/A'])}")
        st.write(f"**Frameworks & Tools:** {', '.join(skills.frameworks_and_tools or ['N/A'])}")
        st.write(f"**Soft Skills:** {', '.join(skills.soft_skills or ['N/A'])}")

        if profile_data.certifications:
            st.divider()
            st.markdown("#### 📜 Certifications")
            for cert in profile_data.certifications:
                st.info(f"**{cert.name}** | {cert.issuing_organization} ({cert.issue_date})")

    with right:
        st.markdown("#### 📄 Professional Summary")
        st.write(profile_data.professional_summary or "N/A")

        if profile_data.work_experience:
            st.divider()
            st.markdown("#### 💼 Work Experience")
            for job in profile_data.work_experience:
                with st.expander(f"{job.job_title} at {job.company_name} ({job.start_date} – {job.end_date or 'Present'})"):
                    for resp in job.responsibilities:
                        st.write(f" - {resp}")

        if profile_data.education:
            st.divider()
            st.markdown("#### 🎓 Academic Background")
            for edu in profile_data.education:
                st.info(f"**{edu.degree} in {edu.major}** | {edu.institution_name} ({edu.start_date} – {edu.end_date}) | GPA: {edu.gpa}")

        if profile_data.projects:
            st.divider()
            st.markdown("#### 🚀 Projects")
            for project in profile_data.projects:
                with st.expander(project.project_name or "Unnamed Project"):
                    st.write(project.description)
                    if project.technologies_used:
                        st.write(f"**Technologies:** {', '.join(project.technologies_used)}")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — PARSED RESUMES
# ══════════════════════════════════════════════════════════════════════════════
with tab_results:
    if not st.session_state.parsed_resumes:
        st.markdown("""
            <div style="text-align:center; padding:60px 20px; color:#666;
                        border:2px dashed #444; border-radius:12px; margin-top:20px;">
                <h3 style="color:#555; margin-bottom:10px;">No Resumes Parsed Yet</h3>
                <p style="font-size:0.95rem;">
                    Upload one or more resume files above and click
                    <strong>▶️ Parse All Resumes</strong> to begin.
                </p>
            </div>
        """, unsafe_allow_html=True)
    else:
        success_count = sum(1 for r in st.session_state.parsed_resumes if r["error"] is None)
        fail_count    = len(st.session_state.parsed_resumes) - success_count
        st.subheader(f"📊 Results — {success_count} parsed successfully, {fail_count} failed")

        for entry in st.session_state.parsed_resumes:
            # ── Resume header card ────────────────────────────────────────────
            st.markdown(
                f'<div class="resume-header">'
                f'<h3>📄 {entry["filename"]}</h3>'
                f'<div class="resume-meta">Latency: {entry["latency"]:.2f}s'
                + (f' &nbsp;|&nbsp; <span style="color:#f55;">Error</span>' if entry["error"] else ' &nbsp;|&nbsp; <span style="color:#4caf50;">✓ Parsed</span>')
                + '</div></div>',
                unsafe_allow_html=True
            )

            if entry["error"]:
                st.error(f"Failed to parse this file: {entry['error']}")
            else:
                _render_profile(entry["profile"])

            st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — PARSED RESUME JSON
# ══════════════════════════════════════════════════════════════════════════════
with tab_json:
    st.subheader("🗂️ Raw JSON Outputs")
    st.caption("JSON data extracted by the model for each resume in the current batch. Resets when a new batch is started.")
    st.divider()

    if not st.session_state.parsing_complete:
        st.markdown("""
            <div style="text-align:center; padding:60px 20px; color:#666;
                        border:2px dashed #444; border-radius:12px; margin-top:20px;">
                <h3 style="color:#555; margin-bottom:10px;">No Data Yet</h3>
                <p style="font-size:0.95rem;">
                    Run a batch parse from above first.<br>
                    The JSON output for each resume will appear here once parsing is complete.
                </p>
            </div>
        """, unsafe_allow_html=True)
    else:
        for entry in st.session_state.parsed_resumes:
            status_icon = "✅" if entry["error"] is None else "❌"
            with st.expander(f"{status_icon} {entry['filename']}  ({entry['latency']:.2f}s)", expanded=False):
                if entry["error"]:
                    st.error(f"Parse error: {entry['error']}")
                else:
                    st.code(json.dumps(entry["json_data"], indent=2), language="json")
