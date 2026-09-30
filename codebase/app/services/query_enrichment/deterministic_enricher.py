"""Deterministic Stage 1 Query Enricher.

Converts vague customer device complaints into structured technical representations
using high-precision Galaxy domain ontology, polarity detection, and symptom extraction.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.query_enrichment.models import EnrichedQuery
from app.services.query_enrichment.normalizer import normalize_query_text
from app.services.query_enrichment.polarity import detect_polarity_and_action

# Galaxy domain ontology mapping keywords to (Domain, Candidate Settings Screens, Technical Concept)
DOMAIN_ONTOLOGY: List[Dict[str, Any]] = [
    {
        "keywords": ["wifi", "wi-fi", "internet", "network", "router", "ssid", "connection", "hotspot", "airplane mode", "flight mode", "nfc"],
        "domain": "Connections",
        "screens": ["Connections", "Wi-Fi", "Mobile Hotspot and Tethering", "NFC and contactless payments", "Airplane mode"],
        "default_title": "Wi-Fi & Connectivity",
    },
    {
        "keywords": ["bluetooth", "earbuds", "galaxy buds", "headphone", "pair", "pairing", "bluetooth device"],
        "domain": "Connections",
        "screens": ["Bluetooth", "Connections"],
        "default_title": "Bluetooth Connection",
    },
    {
        "keywords": ["battery", "drain", "draining", "charge", "charging", "fast charging", "overheating", "standby power", "power saving"],
        "domain": "Battery and device care",
        "screens": ["Battery and device care", "Battery", "Device care"],
        "default_title": "Battery & Power Management",
    },
    {
        "keywords": ["display", "screen", "brightness", "adaptive brightness", "motion smoothness", "refresh rate", "dark mode", "eye comfort", "resolution", "flicker", "green line", "peeling", "cracked", "touch screen", "touch", "rotation", "auto rotate"],
        "domain": "Display",
        "screens": ["Display", "Navigation bar", "Motion smoothness", "Eye comfort shield"],
        "default_title": "Display & Screen",
    },
    {
        "keywords": ["sound", "volume", "speaker", "mute", "vibrate", "vibration", "ringtone", "notification sound", "audio", "mic", "microphone"],
        "domain": "Sounds and vibration",
        "screens": ["Sounds and vibration", "Volume", "Sound quality and effects"],
        "default_title": "Sound & Vibration",
    },
    {
        "keywords": ["lock screen", "lockscreen", "aod", "always on display", "clock style", "wallpaper", "widgets", "lock"],
        "domain": "Lock screen",
        "screens": ["Lock screen", "Always On Display"],
        "default_title": "Lock Screen & AOD",
    },
    {
        "keywords": ["fingerprint", "biometrics", "face recognition", "pin", "password", "pattern", "secure folder", "knox", "security", "privacy"],
        "domain": "Security and privacy",
        "screens": ["Security and privacy", "Biometrics and security", "Fingerprints", "Face recognition"],
        "default_title": "Security & Biometrics",
    },
    {
        "keywords": ["backup", "restore", "smart switch", "samsung cloud", "sync", "google drive", "transfer data", "switch phone"],
        "domain": "Accounts and backup",
        "screens": ["Accounts and backup", "Smart Switch", "Manage accounts"],
        "default_title": "Accounts & Backup",
    },
    {
        "keywords": ["app", "apps", "crash", "crashing", "clear cache", "clear data", "permissions", "default apps", "uninstall", "frozen app"],
        "domain": "Apps",
        "screens": ["Apps", "Default apps", "Permission manager"],
        "default_title": "Application Management",
    },
    {
        "keywords": ["spen", "s pen", "air actions", "stylus", "pen button", "air command"],
        "domain": "Advanced features",
        "screens": ["Advanced features", "S Pen"],
        "default_title": "S Pen & Air Actions",
    },
    {
        "keywords": ["multi window", "split screen", "side button", "power button", "gestures", "motions and gestures", "one hand mode", "dex", "samsung dex", "quick share"],
        "domain": "Advanced features",
        "screens": ["Advanced features", "Motions and gestures", "Side button", "Quick Share"],
        "default_title": "Advanced Features & Gestures",
    },
    {
        "keywords": ["reset", "factory reset", "factory data reset", "reset network settings", "reset all settings", "date and time", "language", "keyboard"],
        "domain": "General management",
        "screens": ["General management", "Reset"],
        "default_title": "General Management & Reset",
    },
    {
        "keywords": ["software update", "system update", "firmware", "one ui update", "download update"],
        "domain": "Software update",
        "screens": ["Software update"],
        "default_title": "Software Update",
    },
    {
        "keywords": ["camera", "photo", "video recording", "flash", "camera settings", "shutter"],
        "domain": "Camera",
        "screens": ["Camera", "Apps"],
        "default_title": "Camera Configuration",
    },
]

# Known hardware / software entity terms
KNOWN_ENTITIES = [
    "Samsung Galaxy", "Galaxy phone", "Galaxy tablet", "Galaxy S24", "Galaxy S23",
    "Galaxy Z Fold", "Galaxy Z Flip", "S Pen", "Smart Switch", "Samsung Cloud",
    "TechCorp", "Nexa", "Nexa X1", "Nexa Fold X1", "TechCorp A15G", "Stylus Pen",
    "Data Transfer", "Quick Assist", "VoiceAssist", "TechCorp Cloud",
    "Quick Share", "Eye Comfort Shield", "Always On Display", "Adaptive Brightness",
    "Motion Smoothness", "Navigation Bar", "Bixby", "Samsung Dex", "Wi-Fi Calling",
    "Mobile Hotspot", "Secure Folder", "Knox", "Google Drive",
]


class DeterministicQueryEnricher:
    """Deterministic, high-speed Stage 1 query enricher."""

    def enrich(self, raw_query: str, siis_title: Optional[str] = None, siis_content: Optional[str] = None) -> EnrichedQuery:
        """Process raw query into an EnrichedQuery object."""
        normalized = normalize_query_text(raw_query)
        polarity, requested_action, intent_flags = detect_polarity_and_action(normalized)

        # Match domain from ontology
        matched_domain = "General Device Support"
        candidate_screens: List[str] = ["Settings"]
        symptoms: List[str] = []
        detected_entities: List[str] = []

        tokens = set(normalized.split())

        # Check domain matches
        best_match_count = 0
        technical_concept = "Device Issue"

        for entry in DOMAIN_ONTOLOGY:
            kw_matches = sum(1 for kw in entry["keywords"] if (kw in normalized or any(k in tokens for k in kw.split())))
            if kw_matches > best_match_count:
                best_match_count = kw_matches
                matched_domain = entry["domain"]
                candidate_screens = list(entry["screens"])
                technical_concept = entry["default_title"]

        # If SIIS title exists and provides stronger domain cues, align context
        if siis_title:
            siis_title_clean = normalize_query_text(siis_title)
            for entry in DOMAIN_ONTOLOGY:
                if any(kw in siis_title_clean for kw in entry["keywords"]):
                    if best_match_count == 0 or entry["domain"] == matched_domain:
                        matched_domain = entry["domain"]
                        for s in entry["screens"]:
                            if s not in candidate_screens:
                                candidate_screens.append(s)

        # Detect entities
        for ent in KNOWN_ENTITIES:
            if re.search(r"\b" + re.escape(ent.lower()) + r"\b", normalized):
                detected_entities.append(ent)

        # Extract symptom keywords
        symptom_words = ["flicker", "drain", "disconnect", "crash", "freeze", "slow", "rotate", "peeling", "cracked", "lines", "lag", "overheating", "fail", "broken", "unresponsive", "stuck"]
        for sw in symptom_words:
            if sw in normalized:
                symptoms.append(sw)

        # Classify intent category
        intent_category = "configuration" if "configuration" in intent_flags else "troubleshooting"

        # Formulate technical query
        clean_words = [w.capitalize() for w in normalized.split() if len(w) > 2][:6]
        tech_core = " ".join(clean_words)
        technical_query = f"{matched_domain}: {tech_core} ({technical_concept})"

        return EnrichedQuery(
            raw_query=raw_query,
            normalized_query=normalized,
            technical_query=technical_query,
            domain=matched_domain,
            symptoms=symptoms,
            entities=detected_entities,
            polarity=polarity,
            requested_action=requested_action,
            constraints=[],
            intent_category=intent_category,
            candidate_settings_screens=candidate_screens,
            stage1_confidence=0.95 if best_match_count > 0 else 0.70,
        )
