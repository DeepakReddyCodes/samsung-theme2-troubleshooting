import json

with open('siis_responses.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total count: {len(data['responses'])}")
for idx, sc in enumerate(data['responses']):
    print(f"\n--- SCENARIO {idx+1} ({sc['id']}) ---")
    print(f"QUERY: {sc['original_query']}")
    print(f"TITLE: {sc['siis_response']['title']}")
