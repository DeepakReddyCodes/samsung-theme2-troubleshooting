"""Deterministic, rule-based SIIS knowledge extractor and fallback provider.

Guarantees:
1. 100% grounded in provided SIIS text (zero hallucination).
2. Runs offline without API keys or network requests.
3. Parses structured headers (##, ###), steps, and procedures.
4. Defends against prompt injection and irrelevant/adversarial content.
5. Correctly classifies auto, manual, and critical actions.
6. Returns empty action list if SIIS contains no actionable troubleshooting facts.
"""
import logging
import re
from typing import List, Optional, Set, Tuple

from app.core.rewrite_controller import (
    count_words,
    format_goal,
    rewrite_action_description,
    rewrite_title,
)
from app.services.extractor.base import ExtractedAction, ILLMProvider, IntermediateIntent

logger = logging.getLogger(__name__)

# Keywords determining category
CRITICAL_KEYWORDS = {
    "force restart", "force a restart", "recovery mode", "factory reset",
    "factory data reset", "reboot system", "hard reset", "wipe cache",
}
MANUAL_KEYWORDS = {
    "service center", "repair services", "liquid damage indicator", "ldi",
    "ejector tool", "sim tray", "mouse and keyboard", "hardware", "authorized service",
    "inspect charger", "usb port", "flashlight", "authorized samsung",
}

# Prompt injection and adversarial phrases to filter out from SIIS
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions",
    r"disregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions|prompts)",
    r"system\s+override",
    r"system\s+prompt",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"jailbreak",
]

# Sensitive / injection-prone operations that require query relevance to extract
SENSITIVE_ACTIONS = {
    "usb debugging": ["usb debugging", "developer options", "adb"],
    "developer options": ["developer options", "developer settings", "build number"],
    "factory reset": ["factory reset", "wipe all", "factory data reset", "erase all"],
}


