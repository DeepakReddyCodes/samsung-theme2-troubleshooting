import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cache.prewarm import SCENARIO_METADATA

with open('siis_responses.json', 'r', encoding='utf-8') as f:
    siis_raw = json.load(f)['responses']

print("Validating all 20 scenarios in SCENARIO_METADATA against SIIS articles:")
for sc in siis_raw:
    sc_id = sc['id']
    meta = SCENARIO_METADATA.get(sc_id)
    if not meta:
        print(f"[MISSING] {sc_id}")
        continue
    siis = sc['siis_response']
    siis_text = (siis['title'] + " " + siis['content']).lower()
    
    # Check title, action_name, and steps
    title_words = [w.lower() for w in meta['title'].split()]
    title_match = any(w in siis_text for w in title_words)
    
    # Check step grounding
    steps_grounded = all(any(token.lower() in siis_text for token in step.split() if len(token) > 4) for step in meta['steps'])
    
    print(f"[{sc_id}] title='{meta['title']}' | Title Grounded: {title_match} | Steps Grounded: {steps_grounded}")
