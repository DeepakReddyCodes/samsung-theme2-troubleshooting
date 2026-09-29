"""Fast-Path Semantic Cache Layer for Samsung Guided Troubleshooting Engine.

Acceptance SLAs:
- Repeat-query P95 latency <= 300 ms
- Repeat-query cache hit rate >= 90%
- Paraphrase cache hit rate >= 80%
- Cold-start P95 latency <= 8.0 s

Features:
- Dual-tier: Exact SHA-256 Hash (<1ms) + Dense Vector Cosine Similarity (<50ms)
- Context-Aware: Integrates SIIS fingerprint into cache identity
- Validation-Guarded: Stores only firewall-validated ContextDeeplinkResponses
- Version-Managed: Invalidation on catalog, SIIS, schema, or engine updates
- Intent-Safe: Rejects collisions when words are similar but actions conflict
"""
from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

from app.core.firewall import ValidationFirewall
from app.core.schema import ContextDeeplinkResponse

logger = logging.getLogger(__name__)

# Default engine and schema versions
DEFAULT_ENGINE_VERSION = "1.0.0"
DEFAULT_SCHEMA_VERSION = "1.0.0"
DEFAULT_SEMANTIC_THRESHOLD = 0.65

# Domain compound replacements
COMPOUND_MAP = {
    r"\bbackup\b": "back up",
    r"\bwi-fi\b": "wifi",
    r"\bwi fi\b": "wifi",
    r"\btouchscreen\b": "touch screen",
    r"\blockscreen\b": "lock screen",
    r"\bautosync\b": "auto sync",
    r"\bquickshare\b": "quick share",
    r"\bsmartswitch\b": "smart switch",
}

# Distinct intent action stems for intent safety check
INTENT_ACTION_CONFLICTS = {
    "backup": {"restore", "reset", "wipe", "delete", "clear"},
    "restore": {"backup", "reset", "wipe", "delete"},
    "reset": {"backup", "restore", "keep", "save"},
    "enable": {"disable", "turn off", "stop"},
    "disable": {"enable", "turn on", "start"},
}


def normalize_query(query: str) -> str:
    """Normalize query text: strip numbering, quotes, punctuation, domain compounds."""
    if not query:
        return ""
    text = query.strip()
    # Remove leading numbering like '1. ', '1. "', '2. '
    text = re.sub(r"^\d+[\.\)]\s*[\"']?", "", text)
    # Remove trailing quotes
    text = re.sub(r"[\"']\s*$", "", text)
    text = text.lower()

    # Normalize domain compounds
    for pat, rep in COMPOUND_MAP.items():
        text = re.sub(pat, rep, text)

    # Replace punctuation with spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_siis_fingerprint(siis_response: Optional[Union[Dict[str, Any], str]]) -> str:
    """Compute deterministic fingerprint for SIIS context."""
    if not siis_response:
        return "CANONICAL_DEFAULT"

    if isinstance(siis_response, dict):
        title = str(siis_response.get("title", "")).strip().lower()
        content = str(siis_response.get("content", "")).strip().lower()
        title = re.sub(r"\s+", " ", title)
        content = re.sub(r"\s+", " ", content)
        key_content = content[:500]  # First 500 chars captures article context
        payload = f"{title}::{key_content}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    if isinstance(siis_response, str):
        cleaned = re.sub(r"\s+", " ", siis_response.strip().lower()[:500])
        payload = cleaned.encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    return "UNKNOWN_SIIS"


def compute_file_hash(path: Union[str, Path]) -> str:
    """Compute SHA-256 hash of a file for cache versioning."""
    p = Path(path)
    if not p.exists():
        return "MISSING"
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


@dataclass
class CacheEntry:
    """Single cached troubleshooting plan with metadata."""
    key: str
    normalized_query: str
    siis_fingerprint: str
    response: ContextDeeplinkResponse
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0
    intent_vector: Optional[np.ndarray] = None
    scenario_id: Optional[str] = None


class CacheVersionManager:
    """Manages version tokens to invalidate cache when dependencies change."""

    def __init__(
        self,
        catalog_path: Optional[Union[str, Path]] = None,
        siis_path: Optional[Union[str, Path]] = None,
        engine_version: str = DEFAULT_ENGINE_VERSION,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
    ):
        self.engine_version = engine_version
        self.schema_version = schema_version
        self.catalog_path = catalog_path
        self.siis_path = siis_path

        self.catalog_hash = compute_file_hash(catalog_path) if catalog_path else "NO_CATALOG"
        self.siis_hash = compute_file_hash(siis_path) if siis_path else "NO_SIIS"
        self._version_token = self._generate_token()

    def _generate_token(self) -> str:
        payload = f"{self.engine_version}::{self.schema_version}::{self.catalog_hash}::{self.siis_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def version_token(self) -> str:
        return self._version_token

    def check_version(self) -> bool:
        """Verify if current underlying files still match the stored token."""
        curr_cat = compute_file_hash(self.catalog_path) if self.catalog_path else "NO_CATALOG"
        curr_siis = compute_file_hash(self.siis_path) if self.siis_path else "NO_SIIS"
        return curr_cat == self.catalog_hash and curr_siis == self.siis_hash


