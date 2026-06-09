import ollama
import json
import os
from schema import ResumeParserResponse

# ── Step A: Derive the exact JSON Schema from Pydantic (snake_case guaranteed) ──
PYDANTIC_SCHEMA = ResumeParserResponse.model_json_schema()

# ── Step B: Load the human-readable example template for the prompt ──
current_dir = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(current_dir, "JSON_Scheme.json")

try:
    with open(schema_path, "r") as f:
        example_template = f.read()
except Exception:
    example_template = json.dumps({"candidate_profile": {}}, indent=2)

# ── Step C: Build the system prompt with explicit field names ──
SYSTEM_PROMPT = f"""You are a precise, deterministic AI data extraction engine.
Your ONLY task is to extract candidate information from an unstructured resume into
a strictly structured JSON object.

## REQUIRED OUTPUT STRUCTURE (follow this example exactly, including key names):
{example_template}

## STRICT RULES:
1. Output ONLY a valid raw JSON object. No markdown fences, no explanations, no extra text.
2. ALL JSON keys MUST use snake_case exactly as shown above (e.g., "first_name" NOT "firstName").
3. The top-level key MUST be "candidate_profile".
4. If a field cannot be found in the resume, use null for string fields and [] for list fields.
5. Date formats: use the format found in the resume (e.g., "2024-06" or "June 2024").
6. Do NOT invent, infer, or guess any data not explicitly present in the resume.
7. Do NOT add any fields not present in the schema above.
"""

def parse_resume_text(raw_text: str) -> ResumeParserResponse:
    """
    Extract structured data from raw resume text via Ollama/Mistral-7B.
    Uses Pydantic JSON Schema as the Ollama `format` argument to enforce output structure.
    """
    response = ollama.chat(
        model="mistral:7b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract the following resume:\n\n{raw_text}"}
        ],
        options={"temperature": 0},
        format=PYDANTIC_SCHEMA   # Ollama enforces this schema on the model output
    )

    raw_json_str = response["message"]["content"]

    try:
        validated_data = ResumeParserResponse.model_validate_json(raw_json_str)
        return validated_data
    except Exception as e:
        # Log the raw response to terminal so we can see what the model produced
        print(f"\n[PARSER ERROR] Pydantic validation failed: {e}")
        print(f"[RAW MODEL OUTPUT]:\n{raw_json_str}\n")
        raise ValueError(f"Failed to validate JSON: {e}")