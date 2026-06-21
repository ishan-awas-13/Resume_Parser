import ollama
import json
import os

SCORER_SYSTEM_PROMPT = """
Your are expert technical recuiter and resume evaluator. 
You will handed:-
1. Job description
2. A list of key tag words that are important for the rule
3. A candidate's past resume as a structured JSON

Your job is to evaluate how suitable the candidate is for the job role.

You wll return ONLY a JSON format output in this following format:
{
    "skills_match": 1-100,
    "role_relevance": 1-100,
    "experience_match": 1-100,
    "education_match": 1-100,
    "project_match": 1-100
    "summary": "give a short explanation for the scoring"
}
"""

def score_candidate_suitability(model_name: str, job_description: str, key_skills: list[str], resume_json: dict) -> dict:
    """
    Evaluate how suitable the candidate is for the job role.
    """
    # Build the prompt
    prompt = f"""Job Description:
{job_description}

Key Skills:
{', '.join(key_skills)}

Resume JSON:
{json.dumps(resume_json, indent=2)}

Now evaluate how suitable the candidate is for the job role."""
    
    response = ollama.chat(
        model=model_name,
        messages=[
            {"role": "system", "content": SCORER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        options={"temperature": 0},
        format="json"
    )

    return json.loads(response["message"]["content"])

    