import pandas as pd
import openai  # type: ignore
import json
import os
import ast

# Ollama client setup
client = openai.OpenAI(
    api_key="ollama",
    base_url="http://192.168.7.54:11434/v1"
)

def call_ollama_chat(description, model="qwen3:14b"):
    user_prompt = f"""You are a textile domain expert.

Extract the following fields from the fabric description:

1. `material`: the fiber composition
2. `fabric_type`: inferred from product title
3. `end_use`: what this fabric can be used to make
4. `features`: how the fabric feels/looks (e.g. soft, stretchy)

Respond in this JSON format:
{{
  "material": "...",
  "fabric_type": "...",
  "end_use": ["..."],
  "features": ["..."]
}}

Text:
\"\"\"{description}\"\"\"

/no_think
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You return structured JSON for fabric metadata."},
                {"role": "user", "content": user_prompt}
            ]
        )
        content = response.choices[0].message.content
        return json.loads(content[content.find("{"):])
    except Exception as e:
        print(f"❌ Metadata error: {e}")
        return {
            "material": None,
            "fabric_type": None,
            "end_use": [],
            "features": []
        }

def call_ollama_question_suggestion_extended(fabric_metadata, model="qwen3:14b"):
    user_prompt = f"""You are a helpful assistant that creates natural question-and-answer pairs for fabric shoppers.

From the metadata below, generate 10 Q&A pairs in English and also include Traditional Chinese versions.

Each answer should:
- Be inspired by the metadata
- NOT copy terms like "soft", "lightweight", or "breathable" directly
- Rephrase naturally: e.g., "soft" → "gentle on the skin", "smooth for everyday comfort"
- Add lifestyle context: suitable for warm weather, lounging, layering, etc.
- Avoid technical terms like GSM or fiber percentages

Respond in this JSON format:
[
  {{
    "question": "...",
    "answer": "...",
    "question_zh": "...",
    "answer_zh": "..."
  }},
  ...
]

Here is the fabric metadata:
{json.dumps(fabric_metadata, indent=2)}

/no_think
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You generate conversational, lifestyle-oriented bilingual Q&A pairs from fabric metadata."},
                {"role": "user", "content": user_prompt}
            ]
        )
        content = response.choices[0].message.content
        return json.loads(content[content.find("["):])
    except Exception as e:
        print(f"❌ Q&A generation error: {e}")
        return []

def infer_tags_from_metadata(features, end_use):
    tags = {
        "season": set(),
        "use_case": set(),
        "occasion": set()
    }

    if any(f in features for f in ["breathable", "lightweight", "airy"]):
        tags["season"].add("summer")
    if any(f in features for f in ["cozy", "thick", "warm"]):
        tags["season"].add("winter")
    if not tags["season"]:
        tags["season"].add("year-round")

    for use in end_use:
        u = use.lower()
        if any(w in u for w in ["shirt", "blouse", "t-shirt", "pants", "leggings"]):
            tags["use_case"].add("casual")
        if any(w in u for w in ["underwear", "pajama", "leggings", "lounge"]):
            tags["use_case"].add("loungewear")
        if any(w in u for w in ["curtain", "bedding", "furnishing"]):
            tags["use_case"].add("home textile")
        if any(w in u for w in ["dress", "skirt", "gown"]):
            tags["use_case"].add("formal")

    for use in end_use:
        u = use.lower()
        if "wedding" in u:
            tags["occasion"].add("wedding")
        if "party" in u:
            tags["occasion"].add("party")
        if "work" in u or "office" in u:
            tags["occasion"].add("workwear")
        if any(w in u for w in ["shirt", "casual", "blouse"]):
            tags["occasion"].add("daily")

    return {
        "season": sorted(tags["season"]),
        "use_case": sorted(tags["use_case"]),
        "occasion": sorted(tags["occasion"])
    }

# File paths
input_file = "moodFabricsFinalCombined.csv"
output_file = "qwen3_moodFabricsFinalquestasdasdasdion.json"

if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)
    done_descriptions = set(item["description"] for item in output_data)
    print(f"Resuming from {len(output_data)} processed fabrics.")
else:
    output_data = []
    done_descriptions = set()

df = pd.read_csv(input_file)

for idx, row in df.iterrows():
    desc = str(row["Description"])
    if desc in done_descriptions:
        print(f"⏩ Skipping Fabric {idx + 1}/{len(df)}")
        continue

    print(f"🔄 Processing Fabric {idx + 1}/{len(df)}...")

    details = row.get("Details", "")
    details_dict = {}
    gsm = None
    material = None
    fabric_type = None

    if details and isinstance(details, str):
        try:
            details_dict = ast.literal_eval(details)
        except Exception as e:
            print(f"⚠️ Details parse error: {e}")

    # Preserve your GSM parsing logic
    weight_str = details_dict.get("Industry Weight", "")
    if weight_str:
        try:
            gsm_digits = ''.join(filter(str.isdigit, weight_str))
            gsm = int(gsm_digits) if gsm_digits else None
        except Exception as e:
            print(f"⚠️ GSM error: {e}")

    material = details_dict.get("Material", None)
    if not material:
        content_str = details_dict.get("Content", "")
        if isinstance(content_str, str):
            material = content_str.split("\n")[0].strip()

    fabric_type = details_dict.get("Fabric Type", None)

    ai_info = call_ollama_chat(desc)
    material = material or ai_info.get("material")
    fabric_type = fabric_type or ai_info.get("fabric_type")
    end_use = ai_info.get("end_use", [])
    features = ai_info.get("features", [])

    tags = infer_tags_from_metadata(features, end_use)

    qa_pairs = call_ollama_question_suggestion_extended({
        "description": desc,
        "material": material,
        "fabric_type": fabric_type,
        "end_use": end_use,
        "features": features
    })

    metadata = {
        "description": desc,
        "material": material,
        "fabric_type": fabric_type,
        "gsm": gsm,
        "end_use": end_use,
        "features": features,
        "season": tags["season"],
        "use_case": tags["use_case"],
        "occasion": tags["occasion"],
        "qa_pairs": qa_pairs
    }

    output_data.append(metadata)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Done Fabric {idx + 1}/{len(df)}")

print("🎉 All done!")
