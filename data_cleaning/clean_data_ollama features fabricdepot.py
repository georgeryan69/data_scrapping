import pandas as pd
import openai  # for Ollama chat client
import json
import os
import ast

# Ollama-compatible OpenAI client
client = openai.OpenAI(
    api_key="ollama",  # dummy token for local usage
    base_url="http://192.168.7.54:11434/v1"
)

def call_ollama_chat(description, model="qwen3:14b"):
    user_prompt = f"""You are a textile domain expert and data cleaner.

You will receive unstructured fabric product data that includes a title, URL, technical description block, and image URLs.

Your task is to extract and standardize the following fields:

1. `material`: the fiber content (e.g., "100% Rayon"). Use the exact phrase from the text.
2. `fabric_type`: the fabric type based on title and description (e.g., "tribal print rayon challis").
3. `gsm`: the weight in grams per square meter as an integer (e.g., 195). Return null if not found.
4. `end_use`: list of applications (e.g., ["blouses", "dresses"]).
5. `features`: list of sensory or physical attributes (e.g., ["soft", "opaque"]).

Respond ONLY in this JSON format:
{{
  "material": "...",
  "fabric_type": "...",
  "gsm": 195,
  "end_use": ["...", "..."],
  "features": ["...", "..."]
}}

Text:
\"\"\"{description}\"\"\"

/no_think
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a fabric analysis assistant that returns structured data only in JSON."},
                {"role": "user", "content": user_prompt}
            ]
        )

        content = response.choices[0].message.content
        json_start = content.find("{")
        if json_start != -1:
            return json.loads(content[json_start:])
    except Exception as e:
        print(f"❌ Qwen API error: {e}")

    return {
        "material": None,
        "fabric_type": None,
        "gsm": None,
        "end_use": [],
        "features": []
    }

def call_ollama_question_suggestion_extended(fabric_metadata, model="qwen3:14b"):
    user_prompt = f"""You are a creative assistant helping fabric shoppers understand fabric characteristics.

From the metadata below, generate 10 question-and-answer (Q&A) pairs in English.

Each question should be a realistic user query that might lead to selecting this fabric.
Each answer should:
- Avoid copying terms directly (e.g., instead of "soft", say "gentle on the skin")
- Describe how the fabric feels, behaves, or could be used — naturally and creatively
- Be helpful, informative, and approachable
- Include everyday examples like summer tops, comfy dresses, cool nights, lounging, layering, etc.

Do NOT include numeric specs like GSM or fiber percentages.

Return a list like this:
[
  {{ "question": "...", "answer": "..." }},
  ...
]

Metadata:
{json.dumps(fabric_metadata, indent=2)}

/no_think
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You generate user questions from structured fabric metadata."},
                {"role": "user", "content": user_prompt}
            ]
        )
        content = response.choices[0].message.content
        json_start = content.find("[")
        if json_start != -1:
            return json.loads(content[json_start:])
    except Exception as e:
        print(f"❌ Question generation error: {e}")

    return []

# File paths
input_file = "fabricdepot_cleaned.csv"
output_file = "qwen3_fabricdepotExport_final.json"

# Load or initialize
if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)
    done_descriptions = set(item["description"] for item in output_data)
    print(f"Resuming from {len(output_data)} already processed.")
else:
    output_data = []
    done_descriptions = set()

# Load CSV
df = pd.read_csv(input_file)

for idx, row in df.iterrows():
    desc = str(row["Description"])
    if desc in done_descriptions:
        print(f"⏩ Fabric {idx + 1}/{len(df)} skipped.")
        continue

    print(f"🔄 Processing fabric {idx + 1}/{len(df)}...")

    details = row.get("Details", "")
    details_dict = {}
    if details and isinstance(details, str):
        try:
            details_dict = ast.literal_eval(details)
        except Exception as e:
            print(f"⚠️ Details parse failed on row {idx}: {e}")

    # Step 1: LLM metadata extraction
    ollama_info = call_ollama_chat(desc)
    material = details_dict.get("Material") or ollama_info.get("material")
    fabric_type = details_dict.get("Fabric Type") or ollama_info.get("fabric_type")
    gsm = ollama_info.get("gsm")
    end_use = ollama_info.get("end_use", [])
    features = ollama_info.get("features", [])

    # Step 2: Fallback GSM handling
    if gsm is None:
        industry_weight = details_dict.get("Weight", "")
        if isinstance(industry_weight, str):
            gsm_digits = ''.join(filter(str.isdigit, industry_weight))
            if gsm_digits:
                gsm = int(gsm_digits)

    # Step 3: Fallback to weight descriptor from description text
    if gsm is None:
        weight_words = ["lightweight", "light", "medium", "midweight", "heavy", "heavyweight"]
        lower_desc = desc.lower()
        for word in weight_words:
            if word in lower_desc:
                gsm = word
                break

    metadata = {
        "description": desc,
        "material": material,
        "fabric_type": fabric_type,
        "gsm": gsm,
        "end_use": end_use,
        "features": features
    }

    questions = call_ollama_question_suggestion_extended(metadata)
    metadata["questions"] = questions
    output_data.append(metadata)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Fabric {idx + 1}/{len(df)} processed.")

print("✅ All fabrics completed.")
