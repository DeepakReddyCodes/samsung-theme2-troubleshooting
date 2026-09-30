import json
from pathlib import Path

siis_path = Path(r"C:\Users\deepa\Samsung_antigravity_new\samsung-theme2-troubleshooting\codebase\siis_responses.json")
ts_path = Path(r"C:\Users\deepa\Samsung_antigravity_new\samsung-theme2-troubleshooting\codebase\frontend\src\data\canonical_scenarios.ts")

with open(siis_path, "r", encoding="utf-8") as f:
    data = json.load(f)

scenarios = []
for r in data.get("responses", []):
    orig = r["original_query"]
    summary = orig[:100] + "..." if len(orig) > 100 else orig
    title = r["siis_response"]["title"]
    sc_id = r["id"].upper()
    label = f"{sc_id}: {title[:50]}"
    scenarios.append({
        "id": r["id"],
        "label": label,
        "original_query": orig,
        "siis_response": r["siis_response"],
        "summary": summary,
    })

ts_content = """import { CanonicalScenario } from "../types";

export const CANONICAL_SCENARIOS: CanonicalScenario[] = """ + json.dumps(scenarios, indent=2) + """;

export const SAMPLE_PARAPHRASES: Record<string, string[]> = {
  row_1: [
    "Display flashes and goes dark when opening Gmail app on tablet.",
    "Gmail causes my tablet screen to go completely blank repeatedly.",
    "Why does my tablet screen turn pitch black when opening emails?",
  ],
  row_2: [
    "My phone screen turns blank or white with no text in apps.",
    "Screen is totally blank white when using Quick Assist or stock app.",
    "Why is my phone display showing only a blank white screen?",
  ],
  row_3: [
    "Fold phone inner screen is completely black, need to backup files.",
    "Can't see display on Fold phone to use Data Transfer for transfer.",
    "How to recover data when Fold screen is black and touch is dead?",
  ],
  row_5: [
    "Data Transfer QR code scan screen stays completely blank.",
    "Tablet screen is blank during Data Transfer transfer with phone.",
    "Unable to scan Data Transfer QR code because display is blank.",
  ],
  row_7: [
    "Tablet screen stays dark with only three app icons lit up.",
    "Only three icons appear on dark tablet screen, nothing else opens.",
    "How to fix dark screen displaying only three application icons?",
  ],
  row_8: [
    "Main screen on phone stays small and doesn't expand to full display.",
    "Why is my display minimized and won't go full screen on TV?",
    "Mirrored phone screen stays tiny with large borders on display.",
  ],
  row_10: [
    "Phone screen flickers and turns blank whenever I open the camera.",
    "Camera display flickers rapidly and goes black when opened.",
    "Why does my phone screen flicker and black out in camera app?",
  ],
  row_12: [
    "How to remove the floating shortcut circle hovering on my screen?",
    "Disable floating assistant menu button on phone screen.",
    "Remove circular shortcut icon that stays on top of display.",
  ],
  row_14: [
    "My phone screen is completely cracked and display is broken.",
    "Phone glass is shattered and unusable, how to schedule repair?",
    "Screen is totally cracked with bleeding display, need service.",
  ],
  row_20: [
    "Phone screen won't rotate automatically when turned sideways.",
    "Auto rotate is not working on phone display.",
    "How to fix screen rotation stuck in portrait orientation?",
  ],
  row_21: [
    "Touch screen is laggy and has noticeable input delay.",
    "Display touch responsiveness is slow and delayed on phone.",
    "How to improve touchscreen responsiveness and reduce lag?",
  ],
  row_22: [
    "Phone powers on and rings but display stays completely black.",
    "Screen won't turn on even though phone is ringing and working.",
    "How to fix black screen on phone that is on and making sounds?",
  ],
};
"""

with open(ts_path, "w", encoding="utf-8") as f:
    f.write(ts_content)

print("Updated canonical_scenarios.ts successfully!")
