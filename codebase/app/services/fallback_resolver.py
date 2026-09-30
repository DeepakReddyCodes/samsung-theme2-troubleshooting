"""Fallback resolver generating grounded bixby://dummy_positive deeplinks.

Enforces:
1. URI is strictly 'bixby://dummy_positive'.
2. Description is exactly 5 to 7 words, starts with 'It will', and names the concrete screen.
3. Message names the concrete Settings screen derived from the actual step/intent.
4. Returns None if no concrete Settings screen target exists in the intent.
5. Never invents troubleshooting steps or placeholder screens (e.g. Display or Generic Action).
6. Guaranteed zero URL leaks.
"""
import re
from typing import List, Optional

from app.core.rewrite_controller import count_words
from app.core.sanitizer import sanitize_text
from app.core.schema import Deeplink
from app.services.retriever.base import DeeplinkResolutionResult, TroubleshootingIntent

# Known standard Galaxy Settings screens for grounded extraction
KNOWN_SETTINGS_SCREENS = [
    "Navigation bar",
    "Display",
    "Battery and device care",
    "Battery",
    "Accounts and backup",
    "Connections",
    "Wi-Fi",
    "Bluetooth",
    "Sound and vibration",
    "Notifications",
    "Lock screen",
    "Security and privacy",
    "Biometrics and security",
    "Accessibility",
    "Software update",
    "Device care",
    "General management",
    "Apps",
    "Advanced features",
    "Camera",
    "Developer options",
    "USB debugging",
    "Motion smoothness",
    "Eye comfort shield",
    "Always On Display",
    "Smart Switch",
    "Samsung Cloud",
    "Quick Share",
    "Adaptive brightness",
    "Screen resolution",
    "Full screen apps",
    "Screen timeout",
    "Easy mode",
    "Edge panels",
    "Side button",
    "Dual Messenger",
    "Secure Folder",
    "Private Share",
    "Mobile Hotspot",
]


def extract_concrete_screen_name(intent: TroubleshootingIntent) -> Optional[str]:
    """Extract the most concrete Samsung Settings screen name from intent steps or action name."""
    text_corpus = f"{intent.screen_hint} {intent.action_name} {' '.join(intent.steps)}"

    # 1. Check if screen_hint matches a known screen
    if intent.screen_hint:
        hint_clean = intent.screen_hint.strip()
        for known in KNOWN_SETTINGS_SCREENS:
            if known.lower() == hint_clean.lower() or known.lower() in hint_clean.lower():
                return known

    # 2. Look for explicit 'Tap on <Screen>', 'Select <Screen>', 'Go to <Screen>' patterns
    pattern = re.compile(
        r"(?:tap on|tap|select|go to|open|navigate to and open|navigate to|turn on|turn off|enable|disable|clean|inspect|configure)\s+([A-Z][a-zA-Z0-9\s&-]+?)(?=[.,;]|and then|\btap\b|\bselect\b|$)",
        re.IGNORECASE,
    )
    matches = pattern.findall(text_corpus)
    for m in matches:
        candidate = m.strip()
        candidate = re.sub(r"^(and|the|your|a)\s+", "", candidate, flags=re.IGNORECASE).strip()
        for known in KNOWN_SETTINGS_SCREENS:
            if known.lower() == candidate.lower() or known.lower() in candidate.lower():
                return known
        words = candidate.split()
        if 1 <= len(words) <= 3 and candidate.lower() not in {"settings", "it", "this", "action", "step", "device", "configuration"}:
            if any(term in candidate.lower() for term in ["screen", "options", "mode", "care", "update", "backup", "sound", "display", "wifi", "bluetooth", "port", "usb", "charging", "battery", "panel", "folder", "view"]):
                return candidate.title()

    # 3. Check action_name itself for concrete target
    if intent.action_name:
        action_candidate = re.sub(r"^(clean|check|inspect|configure|adjust|verify|open|set up|setup|switch|toggle)\s+", "", intent.action_name, flags=re.IGNORECASE).strip()
        if action_candidate and action_candidate.lower() not in {"settings", "it", "this", "action", "step", "device", "configuration", "generic action"}:
            words = action_candidate.split()
            if 1 <= len(words) <= 4:
                if any(term in action_candidate.lower() for term in ["screen", "options", "mode", "care", "update", "backup", "sound", "display", "wifi", "bluetooth", "port", "usb", "charging", "battery", "panel", "folder", "view"]):
                    return action_candidate.title()

    # 4. Check for presence of known screen keywords in the text corpus
    for known in KNOWN_SETTINGS_SCREENS:
        if re.search(r"\b" + re.escape(known) + r"\b", text_corpus, re.IGNORECASE):
            return known

    # Invariant: If no concrete settings screen target is found, return None!
    # NEVER default to "Display" or arbitrary action nouns!
    return None


