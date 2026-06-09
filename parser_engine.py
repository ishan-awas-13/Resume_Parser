import ollama
import json
import os
from schema import ResumeParserResponse

# Load the target JSON schema structure to guide the LLM
current_dir = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(current_dir, "JSON_Scheme.json")

try:
    with open(schema_path, "r") as f:
        schema_template = f.read()
except Exception as e:
    schema_template = "{}"

SYSTEM_PROMPT = f"""Your are A precise deterministic AI data extraction engine. Your sole task is to analyze the unstructured resume provided by the user and extract candidate information into a strictly structured format matching this JSON schema:

{schema_template}

Rules:
1. Output only a valid raw JSON object matching the exact structure above. Do not include any Markdown fences (like ```json), Introduction or any conversational filler text.
2. All extracted text must strictly adhere to the schema. Do not add extra information.
3. If a field cannot be determined with certainty, return null (for objects) or an empty list (for arrays).
4. Date formats should be normalized as YYYY-MM-DD.
5. GPA must be a floating-point number.
6. Do not invent, infer, or guess data not explicitly present in the resume.
7. Keep keys exactly matching the requested schema attributes.
"""

def parse_resume_text(raw_text: str) -> ResumeParserResponse:
    #Step 3: LLM Structuring via Ollama is done here
    response = ollama.chat(
        model = "mistral:7b",
        messages = [
            {'role' : 'system', 'content' : SYSTEM_PROMPT},
            {'role' : 'user', 'content' : f"Please extract the following resume: \n{raw_text}"}
        ],
        options = {
            'temperature' : 0
        },
        format = "json"
    )

    raw_json_str = response['message']['content']

    try:
        validated_data = ResumeParserResponse.model_validate_json(raw_json_str)
        return validated_data
    except Exception as e:
        #fallback tracking here in case JSON struct is missing elements
        print(f"Validation failed due to {e}")
        print(f"Raw model response: {raw_json_str}")
        raise ValueError(f"Failed to validate JSON: {e}")

    