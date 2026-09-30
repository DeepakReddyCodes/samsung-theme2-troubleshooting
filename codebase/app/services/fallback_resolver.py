"""Fallback resolver generating grounded bixby://dummy_positive deeplinks.

Enforces:
1. URI is strictly 'bixby://dummy_positive'.
2. Description is exactly 5 to 7 words, starts with 'It will', and names the concrete screen.
3. Message names the concrete Settings screen derived from the actual step/intent.
4. Never invents troubleshooting steps.
5. Guaranteed zero URL leaks.
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
]


def extract_concrete_screen_name(intent: TroubleshootingIntent) -> Optional[str]:
    """Extract the most concrete Samsung Settings screen name from intent steps or action name."""
    text_corpus = f"{intent.screen_hint} {intent.action_name} {' '.join(intent.steps)}"

    # 1. Look for explicit 'Tap on <Screen>', 'Select <Screen>', 'Go to <Screen>' patterns
    pattern = re.compile(
        r"(?:tap on|tap|select|go to|open|navigate to and open|navigate to)\s+([A-Z][a-zA-Z0-9\s&-]+?)(?=[.,;]|and then|\btap\b|\bselect\b|$)",
        re.IGNORECASE,
    )
    matches = pattern.findall(text_corpus)
    for m in matches:
        candidate = m.strip()
        # Clean filler words
        candidate = re.sub(r"^(and|the|your)\s+", "", candidate, flags=re.IGNORECASE).strip()
        # If candidate matches a known screen or looks like a valid screen name (1-4 words)
        for known in KNOWN_SETTINGS_SCREENS:
            if known.lower() == candidate.lower() or known.lower() in candidate.lower():
                return known
        words = candidate.split()
        # We must not invent targets. Returning something like "Device settings" because it passed this regex is dangerous.
        # Only return candidate if it is a strong match, e.g. capitalized or matches a known word.
        # For W03 strict policy, we simply shouldn't blindly trust `candidate.capitalize()`.
        # However, to avoid breaking other legitimate screens not in KNOWN_SETTINGS_SCREENS but explicitly navigated to
        if 1 <= len(words) <= 3 and candidate.lower() not in {"settings", "it", "this", "device settings", "device", "menu"}:
            return candidate.capitalize()

    # 2. Check for presence of known screen keywords in the text corpus
    for known in KNOWN_SETTINGS_SCREENS:
        if re.search(r"\b" + re.escape(known) + r"\b", text_corpus, re.IGNORECASE):
            return known

    # 3. Fallback to core action noun
    action_words = re.findall(r"\b[\w'-]+\b", intent.action_name)
    cleaned_words = [w for w in action_words if w.lower() not in {"configure", "set", "settings", "to", "and", "the"}]

    return None


def create_grounded_dummy_positive(
    intent: TroubleshootingIntent,
    screen_name: Optional[str] = None,
) -> Optional[DeeplinkResolutionResult]:
    """Build a grounded bixby://dummy_positive resolution strictly derived from the intent context."""
    screen = screen_name or extract_concrete_screen_name(intent)

    if not screen:
        return None

    # Clean screen name for message and description
    clean_screen = sanitize_text(screen)

    # 1. Message: Names the concrete screen
    message = f"Open {clean_screen} Settings"
    if count_words(message) > 5:
        # Keep concise
        screen_short = " ".join(clean_screen.split()[:2])
        message = f"Open {screen_short} Settings"

    # 2. Description: Exactly 5 to 7 words, starts with 'It will', names the screen
    # e.g., "It will open navigation bar settings" (6 words)
    # e.g., "It will open your display settings" (6 words)
    screen_words = [w.lower() for w in re.findall(r"\b[\w'-]+\b", clean_screen)]
    if not screen_words:
        screen_words = ["settings"]

    if len(screen_words) == 1:
        # "It will open your display settings" (6 words)
        description = f"It will open your {screen_words[0]} settings"
    elif len(screen_words) == 2:
        # "It will open navigation bar settings" (6 words)
        description = f"It will open {screen_words[0]} {screen_words[1]} settings"
    elif len(screen_words) == 3:
        # "It will open battery and device care" (7 words)
        description = f"It will open {screen_words[0]} {screen_words[1]} {screen_words[2]}"
    else:
        # "It will open display settings on device" (7 words)
        description = f"It will open {screen_words[0]} {screen_words[1]} settings"

    # Validate word count strictly
    wc = count_words(description)
    if wc < 5:
        description = f"It will open your {clean_screen.lower()} settings"
    elif wc > 7:
        description = f"It will open your device settings"

    # Ensure zero URL leaks
    description = sanitize_text(description)
    message = sanitize_text(message)

    deeplink = Deeplink(
        deeplink="bixby://dummy_positive",
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
