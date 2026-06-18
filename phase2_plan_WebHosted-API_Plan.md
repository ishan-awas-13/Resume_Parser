# AI Resume Parser — Phase 2 Implementation Plan (Revised)
## Architecture Pivot: Local Ollama → Cloud Gemini API

> **Branch:** `Resume-Parser-Phase-2`
> **Starting Point:** Phase 1 baseline on `main` — single file upload, single Ollama model, 2-column display.
> **Key Pivot:** All LLM inference moves off the local machine to **Google's Gemini API** via Google AI Studio.

---

## Why This Pivot

| Concern | Phase 1 (Ollama / Local) | Phase 2 (Gemini API / Cloud) |
|---|---|---|
| Hardware dependency | Requires NVIDIA GPU, 8GB+ VRAM | No local GPU needed |
| Scalability | 1 resume at a time, VRAM bottleneck | Batch many resumes concurrently |
| Model quality | 3B–7B parameter SLMs | Gemini 1.5 Flash / Pro (state of the art) |
| Deployment | Only runs on dev machine | Any machine with an internet connection |
| Cost | Free (local) | Pay-per-token (very cheap for structured extraction) |

---

## Overview of Phase 2 Features

| # | Feature | Description |
|---|---|---|
| 1 | **Gemini API Integration** | Replace Ollama calls with async Gemini API calls for all resume parsing |
| 2 | **Multi-File Batch Upload** | Upload multiple resumes; process them concurrently via async API calls |
| 3 | **DBMS Integration** | Persist all parsed results to a database (SQLite for local dev, PostgreSQL for production) |
| 4 | **Central Scoring System** | Take Job Description and custom Evaluation Criteria from recruiter to score every uploaded resume |
| 5 | **Candidate Comparison Dashboard** | Ranked table comparing all candidates by their JD match score |
| 6 | **Data Export** | Download results as CSV or JSON |

---

## Feature 1 — Gemini API Integration

### API Setup
- API key generated from **Google AI Studio** — stored as an environment variable, never hardcoded.
- Model target: `gemini-1.5-flash` (fast, cheap, strong structured output support).
- Python library: `google-generativeai` (`pip install google-generativeai`).

### Configuration (`.env` file)
```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash
```

Load with `python-dotenv`:
```python
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
```

> [!CAUTION]
> Never commit `.env` to GitHub. Add it to `.gitignore` immediately.

### How the API Will Be Called (`parser_engine.py` — rewritten)

```python
import google.generativeai as genai
import asyncio

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    generation_config={"response_mime_type": "application/json"}  # forces JSON output
)

async def parse_resume_async(raw_text: str) -> ResumeParserResponse:
    response = await asyncio.to_thread(
        model.generate_content,
        [SYSTEM_PROMPT, raw_text]
    )
    return ResumeParserResponse.model_validate_json(response.text)
```

- `response_mime_type: "application/json"` forces Gemini to return structured JSON output — equivalent to Ollama's `format` argument.
- `asyncio.to_thread()` wraps the synchronous SDK call in a thread pool, enabling concurrent batch processing without blocking the event loop.

### Error Handling

All API calls are wrapped with retry logic:

| Error Type | Cause | Handling Strategy |
|---|---|---|
| `429 RESOURCE_EXHAUSTED` | Rate limit hit | Exponential backoff: wait 2s, 4s, 8s then raise |
| `500 INTERNAL` | Gemini server error | Retry up to 3 times, then mark file as failed |
| `InvalidArgument` | Malformed prompt / token limit | Log error, skip that file, continue batch |
| `JSONDecodeError` | Model output not valid JSON | Retry once with stricter prompt instruction |
| Network timeout | Connectivity issue | 30s timeout, retry once |

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import google.api_core.exceptions as gexc

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    retry=retry_if_exception_type((gexc.ResourceExhausted, gexc.ServiceUnavailable))
)
async def parse_resume_with_retry(raw_text: str) -> ResumeParserResponse:
    return await parse_resume_async(raw_text)
