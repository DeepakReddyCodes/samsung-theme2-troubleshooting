"""Executable tests for SIIS grounding invariant."""
import pytest
from app.services.extractor.grounding_checker import GroundingChecker


def test_grounding_rejects_unsupported_facts():
    """Check that if an action is proposed without SIIS support, the checker fails it."""
    checker = GroundingChecker()
    siis_content = "To fix the display, go to Settings and select Display."
    step = "Open the developer options and enable USB debugging."

    result = checker.check_step(step, siis_content)
    # The current checker is lexical, but it should fail this completely unrelated step.
    assert result.is_grounded is False


def test_grounding_rejects_generic_invented_troubleshooting():
    """Ensure fallback instructions like 'Check display settings' without SIIS backup fail."""
    checker = GroundingChecker()
    siis_content = "Turn off the phone and turn it back on."
    step = "Check display settings."

    result = checker.check_step(step, siis_content)
    assert result.is_grounded is False


def test_grounding_preserves_polarity():
    """Check that enable/disable semantics are not inverted.
    Note: Current lexical grounding might fail this. Exposing this defect is valuable.
    """
    checker = GroundingChecker()
    siis_content = "Disable the Wi-Fi connection."
    step = "Enable the Wi-Fi connection."

    # We want to see if the current implementation catches this.
    # It might pass currently (which is a bug according to W00). We just assert the ideal behavior.
    result = checker.check_step(step, siis_content)

    # Currently, the baseline fails this (it says it IS grounded because words overlap).
    # We document the failure by asserting it should be False.
    assert result.is_grounded is False
