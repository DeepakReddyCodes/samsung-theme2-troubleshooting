"""Runner entrypoint for benchmark engine."""
from pathlib import Path
import sys

# Ensure codebase root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.benchmark_engine import run_benchmark

if __name__ == "__main__":
    run_benchmark()