```

### Rate Limit Considerations

Gemini API has tiered rate limits. For **Google AI Studio free tier:**
- 15 requests per minute (RPM)
- 1 million tokens per minute (TPM)

For batch processing of N resumes:
- Add a **semaphore** to cap concurrent requests to a safe level (e.g. 5 at a time):
  ```python
  semaphore = asyncio.Semaphore(5)
  async def bounded_parse(text):
      async with semaphore:
          return await parse_resume_with_retry(text)
  ```
- If N > 15, add a `asyncio.sleep(60/15)` delay between calls automatically.

### New/Modified Files
- `parser_engine.py` — full rewrite: remove Ollama, add async Gemini calls + retry logic
- `requirements.txt` — add `google-generativeai`, `tenacity`, `python-dotenv`
- `.env` — new file (gitignored): API key and model config
- `.gitignore` — add `.env`

---

## Feature 2 — Multi-File Batch Upload

### Processing Flow
```
User uploads N resumes (PDF/DOCX)
        ↓
Extract raw text from all files (extractor.py — no change)
        ↓
Create N async tasks → fire all at Gemini API concurrently (bounded by semaphore)
        ↓
Collect results as they complete → store in st.session_state.all_candidates
        ↓
Failed files → logged to st.session_state.failed_files
        ↓
