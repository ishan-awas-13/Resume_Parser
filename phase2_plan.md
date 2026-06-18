# AI Resume Parser — Phase 2 Implementation Plan

> **Branch:** `Resume-Parser-Phase-2`
> **Starting Point:** Phase 1 baseline on `main` — single file upload, single model, 2-column output display.

---

## Overview of New Features

| # | Feature                                  | Description                                                                                              |
| - | ---------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 1 | **Multi-File Batch Upload**        | Upload multiple resumes at once and process them all through the same model pipeline                     |
| 2 | **Central Scoring System**         | Take Criteria and Job Description from Recruiter to score every uploaded resume against it automatically |
| 3 | **Candidate Comparison Dashboard** | Side-by-side table ranking all candidates by their match score                                           |
| 4 | **Data Export**                    | Download the full results as a CSV or JSON file                                                          |

---

## Feature 1 — Multi-File Batch Upload

### What Changes

The single `st.file_uploader` is replaced with a **multi-file uploader** (`accept_multiple_files=True`). The app processes each uploaded resume one-by-one, displaying a progress bar and live status indicator for each file.

### Processing Flow

```
User uploads N resumes
        ↓
For each resume:
    1. Extract text (extractor.py)
    2. Run LLM → get CandidateProfile (parser_engine.py)
    3. Store result in a session_state list: st.session_state.all_candidates
        ↓
When all done → display results for each candidate in collapsible expanders
```

### Key Design Decisions

- Each result is a dict: `{ "filename": str, "profile": CandidateProfile, "score": float | None }`
- Results are stored in `st.session_state.all_candidates` so they persist across tab switches
- Processing is sequential (not parallel) to avoid VRAM overload on local machines
- A `st.progress()` bar shows how many files have been processed out of the total

### New/Modified Files

- `app.py` — replace uploader, add loop, add progress bar, store results in session state

---

## Feature 2 — Central Scoring System

### What It Does

The recruiter provides a **Job Description (JD)** and optional **Evaluation Criteria** (e.g. key programming languages, minimum experience, key soft skills) via text input fields. The system then reads each candidate's extracted JSON profile and scores them against these parameters automatically.

### Scoring Logic (new file: `scorer.py`)

The score is calculated in Python. It compares the candidate's extracted fields against keywords in the JD text combined with the custom specified evaluation criteria:

| Signal                     | Method                                                                                             | Weight |
| -------------------------- | -------------------------------------------------------------------------------------------------- | ------ |
| **Skills match**     | Compare candidate's programming languages & tools against the JD text and explicit skills criteria | 40%    |
| **Role Relevance**   | Check if candidate's job titles match or are similar to the role requirements                      | 25%    |
| **Experience level** | Compare total years of work experience against specified minimum requirements                      | 20%    |
| **Education check**  | Match candidate's degree type & major against target requirements                                  | 15%    |

Final score = weighted sum of the above, normalized to 0–100%.

### Key Design Decisions

- The JD and Evaluation Criteria are stored in `st.session_state`
- Scoring is triggered by a "Score All Candidates" button
- Scores are written back into the `st.session_state.all_candidates` list
- If no criteria/JD is provided, scores stay `None`

### New/Modified Files

- `scorer.py` — **new file**, scoring logic
- `app.py` — add input fields for JD and criteria, "Score Candidates" button, update state

---

## Feature 3 — Candidate Comparison Dashboard

### What It Shows

A ranked table of all processed candidates, with columns:

| Rank | Candidate Name | File        | Overall Score | Skills Match | Experience | Education |
| ---- | -------------- | ----------- | ------------- | ------------ | ---------- | --------- |
| 1    | John Doe       | resume1.pdf | 87%           | 90%          | 80%        | 90%       |
| 2    | Jane Smith     | resume2.pdf | 72%           | 70%          | 75%        | 70%       |

- Table is sorted by Overall Score (descending) automatically
- Clicking a row (or expanding via `st.expander`) opens the full candidate profile view from Phase 1
- If no JD scoring has been done, the table still shows all candidates but without score columns

### New/Modified Files

- `app.py` — new section below the uploader results, built with `st.dataframe` or `st.table`

---

## Feature 4 — Data Export

### What It Exports

Two download buttons appear after candidates have been processed:

1. **Export as CSV** — flat table with one row per candidate, columns = all scored fields
2. **Export as JSON** — full extracted profile data for all candidates in a JSON array

Both are generated in-memory using `pandas` and Python's `json` module — no files written to disk.

### New/Modified Files

- `app.py` — two `st.download_button` widgets, one for CSV and one for JSON

---

## Proposed Tab Structure for Phase 2

```
[ 📂 Batch Upload & Parse ]  [ 📋 Candidate Dashboard ]  [ 📄 Job Description Scoring ]
```

- **Tab 1 — Batch Upload & Parse:** Upload files, pick model, process all resumes, view individual results
- **Tab 2 — Candidate Dashboard:** Ranked comparison table + export buttons (unlocks after at least 1 candidate is processed)
- **Tab 3 — Job Description Scoring:** Paste JD, trigger scoring, view score breakdown per candidate

---

## New File Summary

| File                 | Status               | Purpose                                      |
| -------------------- | -------------------- | -------------------------------------------- |
| `app.py`           | Modify               | Complete rewrite of UI for multi-file + tabs |
| `scorer.py`        | **Create new** | JD match scoring logic — no LLM             |
| `extractor.py`     | No change            | Already handles file buffers                 |
| `parser_engine.py` | No change            | Already handles model + text → JSON         |
| `schema.py`        | No change            | Pydantic models stay the same                |

---

## Build Order

1. **Multi-file upload + batch processing loop** — get all candidates into session state first
2. **Candidate Dashboard tab** — display the raw table before scoring is added
3. **scorer.py + JD Scoring tab** — add scores on top of existing data
4. **Export buttons** — last, since they depend on data from all previous steps
