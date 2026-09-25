import json

with open('results/results.jsonl', 'r', encoding='utf-8') as f:
    records = [json.loads(line) for line in f]
with open('siis_responses.json', 'r', encoding='utf-8') as f:
    siis_raw = json.load(f)['responses']

for idx, (rec, sc) in enumerate(zip(records, siis_raw)):
    goal_obj = rec['response']['contexts'][0]
    title_words = goal_obj['title'].strip().split()
    siis_payload = sc['siis_response']
    siis_text_lower = (siis_payload['title'] + ' ' + siis_payload['content']).lower()
    title_words_lower = [w.lower() for w in title_words]
    match = any(w in siis_text_lower for w in title_words_lower) or 'device' in title_words_lower or 'troubleshooting' in title_words_lower
    if not match:
        print(f"MISMATCH at idx {idx} ({sc['id']}): title='{goal_obj['title']}', words={title_words_lower}")
        print(f"SIIS title: '{siis_payload['title']}'")
        print(f"SIIS content snippet: '{siis_payload['content'][:200]}'")
