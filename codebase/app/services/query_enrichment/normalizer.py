"""Query normalization utilities for Samsung Guided Troubleshooting Engine.

Converts raw user strings into clean, standardized textual representations
while preserving semantic meaning, technical terms, and negations.
"""
import re
from typing import Dict

# Domain compound replacements and terminology canonicalization
COMPOUND_MAP: Dict[str, str] = {
    r"\bwi-fi\b": "wifi",
    r"\bwi fi\b": "wifi",
    r"\bwireless fidelity\b": "wifi",
    r"\bblue-tooth\b": "bluetooth",
    r"\bblue tooth\b": "bluetooth",
    r"\btouch-screen\b": "touch screen",
    r"\btouchscreen\b": "touch screen",
    r"\block-screen\b": "lock screen",
    r"\blockscreen\b": "lock screen",
    r"\bhome-screen\b": "home screen",
    r"\bhomescreen\b": "home screen",
    r"\bnav-bar\b": "navigation bar",
    r"\bnavbar\b": "navigation bar",
    r"\bnavigation-bar\b": "navigation bar",
    r"\bauto-sync\b": "autosync",
    r"\bauto sync\b": "autosync",
    r"\bquick-share\b": "quick share",
    r"\bquickshare\b": "quick share",
    r"\bsmart-switch\b": "smart switch",
    r"\bsmartswitch\b": "smart switch",
    r"\bs-pen\b": "spen",
    r"\bs pen\b": "spen",
    r"\bhot-spot\b": "hotspot",
    r"\bhot spot\b": "hotspot",
    r"\bpower-saving\b": "power saving",
    r"\bdark-mode\b": "dark mode",
    r"\beye-comfort\b": "eye comfort shield",
    r"\beye comfort\b": "eye comfort shield",
    r"\brefresh-rate\b": "motion smoothness",
    r"\brefresh rate\b": "motion smoothness",
    r"\bfinger-print\b": "fingerprint",
    r"\bfinger print\b": "fingerprint",
    r"\bface-unlock\b": "face recognition",
    r"\bface unlock\b": "face recognition",
    r"\bmulti-window\b": "multi window",
    r"\bmultiwindow\b": "multi window",
    r"\bback-up\b": "backup",
    r"\bback up\b": "backup",
    r"\bfactory-reset\b": "factory reset",
    r"\bhard-reset\b": "factory reset",
}


def normalize_query_text(query: str) -> str:
    """Clean and normalize raw query text."""
    if not query:
        return ""
    text = query.strip()
    # Strip leading numbering like '1. ', '1) ', 'Row 1: ', '"1. '
    text = re.sub(r"^(?:row\s*\d+[:\-]?|\d+[\.\)]|\*|\-)\s*[\"']?", "", text, flags=re.IGNORECASE)
    # Strip enclosing quotes
    text = re.sub(r"^[\"']|[\"']$", "", text)
    text = text.lower()

    # Apply domain compounds
    for pat, rep in COMPOUND_MAP.items():
        text = re.sub(pat, rep, text)

    # Replace punctuation except hyphens in technical words
    text = re.sub(r"[^\w\s-]", " ", text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text