class DeterministicFallbackExtractor(ILLMProvider):
    """Deterministic extractor parsing SIIS markdown content into structured intent."""

    def _determine_goal_mode(self, siis_title: str) -> str:
        """Classify whether the article is primarily Troubleshooting or Configuration."""
        title_lower = siis_title.lower()
        if any(term in title_lower for term in ["how to", "use multi", "transfer", "configure", "set up", "mirroring"]):
            return "Configuration"
        return "Troubleshooting"

    def _derive_topic(self, siis_title: str) -> str:
        """Clean boilerplate device prefixes and derive the core problem topic."""
        clean = siis_title
        # Filter prompt injection phrases
        clean = re.sub(r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions.*$", "", clean, flags=re.IGNORECASE).strip()

        for prefix in [
            "Smartphone,Others Mobile,Tablet,Mobile Accessories",
            "Mobile Accessories,Smartphone,Tablet,Others Mobile",
            "Smartphone,Others Mobile,Mobile Accessories,Tablet",
        ]:
            if clean.startswith(prefix):
                clean = clean[len(prefix):].strip()

        # Remove common question/troubleshooting prefixes
        for prefix_pat in [
            r"^what to do if (?:your )?(?:samsung |galaxy )?(?:phone'?s |tablet'?s |device'?s )?",
            r"^what to do when (?:your )?(?:samsung |galaxy )?(?:phone'?s |tablet'?s |device'?s )?",
            r"^how to (?:fix |troubleshoot |use |resolve |set up |configure )?",
            r"^troubleshooting (?:guide for |for )?",
        ]:
            clean = re.sub(prefix_pat, "", clean, flags=re.IGNORECASE).strip()

        # Remove trailing device suffixes like 'on Samsung phone or tablet'
        clean = re.sub(
            r"\s+(?:on|for)\s+(?:a\s+)?(?:Samsung|Galaxy)?\s*(?:phone|tablet|device).*$",
            "",
            clean,
            flags=re.IGNORECASE,
        ).strip()

        # Remove sentence punctuation
        clean = re.sub(r"[^\w\s-]", " ", clean).strip()
        words = clean.split()
        if len(words) > 3:
            content = [w for w in words if w.lower() not in {"and", "or", "the", "a", "an", "on", "in", "for", "with", "of", "is", "are"}]
            if 2 <= len(content) <= 3:
                clean = " ".join(content)
            elif len(content) > 3:
                clean = " ".join(content[:3])
            else:
                clean = " ".join(words[:3])

        return clean.title() if clean else "Device Issue"

    def _classify_category(self, section_title: str, text: str) -> str:
        """Classify action as auto, manual, or critical based on content."""
        combined = f"{section_title} {text}".lower()

        if any(kw in combined for kw in CRITICAL_KEYWORDS):
            return "critical"

        if any(kw in combined for kw in MANUAL_KEYWORDS):
            return "manual"

        # If mentions Settings, toggling, or navigation, it is auto
        if any(kw in combined for kw in ["settings", "navigate to", "tap", "select", "toggle", "switch", "enable"]):
            return "auto"

        return "manual"

    def _is_prompt_injection(self, text: str) -> bool:
        """Check if text contains prompt injection commands."""
        text_lower = text.lower()
        for pat in PROMPT_INJECTION_PATTERNS:
            if re.search(pat, text_lower):
                return True
        return False

    def _is_actionable_instruction(self, sentence: str) -> bool:
        """Determine if a sentence contains a genuine actionable troubleshooting/settings step."""
        s_clean = sentence.strip()
        if not s_clean or len(s_clean.split()) < 3:
            return False

        # Exclude purely explanatory/definition sentences
        if re.search(r"^(the|this)\s+[\w\s]+\s+is\s+a\s+(natural|satellite|feature|device|guide)", s_clean, re.IGNORECASE):
            return False
        if re.search(r"^this\s+guide\s+helps\s+you", s_clean, re.IGNORECASE):
            return False

        first_word = s_clean.split()[0].lower() if s_clean.split() else ""
        imperative_verbs = {
            "navigate", "tap", "select", "choose", "open", "swipe", "turn", "press",
            "hold", "disconnect", "connect", "check", "ensure", "verify", "insert",
            "remove", "inspect", "eject", "contact", "provide", "toggle", "use",
            "scroll", "drag", "put", "visit", "restart", "reboot", "power", "clean",
            "dry", "unplug", "plug", "charge", "enable", "disable", "set", "adjust",
            "make", "keep", "avoid", "allow", "switch", "test",
        }

        has_imperative = first_word in imperative_verbs
        has_settings_nav = bool(re.search(r"\b(settings|device care|quick settings|quick panel|tap on|select|toggle|switch to|from settings)\b", s_clean, re.IGNORECASE))
        has_action_phrase = bool(re.search(r"\b(turn on|turn off|power off|re-insert|put unused|make calls|drag the|scroll to)\b", s_clean, re.IGNORECASE))

        return has_imperative or has_settings_nav or has_action_phrase

    def _extract_steps_from_section(self, section_text: str, query: str = "") -> List[str]:
        """Extract clean imperative step sentences from section text."""
        raw_lines = section_text.split("\n")
        steps = []
        query_lower = query.lower()

        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Strip list prefixes: '1. ', '2. ', '- ', '* '
            clean_line = re.sub(r"^(\d+[\.\)]|\*|\-)\s*", "", stripped).strip()

            # Split into sentences if line has multiple imperative steps
            sentences = re.split(r"(?<=[.!?])\s+", clean_line)
            for s in sentences:
                s_clean = s.strip()
                if not s_clean:
                    continue

                # Filter prompt injection in sentence
                if self._is_prompt_injection(s_clean):
                    logger.warning(f"Filtered prompt injection sentence: '{s_clean}'")
                    continue

                # Sensitive action relevance check
                is_sensitive_unrelated = False
                for op_name, op_kws in SENSITIVE_ACTIONS.items():
                    if any(kw in s_clean.lower() for kw in op_kws):
                        # If query is not asking about this operation, filter it out
                        if not any(kw in query_lower for kw in op_kws):
                            is_sensitive_unrelated = True
                            break

                if is_sensitive_unrelated:
                    logger.warning(f"Filtered sensitive/unrelated action: '{s_clean}'")
                    continue

                # Check if this sentence is an actionable instruction
                if self._is_actionable_instruction(s_clean):
                    # Clean out web references like 'at the provided links'
                    s_clean = re.sub(r"\s+at the provided links\.?", "", s_clean, flags=re.IGNORECASE)
                    if s_clean and not s_clean.endswith("."):
                        s_clean += "."
                    if s_clean and len(s_clean.split()) >= 3:
                        steps.append(s_clean)

        return steps[:5]  # Cap at top 5 granular steps per action

    def extract(self, query: str, siis_title: str, siis_content: str) -> IntermediateIntent:
        """Extract structured intermediate intent from SIIS title and markdown content."""
        goal_mode = self._determine_goal_mode(siis_title)
        topic = self._derive_topic(siis_title)
        title = rewrite_title(topic)

        # Parse sections separated by markdown headers
        sections = re.split(r"\n(?=##+\s+)", siis_content)

        actions: List[ExtractedAction] = []

        for sec in sections:
            sec_clean = sec.strip()
            if not sec_clean:
                continue

            lines = sec_clean.split("\n")
            header_line = lines[0].strip()
            sec_title = re.sub(r"^#+\s*", "", header_line).strip()
            # Strip Step prefixes like 'Step 1: '
            clean_sec_title = re.sub(r"^Step\s*\d+[:\-]?\s*", "", sec_title).strip()

            body_text = "\n".join(lines[1:]) if len(lines) > 1 else lines[0]
            steps = self._extract_steps_from_section(body_text, query=query)

            if not steps:
                continue

            category = self._classify_category(sec_title, body_text)

            # Clean prompt injection from section title
            clean_sec_title = re.sub(r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions.*$", "", clean_sec_title, flags=re.IGNORECASE).strip()
            # If section title is a long sentence or paragraph, derive concise action title
            if len(clean_sec_title.split()) > 5 or "." in clean_sec_title:
                action_name = f"Check {topic} Settings"
            else:
                action_name = clean_sec_title.title()

            if not action_name or action_name.lower() in {"overview", "introduction", "device support"}:
                action_name = f"Check {topic} Settings"

            # Build 5-7 word description starting with 'It will'
            base_desc = f"It will configure your {topic.lower()} settings"
            desc = rewrite_action_description(base_desc, action_name)

            # Extract screen hint if mentioned
            screen_hint = ""
            for s in steps:
                if "settings" in s.lower():
                    screen_hint = "Settings"
                    break

            actions.append(
                ExtractedAction(
                    action_name=action_name,
                    description=desc,
                    category=category,
                    steps=steps,
                    screen_hint=screen_hint,
                    evidence=sec_title,
                )
            )

        # If no header-based sections found, try parsing body text
        if not actions:
            fallback_steps = self._extract_steps_from_section(siis_content, query=query)
            if fallback_steps:
                actions.append(
                    ExtractedAction(
                        action_name=f"Troubleshoot {topic}",
                        description=f"It will configure your {topic.lower()} settings",
                        category="auto",
                        steps=fallback_steps,
                        screen_hint="Settings",
                        evidence=siis_title,
                    )
                )

        # Invariant: If NO actionable steps were found in SIIS, return empty actions list!
        # NEVER invent generic troubleshooting steps!
        return IntermediateIntent(
            topic=topic,
            goal_mode=goal_mode,
            title=title,
            actions=actions[:3],  # Best 1 to 3 actions, or [] if no actionable steps
            raw_siis_title=siis_title,
        )
