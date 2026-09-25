"""Generate official results/results.jsonl for Samsung PRISM GenAI Hackathon.

Strictly adheres to:
- 20 canonical scenarios from siis_responses.json
- Exactly 10 diverse paraphrases per query covering question, concise, conversational,
  descriptive, technical, and casual styles
- ValidationFirewall check on all responses
- Zero URL leaks
- Preserves verbatim bixby:// catalog deeplinks
- Valid ContextDeeplinkResponse per schema.py
"""
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from app.core.firewall import ValidationFirewall
from app.core.sanitizer import has_url_leaks
from app.core.schema import ContextDeeplinkResponse, actionCategory
from app.services.deeplink_matcher import DeeplinkResolver
from app.cache.prewarm import build_canonical_plan

SIIS_PATH = WORKSPACE_ROOT / "siis_responses.json"
CATALOG_PATH = WORKSPACE_ROOT / "deeplinks.json"
RESULTS_DIR = WORKSPACE_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "results.jsonl"

# 10 genuinely diverse query variations per scenario preserving troubleshooting intent
QUERY_VARIATIONS: Dict[str, List[str]] = {
    "row_1": [
        "How do I fix my Samsung tablet screen going completely blank whenever I open Gmail?",
        "Gmail causes tablet screen to flash and turn black repeatedly.",
        "Whenever I tap to check my emails on my tablet, the display blinks and goes dark after a few seconds.",
        "Opening Gmail on my Samsung A115G makes the screen flash and turn pitch black.",
        "Need troubleshooting steps for email app crashing and blanking out my tablet screen.",
        "Display flashes and cuts out to a blank screen when loading mail server on my tablet.",
        "Why does my tablet screen turn completely dark whenever I launch the email application?",
        "My Samsung tablet display shuts off shortly after opening Gmail messages.",
        "Tablet screen keeps flashing black when trying to sync or read email.",
        "Email app display failure on Samsung A115G tablet causing black screen."
    ],
    "row_2": [
        "Why does my Galaxy S22 screen turn completely blank or white when searching stock prices or using apps?",
        "Galaxy S22 screen goes totally white or black with no text showing in apps.",
        "Every time I open Smart Tutor or check stock prices, my S22 display turns blank white.",
        "Phone screen goes completely white and stops showing text across multiple applications.",
        "How to resolve blank white screen issue on Galaxy S22 during app usage?",
        "Display turns entirely white or blank without showing any text when opening apps on Galaxy S22.",
        "My S22 display goes blank and unresponsive whenever I try using Smart Tutor or other apps.",
        "Screen suddenly turns plain white with no text appearing on my Galaxy phone.",
        "Apps on my Galaxy S22 cause the entire screen to turn blank and blank out text.",
        "Troubleshoot Galaxy S22 blank white screen bug affecting Smart Tutor and stock search."
    ],
    "row_3": [
        "How can I transfer my data from a Galaxy Z Flip 7 when the screen is completely black and unresponsive?",
        "Z Flip 7 screen went pitch black and I cannot access Smart Switch to back up my files.",
        "My Galaxy Flip 7 display is completely black; how do I recover or transfer my data without touch?",
        "Unable to see anything on my Z Flip 7 screen to transfer data with Smart Switch.",
        "Steps to back up data from a black unresponsive screen on Galaxy Z Flip 7.",
        "Galaxy Z Flip 7 screen is completely dead and won't display anything for Smart Switch transfer.",
        "Can I extract files from my Z Flip 7 if the screen went totally dark and won't respond?",
        "Screen blacked out on Galaxy Z Flip 7 preventing data migration and Smart Switch.",
        "Need a way to interact with my Flip 7 and transfer data after screen went totally black.",
        "Galaxy Z Flip 7 display failure data backup and Smart Switch recovery method."
    ],
    "row_4": [
        "My Galaxy A15 screen suddenly turned completely black on its own and won't turn on.",
        "How to fix Samsung Galaxy A15/A16 black screen of death after normal use?",
        "After about a month of use, my Galaxy A16 display went completely dark and won't power up.",
        "Galaxy A15 display is totally black and shows nothing even when holding power button.",
        "Troubleshoot sudden black screen on Samsung Galaxy A15 that doesn't display anything.",
        "Why did my brand new Galaxy A16 screen suddenly go black and stop displaying?",
        "My Galaxy A15 won't show any image on the display even though I try turning it on.",
        "Phone screen went totally blank on its own and doesn't respond to power on attempts.",
        "Samsung A16 screen turned pitch black out of nowhere and shows zero display.",
        "Force restart or fix Galaxy A15 when screen goes completely black on its own."
    ],
    "row_5": [
        "Why is my Galaxy tablet screen staying blank when scanning the Smart Switch QR code from my S25?",
        "Galaxy tablet display goes completely blank during Smart Switch QR code data transfer.",
        "Smart Switch QR transfer fails because tablet screen stays dark when trying to scan from phone.",
        "How do I transfer data from S25 to tablet when the QR scan screen stays blank?",
        "Tablet screen remains completely blank while attempting Smart Switch QR code migration.",
        "Can't proceed with Smart Switch transfer because the tablet display won't show anything during QR scan.",
        "My Samsung tablet stays on a blank screen instead of scanning Smart Switch transfer QR code.",
        "Smart Switch QR code transfer stuck on blank screen on Galaxy tablet.",
        "Fix blank screen problem on Galaxy tablet when using Smart Switch with Galaxy S25.",
        "Unable to transfer data between S25 and tablet because tablet camera/QR screen is blank."
    ],
    "row_7": [
        "My tablet screen is dark with only three app icons lit up and nothing else will open.",
        "Why are only 3 app icons showing on my dark tablet screen while other apps won't load?",
        "Tablet display stays dark and only shows three lit icons; device is unusable.",
        "How to exit multi window or restore full display when only three icons appear on dark screen?",
        "Only three icons are illuminated on my tablet screen and nothing opens when tapped.",
        "Screen locked in dark view with just 3 app shortcuts visible on Samsung tablet.",
        "My Galaxy tablet display is dark except for three app icons and I can't launch anything.",
        "Fix tablet screen showing only 3 lit icons and failing to load regular home screen.",
        "Samsung tablet interface unresponsive with darkened screen and three active icons.",
        "Display stuck showing three bright apps on a dark background on Galaxy tablet."
    ],
    "row_8": [
        "Why is my Samsung phone screen staying small and not filling the display when mirroring?",
        "How can I make my mirrored phone display expand to full screen on my Samsung TV?",
        "Phone screen remains small with large black borders during Smart View screen mirroring.",
        "My Galaxy phone display won't expand to full screen size while casting to television.",
        "Smart View screen mirroring aspect ratio issue making phone screen appear tiny on display.",
        "Why doesn't my Samsung screen mirror fill the entire monitor or TV screen?",
        "Fix small screen size during Smart View mirroring on new Samsung phone.",
        "Mirrored display stays miniaturized and doesn't expand to fill the full screen.",
        "How to change aspect ratio in Smart View so phone screen fills the TV completely?",
        "Phone display looks tiny and won't go full screen when mirroring to Samsung Smart TV."
    ],
    "row_9": [
        "Galaxy Flip 7 inner screen stopped working and shows no image while outer screen still works.",
        "How to access data on Galaxy Flip 7 when main inner display is dead but cover screen works?",
        "Inner folding display is unresponsive and blank on Flip 7 though cover screen responds fine.",
        "Inside screen on my Galaxy Flip 7 died completely; can I still navigate and save files?",
        "Troubleshoot Galaxy Flip 7 inner display failure with functional outer cover screen.",
        "Inner screen has no image and ignores touch on Galaxy Flip 7 while external screen is fine.",
        "How to back up my Flip 7 phone when the main inner screen fails to display anything?",
        "Flip 7 inner folding screen won't respond to touch or turn on, but outer screen functions.",
        "Navigate and recover phone when inside display is blank on Galaxy Z Flip 7.",
        "Connect mouse or monitor to Galaxy Flip 7 after inner screen stops working."
    ],
    "row_10": [
        "Why does my Galaxy Z Flip 6 screen flicker and turn blank every time I open it?",
        "Galaxy Z Flip 6 display flickers and blackens upon opening the fold.",
        "Whenever I unfold my Flip 6, the screen flickers violently and goes completely dark.",
        "Can't access settings or use phone because Flip 6 screen flickers and blanks when opened.",
        "How to resolve screen flickering and black screen when opening Samsung Galaxy Z Flip 6?",
        "Display flickers and cuts out to blank screen as soon as I open my Z Flip 6.",
        "My Galaxy Flip 6 screen blinks rapidly and shuts off whenever the hinge is unfolded.",
        "Screen flickering issue on Galaxy Z Flip 6 camera and folding hinge.",
        "Z Flip 6 display goes dark with flickering lines upon opening device.",
        "Fix screen flicker and black display bug on Galaxy Z Flip 6."
    ],
    "row_11": [
        "My Galaxy Flip 6 screen is half black with one side completely dark and the other working.",
        "How do I fix half of my Galaxy Flip 6 display being pitch black?",
        "One half of my Z Flip 6 screen is totally dark while the opposite side displays normally.",
        "Split blackout on Galaxy Flip 6 screen where one side works and one side is dead.",
        "Half of the folding screen on my Galaxy Flip 6 went dark; can I still navigate device?",
        "Galaxy Flip 6 display panel failure with half the screen blacked out.",
        "Why is one half of my Galaxy Z Flip 6 screen black and unresponsive?",
        "Right or left half of Flip 6 screen is black while remainder of display functions.",
        "Troubleshooting partial screen blackout on Samsung Galaxy Flip 6.",
        "Galaxy Flip 6 screen divided in half with one dark side; repair or data access steps."
    ],
    "row_12": [
        "How do I remove the floating shortcut circle that hovers on my Galaxy S25 screen?",
        "Turn off the hovering assistant menu button with shortcuts on Galaxy S25.",
        "There is a floating circle on my S25 screen with home and recent app shortcuts; how to disable it?",
        "How to get rid of the accessibility assistant menu circle on Samsung Galaxy S25?",
        "Steps to remove the floating shortcut icon that stays on top of my Galaxy phone screen.",
        "Galaxy S25 has an annoying circle floating on the display with quick tools; where is the setting?",
        "Disable floating assistant button for volume, back, and recent apps on Galaxy S25.",
        "Why is there a round shortcut widget hovering on my screen and how do I delete it?",
        "Remove floating accessibility circle widget from Galaxy S25 display.",
        "Turn off Assistant Menu in Accessibility settings to get rid of floating screen shortcut."
    ],
    "row_13": [
        "Galaxy S22 screen stays blank and shows no activation message after old phone was deactivated.",
        "Why is my Galaxy S22 display blank without any activation prompt after switching phones?",
        "Screen stays dark and won't display carrier activation screen on Samsung Galaxy S22.",
        "Switched carriers but Galaxy S22 screen is blank and shows nothing when turned on.",
        "How to activate Galaxy S22 when screen remains blank and shows no welcome or setup message?",
        "Galaxy S22 powers on to a completely blank screen after carrier line transfer.",
        "Carrier deactivated old device but new S22 display is blank with no network prompt.",
        "Fix blank display and missing carrier activation screen on Galaxy S22.",
        "Display shows nothing on Galaxy S22 after carrier activation process.",
        "Troubleshoot Galaxy S22 screen staying blank during carrier phone activation."
    ],
    "row_14": [
        "My Galaxy phone screen is completely cracked and shattered; how do I back up data and get repair?",
        "Screen is totally cracked on my Galaxy phone and display is unusable.",
        "How to handle a completely cracked Galaxy screen with bleeding display?",
        "My Samsung phone display has shattered glass and won't respond to touch; what should I do?",
        "Steps to take when Galaxy phone screen is totally cracked and unusable.",
        "Galaxy screen is badly cracked and bleeding ink; how can I save my files before service?",
        "Entire phone display is shattered; where can I get Samsung screen replacement?",
        "Can I back up my phone when the Galaxy screen is cracked all over?",
        "Cracked and shattered Galaxy screen troubleshooting and authorized repair guide.",
        "Phone screen is broken and cracked across entire surface; schedule Samsung repair."
    ],
    "row_15": [
        "My Galaxy S26 Ultra boots to a blue or black screen with tiny text and won't start up.",
        "How to fix Galaxy S26 Ultra stuck on recovery screen with tiny text and blue display?",
        "Phone won't boot past a blue screen with small writing even after holding power button.",
        "Galaxy S26 Ultra displays blue recovery screen with small system text instead of booting.",
        "Why does my Galaxy phone only show tiny text on a blue or black screen when turned on?",
        "Stuck on Android recovery mode with tiny text on Galaxy S26 Ultra; how to reboot normally?",
        "S26 Ultra shows a black or blue screen with error lines and holding power does nothing.",
        "Reboot Galaxy S26 Ultra out of recovery mode when blue screen with tiny text appears.",
        "Samsung Galaxy S26 Ultra will not start and only displays blue screen with tiny system font.",
        "Troubleshoot phone stuck in recovery boot loop with small font on blue background."
    ],
    "row_16": [
        "My Samsung S Ultra screen flashes very quickly in milliseconds whenever I plug in a charger.",
        "Why does my phone screen rapidly flash for a millisecond when connecting the charging cable?",
        "Display blinks rapidly when charger is plugged into Samsung Galaxy S Ultra.",
        "Screen flashes and flickers instantly whenever I connect my phone to the charger.",
        "How to stop screen flashing milliseconds when inserting USB charger on Samsung Ultra?",
        "Plug-in charging causes my Galaxy display to flash violently for a split second.",
        "Is it normal for Samsung S Ultra screen to flash rapidly when connected to power adapter?",
        "Display flicker occurring precisely when charging cable is attached to Galaxy device.",
        "Troubleshoot rapid screen flash when plugging charger into Samsung Galaxy phone.",
        "Charger connection triggers quick screen blinking glitch on Samsung S Ultra."
    ],
    "row_17": [
        "Galaxy S24 screen is completely blank and dark with occasional scrolling and no visible content.",
        "My S24 screen is black with rare scrolling lines; how can I use Smart Switch to transfer files?",
        "Display is totally dark with occasional scrolling artifacts on Galaxy S24.",
        "Cannot see any content on Galaxy S24 dark screen to perform Smart Switch backup.",
        "How to recover data from Galaxy S24 when screen stays dark with occasional scrolling?",
        "Galaxy S24 display shows no content, only a dark screen that scrolls occasionally.",
        "Dark screen on Galaxy S24 prevents me from interacting or transferring data via Smart Switch.",
        "Smart Switch transfer blocked by completely dark Galaxy S24 screen with occasional scroll.",
        "Troubleshoot Galaxy S24 blank dark screen with phantom scrolling.",
        "Steps to back up data from Galaxy S24 when screen is dark with scrolling glitches."
    ],
    "row_19": [
        "My Galaxy Z Flip 7 screen is cracked right at the fold and touch does not work.",
        "Flip 7 folding crease is cracked, touch is broken, and display is barely visible.",
        "How to back up files and repair Galaxy Z Flip 7 with cracked hinge fold and dead touch?",
        "Cracked crease and unresponsive touch on Galaxy Z Flip 7 folding screen.",
        "Folding area of my Z Flip 7 screen is cracked again and touch has stopped working.",
        "Can hardly see anything on my Flip 7 screen because fold is cracked and touch failed.",
        "Galaxy Z Flip 7 hinge screen crack repair and data backup procedure.",
        "Touch dead on parts of screen and crack along the fold on Galaxy Flip 7.",
        "Troubleshoot cracked fold display and broken touch digitizer on Galaxy Z Flip 7.",
        "Where can I fix my Galaxy Z Flip 7 cracked folding glass and failing touch?"
    ],
    "row_20": [
        "My Galaxy A17 screen looks distorted right after receiving it; how do I run a diagnostic test?",
        "Display appears distorted on new Galaxy A17 and I need to test the screen hardware.",
        "How to diagnose distorted screen and display orientation on brand new Galaxy A17?",
        "New Samsung Galaxy A17 display is warped or distorted; need screen diagnostic steps.",
        "Run Samsung diagnostic test for distorted screen on newly delivered Galaxy A17.",
        "Screen graphics look distorted on my fresh Galaxy A17; how to verify display health?",
        "Galaxy A17 screen distortion troubleshooting and hardware sensor diagnostic test.",
        "Why is my newly unboxed Galaxy A17 display distorted and how can I run diagnostics?",
        "Diagnostic test procedure for display distortion on Samsung Galaxy A17.",
        "Test screen alignment and display distortion on newly received Galaxy phone."
    ],
    "row_21": [
        "My Galaxy S22 screen inputs are delayed and touch responsiveness is laggy.",
        "How do I fix delayed touch input and laggy screen response on Galaxy S22?",
        "Touchscreen latency on Galaxy S22 is causing noticeable delay when tapping.",
        "Why is my Samsung Galaxy S22 touchscreen lagging and slow to respond to touch?",
        "Increase touch sensitivity or fix touch lag on Galaxy S22 display.",
        "Galaxy S22 screen touch response is sluggish with noticeable delays during interaction.",
        "Taps and swipes are delayed on my Galaxy S22 screen; how to improve responsiveness?",
        "Troubleshoot laggy and delayed touchscreen inputs on Samsung S22.",
        "My Galaxy S22 takes too long to register screen touches and gestures.",
        "Improve touch sensitivity and resolve input latency on Samsung Galaxy S22."
    ],
    "row_22": [
        "My Galaxy S24 Ultra screen is completely black and won't turn on, but the phone still rings.",
        "Phone powers on and rings but Galaxy S24 Ultra screen stays completely black.",
        "How to fix black screen on Galaxy S24 Ultra when phone is vibrating and working internally?",
        "Galaxy S24 Ultra display is dead and won't light up even though phone is turned on.",
        "Screen stays totally black on Galaxy S24 Ultra despite no physical damage and phone ringing.",
        "Why does my Galaxy S24 Ultra receive calls and power on while the screen remains black?",
        "Force restart Galaxy S24 Ultra when display won't turn on but phone is operational.",
        "Troubleshoot functional Galaxy S24 Ultra with totally black unresponsive display.",
        "Galaxy S24 Ultra black screen bug with working audio and incoming ringtones.",
        "Display won't illuminate on Galaxy S24 Ultra although device turns on with no damage."
    ]
}


