import pytest
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.benchmark_engine import get_system_metadata

def test_benchmark_engine_metadata():
    """Verify that the benchmark metadata payload is structurally sound and accurately reports deterministic mock state."""
    metadata = get_system_metadata()

    assert "operating_system" in metadata
    assert "python_version" in metadata
    assert "fastapi_version" in metadata
    assert "pydantic_version" in metadata

    assert metadata["benchmark_mode"] == "offline_deterministic"
    assert "Mock" in metadata["provider"]
    assert metadata["llm_called"] is False
    assert "models_loaded" in metadata
