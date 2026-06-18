import streamlit as st
from extractor import get_clean_resume_text
from parser_engine import parse_resume_text
from accuracy_engine import compute_accuracy
import time
import threading # <-- Essential addition for creating parallel execution lanes

st.set_page_config(page_title="AI Resume Parser", layout="wide")
st.title("AI Resume Parser (Benchmarking Edition)")

# ── Shared Model Dictionary ───────────────────────────────────────────────────
MODEL_DICT = {
    "mistral:7b (7B parameters)":          "mistral:7b",
    "phi4-mini:latest (3.8B parameters)":  "phi4-mini:latest",
    "llama3.2:3b (3.2B parameters)":       "llama3.2:3b",
    "qwen2.5:3b (3.1B parameters)":        "qwen2.5:3b",
}

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    div[data-testid="stMarkdownContainer"] p { font-size: 0.95rem; }
    div[data-testid="stAlert"] p, div[data-testid="stAlert"] div { font-size: 0.93rem !important; }
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
    </style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_parser, tab_bench = st.tabs(["📄 Resume Parser", "🔬 Benchmarking"])


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — RESUME PARSER  (existing logic, unchanged)
# ══════════════════════════════════════════════════════════════════════════════
with tab_parser:
    st.write("Submit your resume PDF/DOCX file here to automatically extract candidate insights via **Locally Hosted SLMs**.")

    model_selected = st.selectbox(
        label="Select Model:",
        options=list(MODEL_DICT.keys()),
        index=0,
        key="parser_model_select"
    )
    current_model = MODEL_DICT[model_selected]
    st.write("Selected Model : ", current_model)

    uploaded_file = st.file_uploader("Upload your Resume:", type=["pdf", "docx"], key="parser_uploader")

    if uploaded_file is not None:
        st.success("Resume Received successfully! Starting backend pipeline processing...")

        timer_placeholder  = st.empty()
        status_placeholder = st.empty()
        status_placeholder.info("Preparing document text extraction...")

        try:
            extracted_text = get_clean_resume_text(uploaded_file)

            pipeline_container   = {}
            pipeline_error       = []
            processing_complete  = threading.Event()

            def background_inference_worker():
                try:
                    result = parse_resume_text(current_model, extracted_text)
                    pipeline_container["data"] = result
                except Exception as e:
                    pipeline_error.append(e)
                finally:
                    processing_complete.set()

            inference_thread = threading.Thread(target=background_inference_worker)
            start_marker     = time.time()
            inference_thread.start()

            status_placeholder.info(f"Local Model **{current_model}** is processing your resume… Please Wait…")
            while not processing_complete.is_set():
                elapsed = time.time() - start_marker
                timer_placeholder.metric(
                    label=f"⏱️ Processing Stopwatch ({current_model})",
                    value=f"{elapsed:.1f} s"
                )
                time.sleep(0.1)

            total_latency = time.time() - start_marker
            status_placeholder.empty()

            if pipeline_error:
                raise pipeline_error[0]

            parsed_profile = pipeline_container["data"]
            profile_data   = parsed_profile.candidate_profile

            st.balloons()
            st.subheader("📊 Extracted Candidate Insights Report")
            timer_placeholder.metric(label="⏱️ Final Execution Latency", value=f"{total_latency:.2f} s")
            st.divider()

            left, right = st.columns([1, 1])

            def field(label, value):
                st.markdown(f"""
                    <div class="field-card">
                        <div class="field-label">{label}</div>
                        <div class="field-value">{value or 'N/A'}</div>
                    </div>
                """, unsafe_allow_html=True)

            with left:
                st.markdown("### 👤 Personal Information")
                p_info = profile_data.personal_information
                field("First Name",  p_info.first_name)
                field("Last Name",   p_info.last_name)
                field("✉️ Email",    p_info.email)
                field("📞 Phone",    p_info.phone_number)
                field("🏠 Location", p_info.location)
                field("👔 LinkedIn", p_info.linkedin_url)
                field("🤖 GitHub",   p_info.github_url)
                field("🌐 Portfolio",p_info.portfolio_url)

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
                    with st.expander(f"{job.job_title} at {job.company_name} ({job.start_date} – {job.end_date or 'Present'})"):
                        st.write("**Responsibilities:**")
                        for resp in job.responsibilities:
                            st.write(f" - {resp}")

                st.divider()
                st.markdown("### 🎓 Academic Background")
                for edu in profile_data.education:
                    st.info(f"**{edu.degree} in {edu.major}** | {edu.institution_name} ({edu.start_date} – {edu.end_date}) | GPA: {edu.gpa}")

                st.divider()
                st.markdown("### 🚀 Projects")
                for project in profile_data.projects:
                    with st.expander(project.project_name):
                        st.write(project.description)
                        st.write(f"**Technologies:** {', '.join(project.technologies_used)}")

        except Exception as e:
            timer_placeholder.empty()
            st.error(f"Error in Processing: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — BENCHMARKING
# ══════════════════════════════════════════════════════════════════════════════
with tab_bench:
    st.subheader("🔬 SLM Accuracy Benchmark")
    st.write(
        "Upload a resume, select a **Reference Model** (ground truth) and one or more "
        "**Test Models** to compare. The system will run all models on the same resume "
        "and score each test model's output against the reference."
    )
    st.divider()

    # ── Configuration ─────────────────────────────────────────────────────────
    bcol1, bcol2 = st.columns([1, 1])

    with bcol1:
        ref_label = st.selectbox(
            "🏆 Reference Model (Ground Truth):",
            options=list(MODEL_DICT.keys()),
            index=0,
            key="bench_ref_model"
        )
        ref_model = MODEL_DICT[ref_label]

    with bcol2:
        # Default test options = everything except the chosen reference
        default_test_labels = [k for k in MODEL_DICT.keys() if k != ref_label]
        test_labels = st.multiselect(
            "🧪 Test Models to Compare:",
            options=[k for k in MODEL_DICT.keys() if k != ref_label],
            default=default_test_labels[:2],   # pre-select first 2 by default
            key="bench_test_models"
        )
        test_models = [MODEL_DICT[l] for l in test_labels]

    bench_file = st.file_uploader(
        "Upload Resume for Benchmarking:", type=["pdf", "docx"], key="bench_uploader"
    )

    run_button = st.button("▶️ Run Benchmark", type="primary", key="run_bench")

    # ── Execution ──────────────────────────────────────────────────────────────
    if run_button:
        if bench_file is None:
            st.warning("Please upload a resume file before running the benchmark.")
        elif not test_models:
            st.warning("Please select at least one test model to compare against.")
        else:
            st.divider()

            # ── Step 1: Text Extraction ────────────────────────────────────────
            with st.spinner("Extracting text from resume…"):
                bench_file.seek(0)   # reset buffer pointer in case it was read before
                extracted_text = get_clean_resume_text(bench_file)
            st.success("✅ Text extracted successfully.")

            # ── Step 2: Reference Model Run ────────────────────────────────────
            st.info(f"⚙️ Running **Reference Model** ({ref_model})…")
            ref_timer = st.empty()
            ref_result_container = {}
            ref_error_container  = []
            ref_done             = threading.Event()

            def run_ref():
                try:
                    ref_result_container["data"] = parse_resume_text(ref_model, extracted_text)
                except Exception as e:
                    ref_error_container.append(e)
                finally:
                    ref_done.set()

            t0 = time.time()
            threading.Thread(target=run_ref).start()
            while not ref_done.is_set():
                ref_timer.metric("⏱️ Reference Model", f"{time.time()-t0:.1f} s")
                time.sleep(0.1)
            ref_latency = time.time() - t0
            ref_timer.metric("⏱️ Reference Model", f"{ref_latency:.2f} s ✓")

            if ref_error_container:
                st.error(f"Reference model failed: {ref_error_container[0]}")
                st.stop()

            reference_profile = ref_result_container["data"].candidate_profile
            st.success(f"✅ Reference model ({ref_model}) completed in **{ref_latency:.2f}s**.")

            # ── Step 3: Test Model Runs (Sequential) ───────────────────────────
            all_results = []   # list of dicts from compute_accuracy()

            for test_model in test_models:
                st.info(f"⚙️ Running **Test Model** ({test_model})…")
                test_timer           = st.empty()
                test_result_container = {}
                test_error_container  = []
                test_done             = threading.Event()

                def run_test(model=test_model):
                    try:
                        test_result_container["data"] = parse_resume_text(model, extracted_text)
                    except Exception as e:
                        test_error_container.append(e)
                    finally:
                        test_done.set()

                t1 = time.time()
                threading.Thread(target=run_test).start()
                while not test_done.is_set():
                    test_timer.metric(f"⏱️ {test_model}", f"{time.time()-t1:.1f} s")
                    time.sleep(0.1)
                test_latency = time.time() - t1
                test_timer.metric(f"⏱️ {test_model}", f"{test_latency:.2f} s ✓")

                if test_error_container:
                    st.error(f"Test model {test_model} failed: {test_error_container[0]}")
                    continue

                test_profile = test_result_container["data"].candidate_profile

                # ── Step 4: Score this model ───────────────────────────────────
                result = compute_accuracy(
                    reference=reference_profile,
                    test=test_profile,
                    model_name=test_model,
                    latency_seconds=test_latency
                )
                all_results.append(result)
                st.success(f"✅ {test_model} scored **{result['overall_score']*100:.1f}%** overall in {test_latency:.2f}s.")

            # ── Results Display ────────────────────────────────────────────────
            if all_results:
                st.divider()
                st.subheader("📊 Benchmark Results")
                st.caption(f"Reference model: **{ref_model}**  |  Scores are relative to its output (1.0 = perfect match)")

                # ── Summary Table ──────────────────────────────────────────────
                import pandas as pd

                summary_rows = []
                for r in all_results:
                    row = {
                        "Model":                r["model"],
                        "Latency (s)":          round(r["latency"], 2),
                        "Overall (%)":          round(r["overall_score"] * 100, 1),
                        "Personal Info (%)":    round(r["section_scores"]["personal_information"] * 100, 1),
                        "Skills (%)":           round(r["section_scores"]["skills"] * 100, 1),
                        "Work Experience (%)":  round(r["section_scores"]["work_experience"] * 100, 1),
                        "Education (%)":        round(r["section_scores"]["education"] * 100, 1),
                        "Certifications (%)":   round(r["section_scores"]["certifications"] * 100, 1),
                        "Projects (%)":         round(r["section_scores"]["projects"] * 100, 1),
                    }
                    summary_rows.append(row)

                df = pd.DataFrame(summary_rows).set_index("Model")
                st.dataframe(df, width='stretch')

                # ── Bar Chart — Overall Score ──────────────────────────────────
                st.markdown("#### Overall Accuracy Score by Model")
                chart_data = pd.DataFrame(
                    {"Overall Score (%)": [r["overall_score"] * 100 for r in all_results]},
                    index=[r["model"] for r in all_results]
                )
                st.bar_chart(chart_data)

                # ── Per-Model Field-Level Detail ───────────────────────────────
                st.markdown("#### Detailed Field-Level Scores")
                for r in all_results:
                    with st.expander(f"🔍 {r['model']} — field breakdown"):
                        field_df = pd.DataFrame(
                            {"Score": {k: round(v * 100, 1) for k, v in r["field_scores"].items()}}
                        )
                        st.dataframe(field_df, width='stretch')