def main():
    print("=" * 70)
    print("TASK 1 & TASK 2: Generating Official results/results.jsonl")
    print("=" * 70)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(SIIS_PATH, "r", encoding="utf-8") as f:
        siis_data = json.load(f)

    resolver = DeeplinkResolver(catalog_path=CATALOG_PATH)
    firewall = ValidationFirewall(catalog_path=CATALOG_PATH)

    canonical_list = siis_data["responses"]
    print(f"Loaded {len(canonical_list)} canonical scenarios from {SIIS_PATH.name}")

    results_lines = []
    total_variations = 0
    all_variations_set = set()

    for idx, sc in enumerate(canonical_list):
        sc_id = sc["id"]
        orig_query = sc["original_query"]
        variations = QUERY_VARIATIONS.get(sc_id, [])

        # Verification 1: Exactly 8-10 variations
        assert 8 <= len(variations) <= 10, f"Scenario {sc_id} has {len(variations)} variations (expected 8-10)"

        # Verification 2: No duplicates within scenario
        var_set = set(variations)
        assert len(var_set) == len(variations), f"Scenario {sc_id} contains duplicate variations!"

        # Verification 3: No global duplicates
        for v in variations:
            assert v not in all_variations_set, f"Duplicate variation found across scenarios: '{v}'"
            all_variations_set.add(v)
            # Verification 4: Zero URL leaks in variations
            assert not has_url_leaks(v), f"URL leak detected in variation: '{v}'"

        total_variations += len(variations)

        # Generate actual ContextDeeplinkResponse via pipeline
        plan = build_canonical_plan(sc, resolver, firewall)
        validated_plan, errors = firewall.validate_response(plan, allow_repair=True)
        assert len(errors) == 0, f"Firewall validation failed on {sc_id}: {errors}"

        # Schema & firewall assertions
        assert isinstance(validated_plan, ContextDeeplinkResponse)
        assert len(validated_plan.contexts) == 1
        goal = validated_plan.contexts[0]
        assert len(goal.actions) >= 1
        assert 0.0 <= goal.score <= 1.0

        for action in goal.actions:
            words = action.description.strip().split()
            assert 5 <= len(words) <= 7, f"Action description '{action.description}' word count is {len(words)}"
            assert action.description.startswith("It will"), f"Action desc '{action.description}' does not start with 'It will'"
            if action.category == actionCategory.auto:
                for sg in action.stepGroups:
                    assert sg.actionableDeeplink is not None, f"Auto action missing actionableDeeplink in {sc_id}"
                    assert sg.actionableDeeplink.deeplink.startswith("bixby://"), f"Invalid deeplink in {sc_id}"

        # Zero URL leaks in final response
        resp_json_str = validated_plan.model_dump_json()
        assert not has_url_leaks(resp_json_str), f"URL leak in response for {sc_id}"

        line_record = {
            "query": orig_query,
            "query_variations": variations,
            "response": validated_plan.model_dump(by_alias=True)
        }
        results_lines.append(line_record)

    # Write out results/results.jsonl
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        for record in results_lines:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nSuccessfully written {len(results_lines)} lines to {RESULTS_FILE}")
    print(f"Total canonical scenarios: {len(results_lines)}")
    print(f"Total query variations: {total_variations} (exact average: {total_variations/len(results_lines):.1f} per scenario)")
    print(f"Global duplicate check: 0 duplicates across {len(all_variations_set)} unique queries")
    print(f"Firewall validation: 100% PASS ({len(results_lines)}/{len(results_lines)})")
    print(f"URL leak scan on results.jsonl: 0 leaks detected")
    print("=" * 70)


if __name__ == "__main__":
    main()