class FastPathSemanticCache:
    """High-performance dual-tier semantic cache satisfying official P95 <= 300ms SLA."""

    def __init__(
        self,
        catalog_path: Optional[Union[str, Path]] = None,
        siis_path: Optional[Union[str, Path]] = None,
        semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
        engine_version: str = DEFAULT_ENGINE_VERSION,
        schema_version: str = DEFAULT_SCHEMA_VERSION,
        enable_embeddings: bool = True,
        firewall: Optional[ValidationFirewall] = None,
    ):
        self.semantic_threshold = semantic_threshold
        self.version_manager = CacheVersionManager(
            catalog_path=catalog_path,
            siis_path=siis_path,
            engine_version=engine_version,
            schema_version=schema_version,
        )
        self.firewall = firewall or ValidationFirewall(catalog_path=catalog_path)
        self.enable_embeddings = enable_embeddings

        # Tier 1: Exact hash table (key -> CacheEntry)
        self.exact_store: Dict[str, CacheEntry] = {}

        # Tier 2: Semantic vector pool
        self.entries_list: List[CacheEntry] = []
        self.vector_matrix: Optional[np.ndarray] = None

        # Embedding model
        self.model = None
        if self.enable_embeddings:
            self._init_embedding_model()

        # Telemetry metrics
        self.total_lookups = 0
        self.exact_hits = 0
        self.semantic_hits = 0
        self.misses = 0
        self.latencies_ms: List[float] = []

    @staticmethod
    def normalize_query(query: str) -> str:
        return normalize_query(query)

    def _init_embedding_model(self) -> None:
        """Initialize sentence-transformers model for dense semantic caching."""
        try:
            import os
            from sentence_transformers import SentenceTransformer
            logger.info("Initializing SentenceTransformer('all-MiniLM-L6-v2') for semantic cache...")
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except Exception:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.warning(f"Could not load embedding model for cache ({e}). Running in exact-only mode.")
            self.model = None

    def _compute_key(self, norm_query: str, fingerprint: str) -> str:
        """Compute exact cache key."""
        payload = f"{self.version_manager.version_token}::{norm_query}::{fingerprint}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _encode_text(self, text: str) -> Optional[np.ndarray]:
        """Encode text into a normalized dense embedding."""
        if not self.model or not text:
            return None
        try:
            return self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]
        except Exception as e:
            logger.error(f"Encoding error: {e}")
            return None

    def _rebuild_vector_matrix(self) -> None:
        """Rebuild dense embedding matrix from entries."""
        valid_vecs = [e.intent_vector for e in self.entries_list if e.intent_vector is not None]
        if valid_vecs:
            self.vector_matrix = np.vstack(valid_vecs)
        else:
            self.vector_matrix = None

    def _has_intent_conflict(self, query_norm: str, cached_norm: str) -> bool:
        """Safety check to ensure query does not have opposing action intent to cached plan."""
        def _extract_intents(text: str) -> Set[str]:
            intents = set()
            tokens = set(text.split())
            if "restore" in tokens or "recovering" in tokens:
                intents.add("restore")
            if "reset" in tokens or "wipe" in tokens or "factory" in tokens:
                intents.add("reset")
            if "backup" in tokens or ("back" in tokens and "up" in tokens) or "sync" in tokens:
                intents.add("backup")
            if "disable" in tokens or "turn off" in text or "deactivate" in tokens or "remove" in tokens or "delete" in tokens:
                intents.add("disable")
            if "enable" in tokens or "turn on" in text or "activate" in tokens or "add" in tokens or "create" in tokens or "setup" in tokens:
                intents.add("enable")
            if "unlock" in tokens:
                intents.add("unlock")
            elif "lock" in tokens and "screen" not in text:
                intents.add("lock")
            return intents

        q_int = _extract_intents(query_norm)
        c_int = _extract_intents(cached_norm)

        conflicting_pairs = [
            ("backup", "restore"),
            ("backup", "reset"),
            ("restore", "reset"),
            ("enable", "disable"),
            ("lock", "unlock"),
        ]

        for a1, a2 in conflicting_pairs:
            if a1 in c_int and a2 not in c_int and a2 in q_int:
                return True
            if a2 in c_int and a1 not in c_int and a1 in q_int:
                return True
        return False

    def get(
        self,
        query: str,
        siis_response: Optional[Union[Dict[str, Any], str]] = None,
    ) -> Tuple[Optional[ContextDeeplinkResponse], Dict[str, Any]]:
        """Lookup troubleshooting plan by exact match or semantic similarity.
        
        Returns: (ContextDeeplinkResponse or None, telemetry_metadata)
        """
        t0 = time.perf_counter()
        self.total_lookups += 1

        norm_query = normalize_query(query)
        fingerprint = compute_siis_fingerprint(siis_response)
        exact_key = self._compute_key(norm_query, fingerprint)

        # 1. Tier 1: Exact Hash Hit
        if exact_key in self.exact_store:
            entry = self.exact_store[exact_key]
            entry.hit_count += 1
            self.exact_hits += 1
            t_ms = (time.perf_counter() - t0) * 1000.0
            self.latencies_ms.append(t_ms)
            return entry.response, {
                "cache_hit": True,
                "hit_type": "exact",
                "latency_ms": round(t_ms, 3),
                "scenario_id": entry.scenario_id,
                "confidence": 1.0,
            }

        # 2. Tier 2: Semantic Cosine Match
        if self.model and self.vector_matrix is not None and len(self.entries_list) > 0:
            query_vec = self._encode_text(norm_query)
            if query_vec is not None:
                sims = np.dot(self.vector_matrix, query_vec)
                candidate_indices = np.where(sims >= self.semantic_threshold)[0]
                if len(candidate_indices) > 0:
                    sorted_indices = candidate_indices[np.argsort(-sims[candidate_indices])]
                    for idx in sorted_indices:
                        candidate = self.entries_list[int(idx)]
                        best_sim = float(sims[idx])

                        # Strict Context Compatibility:
                        # Candidate SIIS fingerprint MUST match the requested SIIS fingerprint
                        # NEVER allow cross-article matching!
                        if candidate.siis_fingerprint != fingerprint:
                            continue

                        # Intent conflict check
                        if self._has_intent_conflict(norm_query, candidate.normalized_query):
                            continue

                        candidate.hit_count += 1
                        self.semantic_hits += 1
                        t_ms = (time.perf_counter() - t0) * 1000.0
                        self.latencies_ms.append(t_ms)
                        return candidate.response, {
                            "cache_hit": True,
                            "hit_type": "semantic",
                            "latency_ms": round(t_ms, 3),
                            "scenario_id": candidate.scenario_id,
                            "confidence": round(best_sim, 4),
                        }

        # 3. Cache Miss
        self.misses += 1
        t_ms = (time.perf_counter() - t0) * 1000.0
        self.latencies_ms.append(t_ms)
        return None, {
            "cache_hit": False,
            "hit_type": "miss",
            "latency_ms": round(t_ms, 3),
            "scenario_id": None,
            "confidence": 0.0,
        }

    def put(
        self,
        query: str,
        response: ContextDeeplinkResponse,
        siis_response: Optional[Union[Dict[str, Any], str]] = None,
        scenario_id: Optional[str] = None,
        validate: bool = True,
        intent_vector: Optional[np.ndarray] = None,
        rebuild_matrix: bool = True,
    ) -> bool:
        """Store a validated ContextDeeplinkResponse in the cache."""
        # Enforce validation firewall before storing
        if validate:
            validated_resp, errors = self.firewall.validate_response(response, allow_repair=True)
            if errors:
                logger.error(f"Cannot cache invalid response: {errors}")
                return False
            final_response = validated_resp
        else:
            final_response = response

        norm_query = normalize_query(query)
        fingerprint = compute_siis_fingerprint(siis_response)
        exact_key = self._compute_key(norm_query, fingerprint)

        # Use pre-computed intent vector if provided, else compute
        if intent_vector is not None:
            intent_vec = intent_vector
        else:
            intent_vec = self._encode_text(norm_query) if self.model else None

        entry = CacheEntry(
            key=exact_key,
            normalized_query=norm_query,
            siis_fingerprint=fingerprint,
            response=final_response,
            intent_vector=intent_vec,
            scenario_id=scenario_id,
        )

        self.exact_store[exact_key] = entry
        self.entries_list.append(entry)

        if rebuild_matrix and intent_vec is not None:
            self._rebuild_vector_matrix()

        return True

    def invalidate(self, reason: str = "manual") -> None:
        """Invalidate all cached entries."""
        logger.info(f"Invalidating fast-path cache. Reason: {reason}")
        self.exact_store.clear()
        self.entries_list.clear()
        self.vector_matrix = None

    def get_stats(self) -> Dict[str, Any]:
        """Compute performance percentiles and cache statistics."""
        latencies = sorted(self.latencies_ms) if self.latencies_ms else [0.0]
        n = len(latencies)
        p50 = latencies[int(n * 0.50)] if n > 0 else 0.0
        p95 = latencies[min(int(n * 0.95), n - 1)] if n > 0 else 0.0
        p99 = latencies[min(int(n * 0.99), n - 1)] if n > 0 else 0.0

        hit_count = self.exact_hits + self.semantic_hits
        hit_rate = (hit_count / self.total_lookups) if self.total_lookups > 0 else 0.0

        return {
            "total_lookups": self.total_lookups,
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 4),
            "cached_entries_count": len(self.exact_store),
            "p50_latency_ms": round(p50, 3),
            "p95_latency_ms": round(p95, 3),
            "p99_latency_ms": round(p99, 3),
            "version_token": self.version_manager.version_token,
            "has_embeddings": self.model is not None,
        }
