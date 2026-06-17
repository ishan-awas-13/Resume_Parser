"""
accuracy_engine.py
──────────────────
Compares a test model's CandidateProfile output against a reference
model's CandidateProfile output and returns structured accuracy scores.

Scoring rules:
  - Exact string fields  → 1.0 if match (case-insensitive, trimmed), else 0.0
  - List-of-string fields → Jaccard similarity (intersection / union)
  - Nested object lists   → matched by index, average attribute scores
"""

from schema import CandidateProfile
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def _exact_score(a: Optional[str], b: Optional[str]) -> float:
    """Return 1.0 if both strings match case-insensitively, else 0.0.
    Two None values count as a match (both models agreed nothing was there)."""
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    return 1.0 if a.strip().lower() == b.strip().lower() else 0.0


def _jaccard_score(ref_list: list, test_list: list) -> float:
    """Jaccard similarity between two lists of strings (case-insensitive)."""
    ref_set  = {s.strip().lower() for s in ref_list  if s}
    test_set = {s.strip().lower() for s in test_list if s}
    if not ref_set and not test_set:
        return 1.0   # Both empty — models agreed
    if not ref_set or not test_set:
        return 0.0
    intersection = ref_set & test_set
    union        = ref_set | test_set
    return len(intersection) / len(union)


def _average(scores: list) -> float:
    return sum(scores) / len(scores) if scores else 0.0


# ── Section Scorers ───────────────────────────────────────────────────────────

def _score_personal_info(ref, test) -> dict:
    fields = ["first_name", "last_name", "email", "phone_number",
              "location", "linkedin_url", "github_url", "portfolio_url"]
    scores = {}
    for f in fields:
        scores[f] = _exact_score(getattr(ref, f, None), getattr(test, f, None))
    return scores


def _score_skills(ref, test) -> dict:
    return {
        "programming_languages": _jaccard_score(
            ref.programming_languages, test.programming_languages),
        "frameworks_and_tools":  _jaccard_score(
            ref.frameworks_and_tools,  test.frameworks_and_tools),
        "soft_skills":           _jaccard_score(
            ref.soft_skills,           test.soft_skills),
    }


def _score_work_experience(ref_list, test_list) -> dict:
    """Match jobs by index and average attribute-level scores."""
    if not ref_list and not test_list:
        return {"work_experience": 1.0}
    if not ref_list or not test_list:
        return {"work_experience": 0.0}

    pair_scores = []
    for i, ref_job in enumerate(ref_list):
        if i >= len(test_list):
            pair_scores.append(0.0)
            continue
        test_job = test_list[i]
        job_field_scores = [
            _exact_score(ref_job.company_name, test_job.company_name),
            _exact_score(ref_job.job_title,    test_job.job_title),
            _exact_score(ref_job.location,     test_job.location),
            _exact_score(ref_job.start_date,   test_job.start_date),
            _exact_score(ref_job.end_date,     test_job.end_date),
            _jaccard_score(ref_job.responsibilities, test_job.responsibilities),
        ]
        pair_scores.append(_average(job_field_scores))
    return {"work_experience": _average(pair_scores)}


def _score_education(ref_list, test_list) -> dict:
    if not ref_list and not test_list:
        return {"education": 1.0}
    if not ref_list or not test_list:
        return {"education": 0.0}

    pair_scores = []
    for i, ref_edu in enumerate(ref_list):
        if i >= len(test_list):
            pair_scores.append(0.0)
            continue
        test_edu = test_list[i]
        edu_field_scores = [
            _exact_score(ref_edu.institution_name, test_edu.institution_name),
            _exact_score(ref_edu.degree,           test_edu.degree),
            _exact_score(ref_edu.major,            test_edu.major),
            _exact_score(ref_edu.start_date,       test_edu.start_date),
            _exact_score(ref_edu.end_date,         test_edu.end_date),
            _exact_score(ref_edu.gpa,              test_edu.gpa),
        ]
        pair_scores.append(_average(edu_field_scores))
    return {"education": _average(pair_scores)}


def _score_certifications(ref_list, test_list) -> dict:
    if not ref_list and not test_list:
        return {"certifications": 1.0}
    if not ref_list or not test_list:
        return {"certifications": 0.0}

    pair_scores = []
    for i, ref_cert in enumerate(ref_list):
        if i >= len(test_list):
            pair_scores.append(0.0)
            continue
        test_cert = test_list[i]
        cert_scores = [
            _exact_score(ref_cert.name,                 test_cert.name),
            _exact_score(ref_cert.issuing_organization, test_cert.issuing_organization),
            _exact_score(ref_cert.issue_date,           test_cert.issue_date),
        ]
        pair_scores.append(_average(cert_scores))
    return {"certifications": _average(pair_scores)}


def _score_projects(ref_list, test_list) -> dict:
    if not ref_list and not test_list:
        return {"projects": 1.0}
    if not ref_list or not test_list:
        return {"projects": 0.0}

    pair_scores = []
    for i, ref_proj in enumerate(ref_list):
        if i >= len(test_list):
            pair_scores.append(0.0)
            continue
        test_proj = test_list[i]
        proj_scores = [
            _exact_score(ref_proj.project_name, test_proj.project_name),
            _jaccard_score(ref_proj.technologies_used, test_proj.technologies_used),
        ]
        pair_scores.append(_average(proj_scores))
    return {"projects": _average(pair_scores)}


# ── Public API ────────────────────────────────────────────────────────────────

def compute_accuracy(
    reference: CandidateProfile,
    test:      CandidateProfile,
    model_name: str,
    latency_seconds: float
) -> dict:
    """
    Compare test CandidateProfile against reference CandidateProfile.

    Returns a dict with:
      - model          : str
      - latency        : float (seconds)
      - section_scores : dict  (score per section, 0.0–1.0)
      - overall_score  : float (weighted average, 0.0–1.0)
      - field_scores   : dict  (granular per-field scores)
    """
    ref_p = reference
    tst_p = test

    # --- Field-level ---
    personal_fields = _score_personal_info(
        ref_p.personal_information, tst_p.personal_information)
    skill_fields    = _score_skills(ref_p.skills, tst_p.skills)
    work_fields     = _score_work_experience(
        ref_p.work_experience, tst_p.work_experience)
    edu_fields      = _score_education(ref_p.education, tst_p.education)
    cert_fields     = _score_certifications(
        ref_p.certifications, tst_p.certifications)
    proj_fields     = _score_projects(ref_p.projects, tst_p.projects)

    all_field_scores = {
        **{f"personal_information.{k}": v for k, v in personal_fields.items()},
        **{f"skills.{k}": v              for k, v in skill_fields.items()},
        **work_fields,
        **edu_fields,
        **cert_fields,
        **proj_fields,
    }

    # --- Section-level (average of constituent field scores) ---
    section_scores = {
        "personal_information": _average(list(personal_fields.values())),
        "skills":               _average(list(skill_fields.values())),
        "work_experience":      work_fields["work_experience"],
        "education":            edu_fields["education"],
        "certifications":       cert_fields["certifications"],
        "projects":             proj_fields["projects"],
    }

    # --- Overall (simple average of section scores) ---
    overall = _average(list(section_scores.values()))

    return {
        "model":          model_name,
        "latency":        latency_seconds,
        "section_scores": section_scores,
        "overall_score":  overall,
        "field_scores":   all_field_scores,
    }
