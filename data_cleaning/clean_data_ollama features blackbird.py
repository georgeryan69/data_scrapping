import pandas as pd
import openai  # type: ignore
import json
import os
import ast

# Ollama client setup
client = openai.OpenAI(
    api_key="ollama",  # dummy placeholder for local Ollama
    base_url="http://192.168.7.54:11434/v1"
)

def call_ollama_chat(description, model="qwen3:14b"):
    user_prompt = f"""You are a textile domain expert.

Extract the following fields from the fabric description:

1. `material`: the fiber composition (e.g., "89% Cotton, 11% Spandex"). Use exact match from the input if available.
2. `fabric_type`: describe the fabric type based on keywords in the product title (assume it's provided at the start of the description). Example: "stretch cotton jersey".
3. `end_use`: a list of clothing or home applications the fabric is suitable for. Example: ["shirts", "dresses", "tablecloths"].
4. `features`: a list of sensory-describable features (based on sight, touch, feel, etc.) like ["airy", "soft", "wrinkle-prone", "textured", "drapey"].

Respond ONLY in this JSON format:
{{
  "material": "...",
  "fabric_type": "...",
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
            json_block = content[json_start:]
            return json.loads(json_block)
    except Exception as e:
        print(f"❌ Qwen API error: {e}")

    return {
        "material": None,
        "fabric_type": None,
        "end_use": [],
        "features": []
    }

def call_ollama_question_suggestion_extended(fabric_metadata, model="qwen3:14b"):
    user_prompt = f"""You are a helpful assistant.

You are given structured metadata for a textile fabric. Your task is to generate 10 user-style questions that could lead to selecting this fabric.

Generate:
- At least 2 questions using Style 1: Need or Use Case (e.g., "I need a breathable fabric for summer shirts.")
- At least 2 questions using Style 2: Sensory Descriptions (e.g., "I'm looking for something soft and slightly glossy.")
- At least 2 questions using Style 3: Material-based Queries (e.g., "Do you have anything in 100% cotton suitable for dresses?")
- At least 4 questions using Style 4: Open-Ended Product Descriptions (e.g., "A lightweight cotton satin ideal for bedding and shirts.")

Given the following fabric metadata:
{json.dumps(fabric_metadata, indent=2)}

Return ONLY the questions in a JSON list.

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
input_file = "blackbirdExport_20250602_114652.csv"
output_file = "qwen3_blackbirdExport_features_questions_test.json"

# Load or initialize output data
if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)
    done_descriptions = set(item["description"] for item in output_data)
    print(f"Resuming: {len(output_data)} descriptions already processed.")
else:
    output_data = []
    done_descriptions = set()

# Load input CSV
df = pd.read_csv(input_file)

# Iterate over descriptions
for idx, row in df.iterrows():
    desc = str(row["Description"])
    if desc in done_descriptions:
        print(f"⏩ Progress: Fabric {idx + 1}/{len(df)} - Skipping already processed.")
        continue

    print(f"🔄 Progress: Fabric {idx + 1}/{len(df)} - Processing...")

    # Parse Details column if available
    details = row.get("Details", "")
    details_dict = {}
    gsm = None
    material = None
    fabric_type = None

    if details and isinstance(details, str):
        try:
            details_dict = ast.literal_eval(details)
        except Exception as e:
            print(f"⚠️ Could not parse Details for row {idx}: {e}")

    # Extract GSM
    industry_weight = details_dict.get("Weight", "")
    if industry_weight:
        try:
            # Take only the portion before "/" if it exists
            gsm_part = industry_weight.split("/")[0].strip()

            # Handle range format like "293-306gsm"
            if "-" in gsm_part:
                gsm_part = gsm_part.split("-")[0].strip()

            # Extract leading digits from something like "198gsm" or "293gsm"
            gsm_digits = ''.join(filter(str.isdigit, gsm_part))
            gsm = int(gsm_digits) if gsm_digits else None
        except Exception as e:
            print(f"⚠️ Could not extract GSM for row {idx}: {e}")



    # Extract material: prefer "Material", fallback to first line of "Content"
    material = details_dict.get("Material", None)
    if not material:
        content_str = details_dict.get("Content", "")
        if isinstance(content_str, str):
            material = content_str.split("\n")[0].strip()

    # Extract fabric_type from Details
    fabric_type = details_dict.get("Fabric Type", None)

    # Call Ollama for missing metadata
    ollama_info = call_ollama_chat(desc)

    if not material:
        material = ollama_info.get("material")
    if not fabric_type:
        fabric_type = ollama_info.get("fabric_type")

    end_use = ollama_info.get("end_use", [])
    features = ollama_info.get("features", [])

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

    # Append full data to output
    output_data.append(metadata)

    # Save after each row
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Progress: Fabric {idx + 1}/{len(df)} - Done")

print("✅ All done!")
