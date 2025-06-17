import pandas as pd
import openai # type: ignore
import json
import time

# === 1. Connect to OpenAI GPT-4 Turbo ===
client = openai.OpenAI(api_key="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")  # Replace with your real OpenAI API key

# === 2. Fabric info extraction prompt using GPT-4 Turbo ===
def call_openai_chat(description, model="gpt-4-turbo"):
    user_prompt = f"""
Extract the following fields from the fabric description:

1. content — the fiber composition (e.g., 89% Cotton, 11% Spandex)
2. fabric_type — describe the fabric type based on keywords in the text (e.g., stretch cotton jersey)
3. end_use — a list of clothing or application types the fabric is suitable for (e.g., [\"shirts\", \"dresses\"])

If the content is not mentioned, return \"Unknown\" for the content field.

Respond ONLY in this strict JSON format (no explanation, no markdown, no extra text):
{{
"content": "...",
"fabric_type": "...",
"end_use": ["...", "..."]
}}

Text: {description}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a fabric analysis assistant that returns structured data only in JSON. Do not explain your answer. Do not include any extra text. Respond only with valid JSON."
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content
        json_start = content.find("{")
        if json_start != -1:
            json_block = content[json_start:]
            return json.loads(json_block)

    except Exception as e:
        print(f"\u274c OpenAI API error: {e}")
    return {
        "content": None,
        "fabric_type": None,
        "end_use": []
    }

# === 3. Load Excel file ===
input_file = "main_lib_scrap.xlsx"
text_column = "Description"
df = pd.read_excel(input_file)
#df = df[0:4]

# === 4. Extract info and format as list of dicts with progress ===
output_data = []
total_rows = len(df)

for idx, desc in enumerate(df[text_column].astype(str), start=1):
    print(f"\U0001f501 [{idx}/{total_rows}] Processing description...")
    info = call_openai_chat(desc)
    output_data.append({
        "description": desc,
        "content": info.get("content"),
        "fabric_type": info.get("fabric_type"),
        "end_use": info.get("end_use")
    })
    print(f"\u2705 [{idx}/{total_rows}] Done: {info.get('fabric_type')}\n")
    time.sleep(0.5)  # optional: delay to avoid rate limit (adjust as needed)

# === 5. Save to JSON ===
output_file = "fabric_extraction_openai_output.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print(f"\U0001f389 All done! JSON saved to: {output_file}")