Display: progress bar + per-file status, then full results
```

### Key Design Decisions
- Each candidate entry: `{ "filename": str, "profile": CandidateProfile, "score": float | None, "error": str | None }`
- Processing driven by `asyncio.gather()` with the semaphore pattern from Feature 1
- Streamlit's `st.progress()` + `st.status()` shows live batch progress
- Files that fail (API error / validation error) are shown in a warning box, not silently dropped

### New/Modified Files
- `app.py` — multi-file uploader, async batch trigger, progress tracking

---

## Feature 3 — DBMS Integration

### Database Choice
- **Development:** SQLite (zero setup, file-based, built into Python)
- **Production:** PostgreSQL (scalable, supports concurrent writes)
- ORM: **SQLAlchemy** (same code works for both, swap the connection string)

### Schema

```sql
CREATE TABLE parse_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    filename        TEXT NOT NULL,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,
    phone           TEXT,
    location        TEXT,
    summary         TEXT,
    skills_json     TEXT,   -- JSON array stored as string
    experience_json TEXT,   -- JSON array
    education_json  TEXT,   -- JSON array
    certifications_json TEXT,
    projects_json   TEXT,
    jd_match_score  REAL,   -- populated after scoring step
    parsed_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_used      TEXT DEFAULT 'gemini-1.5-flash'
);
```

### Integration Points
- After each file is parsed successfully → immediately write a row to `candidates` table
- After scoring → update the `jd_match_score` column for each candidate
- On session load → optionally reload a previous session's results by `session_id`

### New Files
- `db.py` — SQLAlchemy models, `init_db()`, `save_candidate()`, `update_score()`, `fetch_session()`
- `resume_parser.db` — SQLite file created locally on first run (gitignored)

---

## Feature 4 — Central Scoring System

### What the Recruiter Provides
Two inputs in **Tab 3 — JD Scoring:**
1. **Job Description** — free-form text area (paste the full JD)
2. **Evaluation Criteria** — structured fields the recruiter fills in:
   - Required Skills (comma-separated list)
   - Minimum years of experience (number input)
   - Required degree level (dropdown: Any / Bachelor's / Master's / PhD)
   - Target major/field (optional text)

### Scoring Engine (`scorer.py` — no LLM needed)

| Signal | Input Source | Method | Weight |
|---|---|---|---|
| **Skills Match** | Candidate `programming_languages` + `frameworks_and_tools` vs. Required Skills + JD text | Token intersection ratio | 40% |
| **Role Relevance** | Candidate `job_title` entries vs. JD text | Fuzzy keyword presence check | 25% |
| **Experience Level** | Count of work experience entries × avg. duration proxy vs. minimum years | Threshold scoring | 20% |
| **Education Match** | Candidate degree level + major vs. recruiter requirements | Exact/fuzzy match | 15% |

Final score = weighted sum, normalized 0–100%.

### After Scoring
- Scores are written back to `st.session_state.all_candidates[i]["score"]`
- Scores are also persisted to the DBMS (`update_score()`)

---

## Feature 5 — Candidate Comparison Dashboard

A ranked table in **Tab 2**, auto-sorted by JD Match Score descending. Columns:

| Rank | Name | File | JD Score | Skills | Experience | Education |
|---|---|---|---|---|---|---|
| 1 | John Doe | cv1.pdf | 87% | 90% | 80% | 90% |
| 2 | Jane Smith | cv2.pdf | 72% | 70% | 75% | 70% |

- Table uses `st.dataframe` — unlocks after at least 1 candidate is processed
- Each row expands to show the full parsed candidate profile from Phase 1's 2-column layout
- Score columns are hidden until JD scoring has been run

---

## Feature 6 — Data Export

Two `st.download_button` widgets in the Dashboard tab:
1. **Export CSV** — flat table, one row per candidate, pandas `.to_csv()`
2. **Export JSON** — full profile data for all candidates, `json.dumps()`

Both in-memory, no disk writes.

---

## Proposed Tab Structure

```
[ 📂 Batch Upload & Parse ]  [ 📋 Candidate Dashboard ]  [ 📄 JD & Criteria Scoring ]
```

- **Tab 1 — Batch Upload & Parse:** Upload N files, trigger async Gemini batch, view per-candidate results
- **Tab 2 — Candidate Dashboard:** Ranked table + export (unlocks after ≥1 candidate processed)
- **Tab 3 — JD & Criteria Scoring:** Paste JD, fill recruiter criteria, trigger scoring, view score breakdown

---

## Complete File Change Map

| File | Status | Change Summary |
|---|---|---|
| `app.py` | Modify | Multi-file uploader, async batch, 3-tab layout, session state |
| `parser_engine.py` | **Full rewrite** | Remove Ollama, add async Gemini calls + retry/backoff |
| `scorer.py` | **Create new** | Pure Python JD match scoring |
| `db.py` | **Create new** | SQLAlchemy models + CRUD helpers |
| `extractor.py` | No change | Already handles file buffers |
| `schema.py` | No change | Pydantic models unchanged |
| `requirements.txt` | Update | Add `google-generativeai`, `tenacity`, `python-dotenv`, `sqlalchemy` |
| `.env` | **Create new** | `GEMINI_API_KEY`, `GEMINI_MODEL`, `DATABASE_URL` |
| `.gitignore` | Update | Add `.env`, `*.db` |

---

## Build Order

1. **Rewrite `parser_engine.py`** → verify Gemini API works with a single resume first
2. **Add `.env` config + `requirements.txt` updates** → environment fully set up
3. **Set up `db.py`** → SQLite schema initialized, save/load helpers tested
4. **Multi-file batch upload in `app.py`** → async batch with progress bar
5. **`scorer.py` + JD Scoring tab** → scoring logic on top of parsed data
6. **Candidate Dashboard** → ranked table with expand-to-profile
7. **Export buttons** → CSV + JSON download

---

## Deployment Notes

For running on any machine (not just the dev laptop):
- Copy `.env` manually (or use GitHub Secrets / environment variables in production)
- `pip install -r requirements.txt` in a fresh virtualenv
- `streamlit run app.py` — no GPU, no Ollama service needed
- For a hosted deployment (e.g. Streamlit Cloud): add `GEMINI_API_KEY` as a secret in the Streamlit Cloud dashboard, it maps directly to `os.getenv()`
