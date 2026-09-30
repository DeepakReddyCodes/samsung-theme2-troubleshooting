"""Unit tests for Stage 1 Query Enrichment."""
import pytest
from app.services.query_enrichment import (
    DeterministicQueryEnricher,
    EnrichedQuery,
    QueryEnricher,
    detect_polarity_and_action,
    normalize_query_text,
)


def test_normalization_removes_bullets_and_compounds():
    """Verify query text normalization cleans bullets, quotes, and standardizes compounds."""
    raw = '1. "My Wi-Fi keeps disconnecting from home network!"'
    norm = normalize_query_text(raw)
    assert norm == "my wifi keeps disconnecting from home network"

    raw2 = "2) Touch-Screen is not responding on my Galaxy S24"
    norm2 = normalize_query_text(raw2)
    assert norm2 == "touch screen is not responding on my galaxy s24"


def test_polarity_and_action_direction_detection():
    """Verify polarity detector accurately distinguishes enable, disable, reset, backup, restore."""
    pol, act, flags = detect_polarity_and_action("How do I enable Wi-Fi on my phone?")
    assert pol == "enable"
    assert act == "enable"

    pol, act, flags = detect_polarity_and_action("How do I turn off Bluetooth?")
    assert pol == "disable"
    assert act == "disable"

    pol, act, flags = detect_polarity_and_action("How to back up my data to Samsung Cloud?")
    assert pol == "backup"
    assert act == "backup"

    pol, act, flags = detect_polarity_and_action("How to factory reset my device?")
    assert pol == "critical"
    assert act == "reset"

    pol, act, flags = detect_polarity_and_action("My display is flickering and green line appeared")
    assert pol == "negative"
    assert "negation_detected" in flags or act == "troubleshoot"


def test_deterministic_query_enrichment():
    """Verify deterministic enricher produces complete EnrichedQuery contract."""
    enricher = DeterministicQueryEnricher()
    eq = enricher.enrich("The battery is draining too fast overnight on my Galaxy S23")

    assert isinstance(eq, EnrichedQuery)
    assert eq.domain == "Battery and device care"
    assert "drain" in eq.symptoms
    assert any("Battery" in s for s in eq.candidate_settings_screens)
    assert eq.polarity == "negative"
    assert len(eq.technical_query) > 0


def test_query_enricher_facade():
    """Verify QueryEnricher top-level orchestrator works reliably."""
    orchestrator = QueryEnricher()
    eq = orchestrator.enrich(
        query="Cannot pair my Galaxy Buds via Bluetooth",
        siis_response={"title": "Pairing Bluetooth devices with Samsung Galaxy", "content": "Open Bluetooth settings"}
    )
    assert eq.domain == "Connections"
    assert "Bluetooth" in eq.candidate_settings_screens
    assert eq.raw_query == "Cannot pair my Galaxy Buds via Bluetooth"
