"""Sanitizer and Zero-URL Leak detector enforcing Gate G5.

Ensures absolute prohibition of web URLs (http, https, www, .com, etc.)
while strictly protecting legitimate Samsung deeplinks (bixby://...).
"""
import re
from typing import Any, List, Tuple

# Patterns identifying web URL leaks (G5 violation)
# Explicitly ignores bixby:// schemes
_HTTP_PATTERN = re.compile(r"https?://[^\s<>'\"\)\]]+", re.IGNORECASE)
_WWW_PATTERN = re.compile(r"\bwww\.[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+[^\s<>'\"\)\]]*", re.IGNORECASE)
_DOMAIN_PATTERN = re.compile(
    r"\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|org|net|edu|gov|io|co|in|ai)\b(?:/[^\s<>'\"\)\]]*)?",
    re.IGNORECASE,
)
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")
_HTML_LINK_PATTERN = re.compile(r"<a\s+[^>]*href=[\"'][^\"']*[\"'][^>]*>(.*?)</a>", re.IGNORECASE)


def is_bixby_uri(text: str) -> bool:
    """Return True if text is a legitimate Samsung bixby URI."""
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    return stripped.startswith("bixby://")


def find_url_leaks(text: str) -> List[Tuple[str, str]]:
    """Scan text for any web URL leaks.
    
    Returns a list of (leak_type, matched_string) tuples.
    If the text itself is a legitimate bixby URI, it is not flagged.
    """
    if not isinstance(text, str) or not text:
        return []

    # Legitimate Samsung deeplinks are never web URL leaks
    if is_bixby_uri(text):
        return []

    leaks: List[Tuple[str, str]] = []

    # Check for markdown links [label](url)
    for match in _MARKDOWN_LINK_PATTERN.finditer(text):
        url_part = match.group(2)
        if not is_bixby_uri(url_part):
            leaks.append(("markdown_link", match.group(0)))

    # Check for HTML links
    for match in _HTML_LINK_PATTERN.finditer(text):
        leaks.append(("html_link", match.group(0)))

    # Check for http:// or https://
    for match in _HTTP_PATTERN.finditer(text):
        leaks.append(("http_url", match.group(0)))

    # Check for www.
    for match in _WWW_PATTERN.finditer(text):
        leaks.append(("www_url", match.group(0)))

    # Check for bare domain names with common TLDs (e.g., samsung.com)
    for match in _DOMAIN_PATTERN.finditer(text):
        # Exclude matches that are part of bixby package identifiers like com.android.settings
        matched_str = match.group(0)
        start_idx = match.start()
        # Look behind to ensure it's not prefixed by 'bixby://' or a package path
        prefix = text[max(0, start_idx - 10):start_idx]
        if "bixby://" in prefix or prefix.endswith("/"):
            continue
        leaks.append(("domain_url", matched_str))

    return leaks


def has_url_leaks(text: str) -> bool:
    """Return True if any web URL leak is detected in text."""
    return len(find_url_leaks(text)) > 0


def sanitize_text(text: str) -> str:
    """Scrub web URLs, domains, and markdown links from text while preserving legitimate content."""
    if not isinstance(text, str) or not text:
        return text

    if is_bixby_uri(text):
        return text

    cleaned = text

    # Replace markdown links with just their anchor text
    cleaned = _MARKDOWN_LINK_PATTERN.sub(r"\1", cleaned)

    # Replace HTML links with their inner text
    cleaned = _HTML_LINK_PATTERN.sub(r"\1", cleaned)

    # Remove http:// and https:// URLs
    cleaned = _HTTP_PATTERN.sub("", cleaned)

    # Remove www. URLs
    cleaned = _WWW_PATTERN.sub("", cleaned)

    # Remove bare domain URLs (e.g. samsung.com/support)
    def _domain_cleaner(match: re.Match) -> str:
        start_idx = match.start()
        prefix = cleaned[max(0, start_idx - 10):start_idx]
        if "bixby://" in prefix or prefix.endswith("/"):
            return match.group(0)
        return ""

    cleaned = _DOMAIN_PATTERN.sub(_domain_cleaner, cleaned)

    # Clean up any leftover double spaces or dangling punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.\?!])", r"\1", cleaned)
    return cleaned


def scan_object_for_url_leaks(obj: Any, path: str = "root") -> List[Tuple[str, str, str]]:
    """Recursively scan a dictionary, list, or Pydantic model for URL leaks.
    
    Returns a list of (field_path, leak_type, matched_string) tuples.
    """
    leaks = []

    if isinstance(obj, str):
        # Only check string if it is not a deeplink URI field
        if not path.endswith("deeplink"):
            found = find_url_leaks(obj)
            for leak_type, matched in found:
                leaks.append((path, leak_type, matched))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            child_path = f"{path}.{k}"
            leaks.extend(scan_object_for_url_leaks(v, child_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            child_path = f"{path}[{i}]"
            leaks.extend(scan_object_for_url_leaks(item, child_path))
    elif hasattr(obj, "model_dump"):
        leaks.extend(scan_object_for_url_leaks(obj.model_dump(), path))

    return leaks
