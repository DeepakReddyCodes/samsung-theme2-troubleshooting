"""Polarity and Action Direction detector for Samsung Guided Troubleshooting Engine.

Distinguishes:
- Enable vs Disable
- Backup vs Restore vs Reset
- Problem symptom vs Desired action
- Positive vs Negative state
"""
import re
from typing import Set, Tuple


ENABLE_KEYWORDS = {
    "enable", "turn on", "activate", "start", "connect", "turn on wifi",
    "turn on bluetooth", "set up", "switch on", "allow", "unmute", "unlock",
}

DISABLE_KEYWORDS = {
    "disable", "turn off", "deactivate", "stop", "disconnect", "turn off wifi",
    "turn off bluetooth", "switch off", "block", "mute", "lock", "remove", "delete",
}

BACKUP_KEYWORDS = {
    "backup", "back up", "save", "sync", "upload to cloud", "smart switch backup",
}

RESTORE_KEYWORDS = {
    "restore", "recover", "retrieve", "bring back", "smart switch restore",
}

RESET_KEYWORDS = {
    "reset", "factory reset", "wipe", "erase", "format", "clear all data",
}

NEGATION_PATTERNS = [
    r"\bnot\s+\w+",
    r"\bno\s+\w+",
    r"\bwon'?t\s+\w+",
    r"\bcan'?t\s+\w+",
    r"\bcannot\s+\w+",
    r"\bdoesn'?t\s+\w+",
    r"\bdoes\s+not\s+\w+",
    r"\bfails?\s+to\s+\w+",
    r"\bunable\s+to\s+\w+",
    r"\bstopped\s+\w+",
    r"\bkeeps?\s+\w+",
    r"\bbroken\b",
    r"\bfailure\b",
    r"\bissues?\b",
    r"\bproblems?\b",
]


def detect_polarity_and_action(text: str) -> Tuple[str, str, Set[str]]:
    """Analyze query text to determine polarity, requested action direction, and detected flags.
    
    Returns:
        (polarity, requested_action, intent_flags)
    """
    text_lower = text.lower()
    intent_flags: Set[str] = set()

    # 1. Action direction
    requested_action = "troubleshoot"
    polarity = "negative"

    if any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in RESET_KEYWORDS):
        requested_action = "reset"
        polarity = "critical"
        intent_flags.add("reset")
    elif any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in RESTORE_KEYWORDS):
        requested_action = "restore"
        polarity = "restore"
        intent_flags.add("restore")
    elif any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in BACKUP_KEYWORDS):
        requested_action = "backup"
        polarity = "backup"
        intent_flags.add("backup")
    elif any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in DISABLE_KEYWORDS):
        requested_action = "disable"
        polarity = "disable"
        intent_flags.add("disable")
    elif any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in ENABLE_KEYWORDS):
        requested_action = "enable"
        polarity = "enable"
        intent_flags.add("enable")

    # 2. Check for explicit question/configuration intent vs error symptom
    if re.search(r"\b(how\s+to|how\s+do\s+i|steps\s+to|configure|set\s+up)\b", text_lower):
        intent_flags.add("configuration")
        if polarity == "negative":
            polarity = "neutral_inquiry"

    # 3. Check for negation
    for neg_pat in NEGATION_PATTERNS:
        if re.search(neg_pat, text_lower):
            intent_flags.add("negation_detected")
            if polarity not in {"enable", "disable", "reset", "backup", "restore"}:
                polarity = "negative"

    return polarity, requested_action, intent_flags
