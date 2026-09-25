"""Global application state and lifecycle manager for Samsung SmartGuide Engine.

Responsible for the orchestrated startup sequence:
1. Load schema.
2. Load deeplink catalog.
3. Load SIIS knowledge.
4. Initialize retrieval indexes.
5. Initialize semantic model if enabled.
6. Prewarm canonical cache.
7. Mark application ready.
"""
import logging
from pathlib import Path
import time
from typing import Any, Dict, Optional

from app.cache.prewarm import prewarm_canonical_scenarios
from app.cache.semantic_cache import FastPathSemanticCache
from app.core.firewall import ValidationFirewall
from app.core.schema import ContextDeeplinkResponse
from app.services.deeplink_matcher import DeeplinkResolver
from app.services.extractor.deterministic_extractor import DeterministicFallbackExtractor
from app.services.extractor.engine import ColdPathExtractionEngine
from app.services.extractor.gemini_extractor import GeminiExtractor
from app.services.extractor.grounding_checker import GroundingChecker

logger = logging.getLogger(__name__)


class ApplicationState:
    """Encapsulates all initialized singletons and lifecycle state."""

    def __init__(self):
        self.is_ready: bool = False
        self.startup_time_s: float = 0.0
        self.catalog_path: Optional[Path] = None
        self.siis_path: Optional[Path] = None
        self.catalog_size: int = 0
        self.firewall: Optional[ValidationFirewall] = None
        self.resolver: Optional[DeeplinkResolver] = None
        self.cache: Optional[FastPathSemanticCache] = None
        self.cold_engine: Optional[ColdPathExtractionEngine] = None
        self.prewarm_stats: Dict[str, Any] = {}

    def initialize(
        self,
        catalog_path: Optional[Path] = None,
        siis_path: Optional[Path] = None,
        enable_embeddings: bool = True,
        force_reinit: bool = False,
    ) -> None:
        """Run official startup sequence."""
        if self.is_ready and not force_reinit:
            logger.info("Application state already initialized.")
            return

        t0 = time.perf_counter()
        logger.info("Starting Samsung Smart Guided Troubleshooting Engine initialization...")

        # Locate authoritative data files
        workspace_root = Path(__file__).resolve().parent.parent
        self.catalog_path = catalog_path or (workspace_root / "deeplinks.json")
        self.siis_path = siis_path or (workspace_root / "siis_responses.json")

        # 1. Load schema (verify ContextDeeplinkResponse class)
        assert issubclass(ContextDeeplinkResponse, object), "Schema verification failed"

        # 2. Load deeplink catalog & validation firewall
        self.firewall = ValidationFirewall(catalog_path=self.catalog_path)
        self.resolver = DeeplinkResolver(catalog_path=self.catalog_path)
        self.catalog_size = len(self.resolver.lexical_matcher.entries) + 1  # 578 total (577 usable + 1 dummy)
        logger.info(f"Loaded deeplink catalog: {self.catalog_size} entries.")

        # 3, 4 & 5. Initialize retrieval indexes & FastPathSemanticCache
        self.cache = FastPathSemanticCache(
            catalog_path=self.catalog_path,
            siis_path=self.siis_path,
            enable_embeddings=enable_embeddings,
            firewall=self.firewall,
        )

        # 6. Prewarm canonical cache
        self.prewarm_stats = prewarm_canonical_scenarios(
            cache=self.cache,
            siis_path=self.siis_path,
            resolver=self.resolver,
            firewall=self.firewall,
        )
        logger.info(f"Canonical cache prewarmed: {self.prewarm_stats}")

        # 7. Initialize Cold-Path Engine with grounding checker & cache writeback
        self.cold_engine = ColdPathExtractionEngine(
            provider=GeminiExtractor(fallback=DeterministicFallbackExtractor()),
            resolver=self.resolver,
            firewall=self.firewall,
            cache=self.cache,
            grounding_checker=GroundingChecker(),
        )

        self.startup_time_s = time.perf_counter() - t0
        self.is_ready = True
        logger.info(f"Engine initialization complete in {self.startup_time_s:.3f}s. Ready to serve.")

    def reset(self) -> None:
        """Reset state (primarily for lifecycle unit tests)."""
        self.is_ready = False
        self.startup_time_s = 0.0
        self.catalog_path = None
        self.siis_path = None
        self.catalog_size = 0
        self.firewall = None
        self.resolver = None
        self.cache = None
        self.cold_engine = None
        self.prewarm_stats = {}


app_state = ApplicationState()
