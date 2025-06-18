import json
import os
import sys
import time
from collections import defaultdict

import pandas as pd

# CONFIGURABLE FILES
JSON_INPUT = 'RawVLLMFabricdepot.json'  # Change as needed
# Dynamically generate Excel mapping filename based on JSON input
EXCEL_MAPPING = f"mapping_{os.path.splitext(JSON_INPUT)[0]}.xlsx"
MAINLIB_JSON = 'mainlib.json'
# Dynamically generate output JSON filename based on input
JSON_OUTPUT = f"Cleaned{os.path.splitext(JSON_INPUT)[0]}.json"

# 1. Extract unique fabric_type values from the input JSON
with open(JSON_INPUT, 'r', encoding='utf-8') as f:
    data = json.load(f)

unique_fabric_types = set()
for entry in data:
    ft = entry.get('fabric_type')
    if ft and isinstance(ft, str) and ft.strip():
        unique_fabric_types.add(ft.strip().lower())  # normalize to lowercase

# 2. Load mainlib.json as a mapping dictionary (if exists)
if os.path.exists(MAINLIB_JSON):
    with open(MAINLIB_JSON, 'r', encoding='utf-8') as f:
        mainlib = json.load(f)
    # Normalize mainlib keys and values to lowercase
    mainlib = {k.lower(): [v.lower() for v in vlist] for k, vlist in mainlib.items()}
else:
    mainlib = {}

# 2.1. Load mappingLib.json for fabric name detection
MAPPINGLIB_JSON = 'mappingLib.json'
fabric_name_mapping = {}
if os.path.exists(MAPPINGLIB_JSON):
    with open(MAPPINGLIB_JSON, 'r', encoding='utf-8') as f:
        mappinglib = json.load(f)
    
    # Extract fabric names (part after underscore) and map to full fabric type
    all_fabric_types = mappinglib.get('all_fabric_types', [])
    for fabric_type in all_fabric_types:
        if '_' in fabric_type:
            fabric_name = fabric_type.split('_', 1)[1].lower()  # Get part after first underscore
            fabric_name_mapping[fabric_name] = fabric_type.lower()
    
    print(f"Loaded {len(fabric_name_mapping)} fabric name mappings from {MAPPINGLIB_JSON}")
else:
    print(f"Warning: {MAPPINGLIB_JSON} not found. Fabric name auto-mapping disabled.")
    mappinglib = {}

# 3. Prepare DataFrame for Excel mapping
rows = []
for ft in sorted(unique_fabric_types):
    # Try to auto-map using mainlib first
    combined = None
    for k, vlist in mainlib.items():
        if ft in vlist:
            combined = k
            break
    
    # If not found in mainlib, try fabric name mapping
    if not combined:
        ft_words = ft.split()  # Split fabric type into words
        for word in ft_words:
            word_clean = word.lower().strip('.,!?;:')  # Remove punctuation
            if word_clean in fabric_name_mapping:
                combined = fabric_name_mapping[word_clean]
                break
        
        # Also try checking if any fabric name is contained within the fabric type string
        if not combined:
            for fabric_name, full_type in fabric_name_mapping.items():
                if fabric_name in ft:
                    combined = full_type
                    break
    
    rows.append({'fabric_type': ft, 'combined': combined or ''})

df = pd.DataFrame(rows)

# 4. Write to Excel for manual review
print(f"Writing mapping to {EXCEL_MAPPING} ...")
df.to_excel(EXCEL_MAPPING, index=False)
print(f"Please review and update the 'combined' column in {EXCEL_MAPPING} as needed.")
input("Press Enter after you have finished editing the Excel file...")

# 5. Read the updated mapping from Excel
mapping_df = pd.read_excel(EXCEL_MAPPING)

# 6. Build mapping dict: fabric_type -> combined (all lowercase)
ft_to_combined = {str(row['fabric_type']).strip().lower(): str(row['combined']).strip().lower() for _, row in mapping_df.iterrows() if pd.notna(row['fabric_type'])}

# 7. Update mainlib.json: combined -> list of fabric_type variations (all lowercase, unique)
mainlib_dict = defaultdict(list)
new_fabric_types = set()
for _, row in mapping_df.iterrows():
    combined = str(row['combined']).strip().lower()
    fabric_type = str(row['fabric_type']).strip().lower()
    if combined and fabric_type:
        if fabric_type not in mainlib_dict[combined]:
            mainlib_dict[combined].append(fabric_type)
        # Track new fabric types that aren't in mappingLib
        if combined not in [ft.lower() for ft in mappinglib.get('all_fabric_types', [])]:
            new_fabric_types.add(combined)

# Sort the lists
mainlib_dict = {k: sorted(v) for k, v in mainlib_dict.items()}

with open(MAINLIB_JSON, 'w', encoding='utf-8') as f:
    json.dump(mainlib_dict, f, ensure_ascii=False, indent=2)
print(f"Updated {MAINLIB_JSON} with {len(mainlib_dict)} keys.")

# 7.1. Update mappingLib.json with new fabric types
if new_fabric_types and os.path.exists(MAPPINGLIB_JSON):
    print(f"Found {len(new_fabric_types)} new fabric types to add to {MAPPINGLIB_JSON}")
    
    # Separate new fabric types by category (woven/knit)
    new_woven = [ft for ft in new_fabric_types if ft.startswith('woven_')]
    new_knit = [ft for ft in new_fabric_types if ft.startswith('knit_')]
    
    # Add to existing lists
    mappinglib['fabric_types']['woven'].extend(new_woven)
    mappinglib['fabric_types']['knit'].extend(new_knit)
    mappinglib['all_fabric_types'].extend(list(new_fabric_types))
    
    # Sort all lists
    mappinglib['fabric_types']['woven'] = sorted(list(set(mappinglib['fabric_types']['woven'])))
    mappinglib['fabric_types']['knit'] = sorted(list(set(mappinglib['fabric_types']['knit'])))
    mappinglib['all_fabric_types'] = sorted(list(set(mappinglib['all_fabric_types'])))
    
    # Write updated mappingLib.json
    with open(MAPPINGLIB_JSON, 'w', encoding='utf-8') as f:
        json.dump(mappinglib, f, ensure_ascii=False, indent=2)
    
    print(f"Updated {MAPPINGLIB_JSON}:")
    if new_woven:
        print(f"  - Added {len(new_woven)} new woven types: {new_woven}")
    if new_knit:
        print(f"  - Added {len(new_knit)} new knit types: {new_knit}")
    
    other_types = [ft for ft in new_fabric_types if not ft.startswith(('woven_', 'knit_'))]
    if other_types:
        print(f"  - Warning: {len(other_types)} fabric types don't follow woven_/knit_ pattern: {other_types}")
elif new_fabric_types:
    print(f"Warning: Found {len(new_fabric_types)} new fabric types but {MAPPINGLIB_JSON} not found")

# 8. Apply mapping to the input JSON and write output (all lowercase)
for entry in data:
    ft = entry.get('fabric_type')
    ft_norm = ft.strip().lower() if isinstance(ft, str) and ft.strip() else ''
    mapped = ft_to_combined.get(ft_norm)
    if mapped:
        entry['fabric_type'] = mapped
    else:
        entry['fabric_type'] = None

with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Wrote mapped JSON to {JSON_OUTPUT}.")