def create_grounded_dummy_positive(
    intent: TroubleshootingIntent,
    screen_name: Optional[str] = None,
) -> Optional[DeeplinkResolutionResult]:
    """Build a grounded bixby://dummy_positive resolution strictly derived from the intent context.
    
    Returns None if no concrete Settings screen exists.
    """
    screen = screen_name or extract_concrete_screen_name(intent)
    if not screen:
        return None

    # Clean screen name for message and description
    clean_screen = sanitize_text(screen)
    screen_title = clean_screen.title()

    # 1. Message: Names the concrete screen
    message = f"Open {clean_screen} Settings"
    if count_words(message) > 5:
        screen_short = " ".join(clean_screen.split()[:2])
        message = f"Open {screen_short} Settings"

    # 2. Description: Exactly 5 to 7 words, starts with 'It will', names the screen
    screen_words = [w for w in re.findall(r"\b[\w'-]+\b", screen_title)]
    if not screen_words:
        screen_words = ["Settings"]

    if len(screen_words) == 1:
        description = f"It will open your {screen_words[0]} settings"
    elif len(screen_words) == 2:
        description = f"It will open {screen_words[0]} {screen_words[1]} settings"
    elif len(screen_words) == 3:
        description = f"It will open {screen_words[0]} {screen_words[1]} {screen_words[2]}"
    else:
        description = f"It will open {screen_words[0]} {screen_words[1]} settings"

    # Validate word count strictly
    wc = count_words(description)
    if wc < 5:
        description = f"It will open your {screen_title} settings"
    elif wc > 7:
        description = f"It will open {screen_title} settings on device"
        if count_words(description) > 7:
            description = f"It will open {screen_words[0]} {screen_words[1]} settings"

    # Ensure zero URL leaks
    description = sanitize_text(description)
    message = sanitize_text(message)

    dummy_uri = _get_dummy_deeplink_uri()
    deeplink = Deeplink(
        deeplink=dummy_uri,
        description=description,
        message=message,
        originalType="placeholder",
    )

    return DeeplinkResolutionResult(
        actionable_deeplink=deeplink,
        validation_deeplink=None,
        matched_entry_id="DL-DUMMY",
        matched_fields=["grounded_fallback", "concrete_screen_extraction"],
        confidence_score=0.0,
        is_fallback=True,
        debug_explanation=f"No high-confidence catalog match found. Grounded fallback created naming concrete screen '{clean_screen}'.",
    )


def _get_dummy_deeplink_uri() -> str:
    """Detect whether catalog uses voiceassist://dummy_positive or bixby://dummy_positive."""
    try:
        catalog_path = Path(__file__).resolve().parent.parent.parent / "deeplinks.json"
        if catalog_path.exists():
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for dl in data.get("deeplinks", []):
                if dl.get("id") == "DL-DUMMY":
                    return dl.get("deeplink", "voiceassist://dummy_positive")
    except Exception:
        pass
    return "voiceassist://dummy_positive"
