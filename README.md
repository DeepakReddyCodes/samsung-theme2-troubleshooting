<p align="center">
  <h1 align="center">🔧 Samsung Smart Guided Troubleshooting Engine</h1>
  <p align="center">
    <strong>Samsung PRISM GenAI Hackathon Y2026 — Theme 02</strong><br>
    <em>Intelligent, Low-Latency Diagnostic Reasoning for Samsung Galaxy Devices</em>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react" alt="React">
  <img src="https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?logo=google" alt="Gemini">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/License-Hackathon-orange" alt="License">
</p>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Innovation: Next-Best-Evidence (NBE)](#-key-innovation-next-best-evidence-nbe)
- [Architecture](#-architecture)
- [Features](#-features)
- [Performance Benchmarks](#-performance-benchmarks)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Configuration](#environment-configuration)
  - [Running the Application](#running-the-application)
- [Docker Deployment](#-docker-deployment)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Project Structure](#-project-structure)
- [Dataset Files](#-dataset-files)
- [Architectural Deep Dive](#-architectural-deep-dive)
- [Evaluation Metrics](#-evaluation-metrics)
- [Live Demo Flow](#-live-demo-flow)
- [Limitations](#-limitations)
- [License](#-license)

---

## 🌟 Overview

Modern device troubleshooting suffers from **high cognitive load**, **fragmented Settings menus**, and **AI hallucinations** (invented steps, invalid URLs, fabricated deeplinks). This project delivers a production-grade engine that solves all three.

The **Samsung Smart Guided Troubleshooting Engine** ingests natural language device complaints along with authoritative Samsung Internal Information Store (SIIS) articles and produces:

- ✅ **Structured, step-by-step diagnostic workflows** grounded strictly in SIIS evidence
- ✅ **Verbatim Samsung OneUI Settings deeplinks** (`bixby://...`) from a 578-entry catalog
- ✅ **Sub-millisecond repeat-query responses** via a dual-tier semantic cache
- ✅ **Zero hallucinations** — every action is traceable to source evidence
- ✅ **Zero web URL leaks** — no `http://`, `https://`, or `www.` in any response

---
Youtube  Demo link: https://youtu.be/LECs04dMLfk



## 🧠 Key Innovation: Next-Best-Evidence (NBE)

Our primary differentiator is the **Next-Best-Evidence (NBE)** engine — an information-theoretic diagnostic optimizer that goes beyond static troubleshooting by actively reasoning about *which diagnostic action provides the most value*.

### How NBE Works

```
                    ┌─────────────────────────┐
                    │   Hypothesis Space H    │
                    │  h₁: WiFi config issue  │
                    │  h₂: Hardware failure   │
                    │  h₃: Software bug       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Shannon Entropy H(H)   │
                    │  Measures diagnostic    │
                    │  uncertainty (bits)     │
                    └────────────┬────────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               ▼                 ▼                  ▼
    ┌──────────────────┐ ┌───────────────┐ ┌───────────────────┐
    │ Evidence E₁      │ │ Evidence E₂   │ │ Evidence E₃       │
    │ Check WiFi       │ │ Restart Phone │ │ Factory Reset     │
    │ Cost: Low        │ │ Cost: Medium  │ │ Cost: High        │
    └────────┬─────────┘ └───────┬───────┘ └─────────┬─────────┘
             │                   │                    │
             ▼                   ▼                    ▼
    ┌─────────────────────────────────────────────────────────┐
    │        Expected Information Gain (EIG) Ranking          │
    │                                                         │
    │  EIG(E) = H(H) - E_e[ H(H | E=e) ]                    │
    │  Utility(E) = (EIG(E) / Cost(E)) × Availability(E)    │
    │                                                         │
    │  → Select E₁ (highest utility-to-cost ratio)           │
    └─────────────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────┐
    │  Bayesian Posterior     │
    │  Update: P(h|E=e)      │
    │  → Reassess sufficiency │
    │  → Resolve or continue  │
    └─────────────────────────┘
```

### NBE Mathematical Foundation

| Component | Formula | Purpose |
|---|---|---|
| **Shannon Entropy** | `H(H) = -Σ P(hᵢ) × log₂(P(hᵢ))` | Measures total diagnostic uncertainty |
| **Expected Information Gain** | `EIG(E) = H(H) - E[H(H\|E=e)]` | Expected uncertainty reduction from evidence |
| **Bayesian Posterior** | `P(hᵢ\|E=e) = P(E=e\|hᵢ)P(hᵢ) / P(E=e)` | Updated beliefs after observing evidence |
| **Cost-Aware Utility** | `U(E) = (EIG(E) / Cost(E)) × Avail(E)` | Balances information gain against user effort |

### Why NBE Matters

Traditional troubleshooting engines present actions in a **fixed order** regardless of the specific complaint. NBE dynamically reorders diagnostic steps to:

1. **Minimize user effort** — cheapest, most informative actions first
2. **Maximize diagnostic resolution speed** — each step maximally reduces uncertainty
3. **Handle ambiguous complaints** — multi-symptom queries are disambiguated via entropy analysis
4. **Provide deterministic, reproducible rankings** — no randomness, fully traceable decisions

The NBE subsystem is implemented in [`codebase/app/services/nbe/`](codebase/app/services/nbe/) with 15 dedicated tests covering entropy calculation, EIG computation, Bayesian updates, cost-aware utility, tie-breaking, and the full decision loop state machine.

---

## 🏗 Architecture

```
                                  [ User Request ]
                           (Query + SIIS Context Object)
                                         │
                                         ▼
                     ┌───────────────────────────────────────┐
                     │          FastAPI Application          │
                     │         POST /v1/troubleshoot         │
                     └───────────────────┬───────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │  Query Enrichment   │
                              │  (Stage 1 LLM)      │
                              │  - Normalization     │
                              │  - Polarity detect   │
                              │  - Entity extraction │
                              └──────────┬──────────┘
                                         │
                     ┌───────────────────────────────────────┐
                     │    Fast-Path Semantic Cache Layer     │
                     │  - Tier 1: SHA-256 Exact Context Key  │
                     │  - Tier 2: Sentence-Transformer Dense │
                     │  - SIIS Fingerprint & Polarity Guard  │
                     └───────┬───────────────────────┬───────┘
                      HIT    │                       │ MISS
                             │                       ▼
                             │      ┌─────────────────────────────────┐
                             │      │  Cold-Path Knowledge Extractor  │
                             │      │  ┌─────────────────────────┐    │
                             │      │  │ Gemini Two-Stage LLM    │    │
                             │      │  │ + Grounding Checker     │    │
                             │      │  └──────────┬──────────────┘    │
                             │      │        pass │ fail              │
                             │      │             │  ↓                │
                             │      │  ┌──────────┴──────────────┐    │
                             │      │  │ Deterministic Fallback  │    │
                             │      │  │ (Zero-downtime SIIS)    │    │
                             │      │  └─────────────────────────┘    │
                             │      └────────────────┬────────────────┘
                             │                       │
                             │      ┌────────────────▼────────────────┐
                             │      │   NBE / EIG Action Optimizer   │
                             │      │   (Bayesian evidence ranking)   │
                             │      └────────────────┬────────────────┘
                             │                       │
                             │      ┌────────────────▼────────────────┐
                             │      │    Deeplink Catalog Resolver    │
                             │      │  - 578 Authoritative URIs       │
                             │      │  - Lexical + Semantic Matching  │
                             │      │  - Verbatim Copying & Fallback  │
                             │      └────────────────┬────────────────┘
                             │                       │
                             ▼                       ▼
                     ┌───────────────────────────────────────┐
                     │       Zero-Bypass Validation          │
                     │              Firewall                 │
                     │  - Schema Invariants & Regex Formats  │
                     │  - Action Ordering (auto→manual→crit) │
                     │  - Zero-URL Leak Sanitizer            │
                     └───────────────────┬───────────────────┘
                                         │
                                         ▼
                             [ ContextDeeplinkResponse ]
```

---

## ✨ Features

### Core Engine
| Feature | Description |
|---|---|
| **Two-Stage LLM Pipeline** | Stage 1 (Query Enrichment) normalizes and classifies complaints. Stage 2 (Extraction) produces structured troubleshooting plans with evidence references. |
| **SIIS Grounding Checker** | Every extracted action is verified against SIIS source text. Unsupported claims are rejected, not hallucinated. |
| **Deterministic Fallback** | When Gemini API is unavailable or returns ungroundable output, a zero-downtime rules-based extractor processes SIIS directly. |
| **Deeplink Catalog Resolver** | Dual-pass lexical + dense semantic matching against 578 Samsung OneUI deeplinks with confidence gating. |
| **Validation Firewall** | Zero-bypass schema enforcer: Goal titles (2–3 words), descriptions (5–7 words, "It will…"), action ordering (`auto` → `manual` → `critical`), URL leak prevention. |

### Innovation Layer
| Feature | Description |
|---|---|
| **Next-Best-Evidence (NBE)** | Bayesian information-theoretic engine that optimally sequences diagnostic actions by maximizing entropy reduction per unit cost. |
| **Expected Information Gain (EIG)** | Calculates the expected Shannon entropy reduction for each candidate diagnostic step. |
| **Cost-Aware Utility** | Weighs information gain against action cost (user effort, time) and availability to select the most efficient next step. |
| **Multi-Turn Decision Loop** | State machine managing iterative evidence acquisition with sufficiency reassessment after each observation. |

### Performance & Caching
| Feature | Description |
|---|---|
| **Dual-Tier Semantic Cache** | Tier 1: SHA-256 exact hash. Tier 2: `all-MiniLM-L6-v2` dense vectors with cosine similarity. |
| **SIIS Context Isolation** | SHA-256 fingerprinting prevents cross-article cache contamination. |
| **Polarity Guard** | Detects opposing intents (`enable`/`disable`, `backup`/`restore`) to prevent cache collisions. |
| **Sub-300ms P95** | Exact hits in < 1ms, semantic hits in ~15ms, cold-path in ~39ms. |

### Frontend
| Feature | Description |
|---|---|
| **Interactive Troubleshooter** | Enter complaints, view structured diagnostic workflows, inspect deeplinks. |
| **Evaluator Dashboard** | Real-time KPI cards, telemetry HUD, cache statistics, historical query log. |
| **Export Functionality** | Download `output.json` and `results.jsonl` submission artifacts directly from the UI. |

---

## 📊 Performance Benchmarks

| Metric | Target | Achieved |
|---|---|---|
| Repeat query P95 latency | ≤ 300 ms | **< 1.0 ms** ✅ |
| Repeat query cache hit rate | ≥ 90% | **100.0%** ✅ |
| Paraphrase semantic hit rate | ≥ 80% | **92.5%** ✅ |
| Paraphrase P95 latency | ≤ 300 ms | **~56 ms** ✅ |
| Cold-path P95 latency | ≤ 8,000 ms | **~39 ms** ✅ |
| Startup / prewarming | ≤ 8,000 ms | **~6.4 s** ✅ |
| Schema-valid output | ≥ 99% | **100.0%** ✅ |
| Web URL leaks | 0 | **0** ✅ |
| Fabricated deeplinks | 0 | **0** ✅ |

### Architectural Ablation

| Variant | Step Accuracy | P95 Latency | Cost/Query | Notes |
|---|:---:|:---:|:---:|---|
| **Baseline: Full LLM Mapping** | 2.1 | 4,200 ms | $0.0042 | Hallucinates URIs, high latency |
| **Ours: Hybrid BM25 + Dense** | **3.0** | **56 ms** | **$0.0000** | 100% valid catalog URIs |
| Pure Rules-Based | 2.4 | 12 ms | $0.0000 | Misses colloquial phrasings |

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version | Required |
|---|---|---|
| Python | 3.10+ | ✅ |
| Node.js | 18+ | ✅ (for frontend build) |
| npm | 9+ | ✅ (for frontend build) |
| Docker | 20+ | Optional |
| Gemini API Key | — | Optional (deterministic fallback works without it) |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/samsung-theme2-troubleshooting.git
cd samsung-theme2-troubleshooting

# 2. Create and activate a Python virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Install Python dependencies
cd codebase
pip install -r requirements.txt

# 4. Install frontend dependencies (optional — pre-built assets included)
cd frontend
npm install
cd ..
```

### Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Google Gemini API (Optional — engine runs fully without it using deterministic fallback)
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# System Settings
ENGINE_VERSION=1.0.0
SCHEMA_VERSION=1.0.0
SEMANTIC_CACHE_THRESHOLD=0.65
DEEPLINK_CONFIDENCE_THRESHOLD=0.35
```

| Variable | Required | Default | Description |
|:---|:---:|:---:|:---|
| `GEMINI_API_KEY` | Optional | `""` | Google Gemini API key. If omitted, engine runs in deterministic fallback mode with zero downtime. |
| `GEMINI_MODEL` | Optional | `gemini-2.5-flash` | Gemini model identifier for cold-path reasoning. |
| `ENGINE_VERSION` | Optional | `1.0.0` | Semantic version token for cache invalidation on engine updates. |
| `SEMANTIC_CACHE_THRESHOLD` | Optional | `0.65` | Cosine similarity threshold for Tier-2 semantic cache hits. |
| `DEEPLINK_CONFIDENCE_THRESHOLD` | Optional | `0.35` | Minimum similarity to bind a catalog deeplink. |

### Running the Application

#### Option A: Backend + Frontend (Unified)

The FastAPI backend serves the pre-compiled React frontend at the root URL:

```bash
cd codebase

# Build frontend (if not pre-built)
cd frontend && npm run build && cd ..

# Start the unified server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/** — the complete application is served from a single port.

#### Option B: Development Mode (Hot-Reloading)

**Terminal 1 — Backend:**
```bash
cd codebase
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd codebase/frontend
npm run dev
```

Open **http://localhost:5173/** (frontend dev server with API proxy to port 8000).

#### Option C: Quick Verification

```bash
cd codebase

# Start the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &

# Health check
curl http://127.0.0.1:8000/health

# Test a troubleshooting query
curl -X POST "http://127.0.0.1:8000/v1/troubleshoot" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "My Samsung phone screen keeps going dark",
       "siis_response": {
         "title": "Screen timeout settings on Galaxy device",
         "content": "Navigate to Settings, then tap Display, then Screen timeout to adjust."
       }
     }'
```

---

## 🐳 Docker Deployment

### Using Docker Build

```bash
cd codebase

# Build the multi-stage Docker image (includes frontend compilation)
docker build -t samsung-smartguide:latest .

# Run the container
docker run -p 8000:8000 \
  -e GEMINI_API_KEY="" \
  samsung-smartguide:latest
```

### Using Docker Compose

```bash
cd codebase

# Create .env file with your configuration (optional)
cp .env.example .env

# Build and start
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

Access the application at **http://localhost:8000/**.

### Dockerfile Architecture

The Dockerfile uses a **multi-stage build**:
1. **Stage 1** (`node:20-slim`): Compiles the React/Vite frontend into production assets.
2. **Stage 2** (`python:3.11-slim`): Installs Python dependencies, copies backend code + compiled frontend, and starts Uvicorn.
3. **Health check**: Built-in Docker `HEALTHCHECK` pings `/health` every 30 seconds.

---

## 📡 API Reference

### `GET /health` — Health Check

```json
{
  "status": "ok",
  "ready": true,
  "version": "1.0.0",
  "catalog_size": 578,
  "cache_entries": 40,
  "startup_time_s": 1.398
}
```

### `POST /v1/troubleshoot` — Diagnostic Engine

**Request:**
```json
{
  "query": "My Samsung A115G tablet screen flashes and goes blank when opening Gmail",
  "siis_response": {
    "title": "Email server not responding on Samsung phone or tablet",
    "content": "Verify your internet connection. Swipe down to open Quick settings, tap Connections, then tap Wi-Fi."
  }
}
```

**Response:**
```json
{
  "contexts": [
    {
      "goal": "Follow these steps to perform this Email Connection Troubleshooting",
      "title": "Email server connection",
      "score": 0.95,
      "actions": [
        {
          "actionName": "Check Wifi Network Settings",
          "description": "It will check your wifi connection status",
          "category": "auto",
          "stepGroups": [
            {
              "steps": [
                "Navigate to and open Settings.",
                "Tap on Connections, then tap Wi-Fi.",
                "Verify active Wi-Fi connection status."
              ],
              "actionableDeeplink": {
                "deeplink": "bixby://masked/act/b3ed3ed663",
                "description": "Opens Wi-Fi settings on the device.",
                "message": "Enable Wi-Fi",
                "originalType": "onURL"
              },
              "validationDeeplink": null
            }
          ]
        }
      ]
    }
  ]
}
```

**Response Headers:**

| Header | Description |
|---|---|
| `X-Process-Time-Ms` | Server execution duration in milliseconds |
| `X-Cache-Hit` | `true` or `false` |
| `X-Cache-Type` | `exact`, `semantic`, or `miss` |
| `X-Extraction-Path` | `fast_path_exact`, `fast_path_semantic`, or `cold_path` |
| `X-NBE-Entropy` | Current diagnostic entropy (bits) |
| `X-NBE-Top-Evidence` | Highest EIG evidence identifier |

### `GET /v1/export/output.json` — Download Output Artifact

Returns the full `output.json` submission artifact.

### `GET /v1/export/results.jsonl` — Download Results Artifact

Returns the `results.jsonl` benchmark artifact.

---

## 🧪 Testing

### Full Backend Test Suite

```bash
cd codebase
python -m pytest tests/ -v
```

This runs **130+ tests** across:

| Suite | File | Focus |
|---|---|---|
| API Contract & Acceptance | `tests/test_api.py` | Schema, URI integrity, URL leaks, cache, cold path |
| Validation Firewall | `tests/test_firewall.py` | Goal/title/description format, ordering, sanitization |
| Deeplink Resolution | `tests/test_deeplinks.py` | Catalog matching, confidence gate, fallback policy |
| Semantic Cache | `tests/test_cache.py` | Exact/semantic hits, latency benchmarks, isolation |
| Two-Stage Gemini LLM | `tests/test_gemini_two_stage.py` | Mock/live LLM, fallbacks, JSON repair, hallucination blocking |
| NBE & Information Theory | `tests/test_nbe.py` | Shannon entropy, EIG, Bayesian updates, decision loop |
| Query Enrichment | `tests/test_query_enrichment.py` | Normalization, polarity, entity extraction |
| Extraction Engine | `tests/test_extraction.py` | Deterministic extraction, grounding verification |
| Contract Compliance | `tests/compliance/test_contracts.py` | Response schema, field validation |
| Grounding Invariants | `tests/compliance/test_grounding.py` | SIIS evidence traceability |
| Generalization | `tests/compliance/test_generalization.py` | Unseen SIIS articles |
| Adversarial Resilience | `tests/compliance/test_adversarial.py` | Prompt injection, polarity attacks |
| Cache Isolation | `tests/compliance/test_cache_isolation.py` | Cross-article contamination prevention |
| Deeplink Policy | `tests/compliance/test_deeplink_policy.py` | Catalog integrity, dummy_positive policy |
| Frontend Integration | `tests/test_frontend_integration.py` | API-to-UI contract |

### Frontend Test Suite

```bash
cd codebase/frontend
npm test
```

Runs **11 tests** covering typed API handling, response parsing, telemetry HUD, and responsive styles.

### Benchmarking

```bash
cd codebase
python scripts/benchmark_engine.py
```

Generates `results/benchmark_metrics.json` with:
- Startup/prewarming latency
- 100 repeated canonical queries (P50/P95/P99, hit rate)
- 200 diverse paraphrases (P50/P95/P99, hit rate)
- 12 unseen generalization scenarios
- 12-gate schema & quality validation

### Generate Submission Artifacts

```bash
cd codebase
python scripts/generate_results.py
```

Produces `output.json` and `results/results.jsonl`.

---

## 📁 Project Structure

```
samsung-theme2-troubleshooting/
│
├── README.md                              # This file
├── requirements.txt                       # Python dependencies
├── metrics.md                             # Performance metrics report (Appendix C)
│
├── docs/
│   ├── IMPLEMENTATION.md                  # Architecture blueprint & implementation guide
│   └── REQUIREMENTS_TRACEABILITY.md       # Samsung requirements → code → test mapping
│
└── codebase/
    ├── app/
    │   ├── main.py                        # FastAPI service, lifecycle, static mounting
    │   ├── state.py                       # Application startup singleton & orchestration
    │   ├── api/
    │   │   └── schemas.py                 # Pydantic request/response DTOs
    │   ├── core/
    │   │   ├── schema.py                  # ContextDeeplinkResponse model (frozen contract)
    │   │   ├── firewall.py                # Zero-bypass validation firewall
    │   │   ├── sanitizer.py               # URL leak detection & text sanitization
    │   │   └── rewrite_controller.py      # Format-only title/description rewriting
    │   ├── cache/
    │   │   ├── semantic_cache.py          # Dual-tier (exact + semantic) cache engine
    │   │   └── prewarm.py                 # Startup cache prewarming from SIIS scenarios
    │   └── services/
    │       ├── extractor/
    │       │   ├── engine.py              # Cold-path pipeline orchestrator
    │       │   ├── gemini_extractor.py     # Gemini LLM structured extraction (Stage 2)
    │       │   ├── deterministic_extractor.py  # Rules-based SIIS fallback
    │       │   ├── grounding_checker.py   # Claim-level SIIS evidence verification
    │       │   └── base.py                # Extractor interface definitions
    │       ├── query_enrichment/
    │       │   ├── gemini_enricher.py      # Gemini LLM query enrichment (Stage 1)
    │       │   ├── deterministic_enricher.py  # Rules-based enrichment fallback
    │       │   ├── normalizer.py          # Technical terminology normalization
    │       │   ├── polarity.py            # Intent polarity detection (enable/disable)
    │       │   ├── enricher.py            # Enrichment facade
    │       │   └── models.py              # Enrichment data models
    │       ├── nbe/                        # ⭐ Next-Best-Evidence Innovation
    │       │   ├── engine.py              # NBE orchestration engine
    │       │   ├── eig_calculator.py      # Shannon entropy & EIG computation
    │       │   ├── decision_loop.py       # Multi-turn Bayesian state machine
    │       │   └── models.py              # Hypothesis, CandidateEvidence, NBEResult
    │       ├── deeplink_matcher.py        # Dual-pass catalog deeplink resolver
    │       ├── fallback_resolver.py       # dummy_positive fallback policy
    │       └── retriever/
    │           ├── lexical_matcher.py      # BM25-style metadata retrieval
    │           └── semantic_matcher.py     # Dense vector semantic retrieval
    │
    ├── frontend/                           # React + Vite + TypeScript dashboard
    │   ├── src/
    │   │   ├── components/                # TroubleshootingView, DashboardView, ActionCard
    │   │   ├── services/api.ts            # API client with typed responses
    │   │   └── styles/                    # CSS design system
    │   └── tests/                         # Frontend test suite
    │
    ├── tests/                              # Backend test suites
    │   ├── compliance/                    # Contract, grounding, adversarial, isolation tests
    │   ├── test_api.py                    # API acceptance tests
    │   ├── test_cache.py                  # Cache latency benchmarks
    │   ├── test_nbe.py                    # NBE/EIG information theory tests
    │   ├── test_gemini_two_stage.py       # LLM pipeline tests
    │   └── ...
    │
    ├── scripts/                            # Benchmarking & evaluation scripts
    │   ├── benchmark_engine.py            # Full benchmark suite
    │   ├── generate_results.py            # Submission artifact generator
    │   └── audit_urls_and_deeplinks.py    # URL/deeplink integrity audit
    │
    ├── results/                            # Generated benchmark artifacts
    │   ├── results.jsonl                  # 20-scenario evaluation results
    │   ├── output.json                    # Full submission output
    │   └── benchmark_metrics.json         # Performance metrics
    │
    ├── deeplinks.json                      # 578-entry Samsung OneUI deeplink catalog
    ├── siis_responses.json                 # 20 canonical SIIS articles
    ├── input.txt                           # 20 canonical evaluation queries
    ├── sample_output.json                  # Authoritative schema reference
    ├── schema.py                           # Pydantic schema contract
    ├── requirements.txt                    # Python dependencies
    ├── Dockerfile                          # Multi-stage production Docker image
    ├── docker-compose.yml                  # Docker Compose orchestration
    ├── .env.example                        # Environment variable template
    ├── FINAL_VERIFICATION_REPORT.md        # Complete verification report
    └── RELEASE_TAG.md                      # Release metadata
```

---

## 📦 Dataset Files

| File | Description | Entries |
|---|---|---|
| `deeplinks.json` | Authoritative Samsung OneUI Settings deeplink catalog with validation triggers | 578 URIs |
| `siis_responses.json` | Samsung Internal Information Store articles (Galaxy S-series, Z Fold/Flip, Tab, OneUI) | 20 articles |
| `input.txt` | Canonical evaluator user problem queries | 20 queries |
| `sample_output.json` | Authoritative baseline schema reference from Samsung | 1 example |
| `schema.py` | Pydantic contract: `ContextDeeplinkResponse`, `Goal`, `Action`, `StepGroup`, `Deeplink`, `ValidationDeepLink` | — |

---

## 🔍 Architectural Deep Dive

### 1. Query Enrichment (Stage 1)

Converts vague user complaints into normalized technical queries:
- **Terminology normalization**: "screen went black" → "display failure / black screen"
- **Polarity detection**: Distinguishes "enable WiFi" vs "disable WiFi"
- **Entity extraction**: Identifies device models, Samsung features, Settings paths
- **Dual provider**: Gemini LLM or deterministic rules-based fallback

### 2. Grounded Extraction (Stage 2)

Extracts structured troubleshooting workflows strictly from SIIS evidence:
- **Evidence-backed actions**: Each action must cite supporting SIIS text
- **Grounding checker**: Post-LLM verification layer that rejects unsupported claims
- **Malformed JSON recovery**: Automatic repair of incomplete LLM JSON outputs
- **Deterministic fallback**: Regex-based SIIS parsing when LLM is unavailable

### 3. Deeplink Catalog Resolution

Maps diagnostic actions to Samsung OneUI Settings deeplinks:
- **Lexical retrieval**: TF-IDF over catalog metadata (description, message, Q&A)
- **Semantic retrieval**: `all-MiniLM-L6-v2` dense embeddings for colloquial matches
- **Confidence gating**: Below-threshold results use grounded `bixby://dummy_positive` fallback
- **Verbatim copying**: Catalog URIs are never modified, only copied exactly

### 4. Dual-Tier Semantic Cache

Achieves sub-millisecond repeat-query responses:
- **Tier 1 (Exact)**: `SHA-256(normalized_query + SIIS_hash + engine_version + catalog_version)`
- **Tier 2 (Semantic)**: Dense vector cosine similarity with SIIS fingerprint guard
- **Polarity guard**: Prevents cache collisions between opposing intents
- **Version invalidation**: Engine or catalog updates automatically invalidate stale entries

### 5. Validation Firewall

Zero-bypass schema enforcement on every response:
- Goal title: 2–3 words
- Action description: 5–7 words, starts with "It will"
- Category ordering: `auto` → `manual` → `critical`
- Web URL leak detection: Blocks `http://`, `https://`, `www.`, markdown links
- Deeplink integrity: Validates against catalog or sanctioned fallback patterns

---

## 📈 Evaluation Metrics

Detailed metrics are available in [`metrics.md`](metrics.md), following the official Appendix C template.

| Category | Key Metric | Value |
|---|---|---|
| **Compliance** | Schema-valid outputs | 100.0% |
| **Compliance** | Rule compliance (title/description syntax) | 100.0% |
| **Compliance** | URL leaks | 0 |
| **Accuracy** | Step accuracy (vs. ground truth) | 3.0 / 3.0 |
| **Accuracy** | Deeplink relevance | 2.0 / 2.0 |
| **Latency** | Cache hit - exact P95 | 1.24 ms |
| **Latency** | Cache hit - semantic P95 | 55.92 ms |
| **Latency** | Cold path P95 | 38.80 ms |
| **Cost** | Cache hit inference cost | $0.00 |
| **Cost** | Cold path inference cost (deterministic) | $0.00 |
| **Cost** | Cold path inference cost (Gemini LLM) | ~$0.0003 |

---

## 🎬 Live Demo Flow

1. **Health Check**: Navigate to `http://127.0.0.1:8000/health` — verify `"ready": true, "catalog_size": 578`.
2. **Interactive Troubleshooter**: Select a scenario, click **Run Instant Diagnosis** — observe < 1ms exact cache hit.
3. **Paraphrase Test**: Click a paraphrase variant — observe ~15ms `SEMANTIC HIT` with live telemetry.
4. **Cross-Article Safety**: Same query with different SIIS article — observe clean cache miss and fresh extraction.
5. **Unseen Generalization**: Enter a novel complaint — observe cold-path extraction in ~35ms.
6. **Evaluator Dashboard**: View real-time KPIs: 100% hit rate, 92.5% paraphrase rate, sub-ms P95, telemetry log.
7. **Export Artifacts**: Download `output.json` and `results.jsonl` for official submission.

---

## ⚠️ Limitations

1. **Deeplink Execution**: `bixby://masked/...` URIs execute only on physical Samsung Galaxy devices running OneUI. On non-Samsung devices, the UI provides a deeplink inspector with manual step-by-step fallback.
2. **Token Limits**: Extremely large SIIS articles (>20,000 characters) are automatically truncated to the most relevant diagnostic sections.
3. **Rate Limits**: Cloud Gemini API calls may hit `429 RESOURCE_EXHAUSTED` under heavy load — the system gracefully falls back to deterministic processing.
4. **Catalog Coverage**: Some OS features mentioned in Samsung support articles have no corresponding leaf URI in `deeplinks.json` — these use the sanctioned `dummy_positive` fallback with a concrete Settings screen reference.

---

## 📄 License

This project was developed for the **Samsung PRISM GenAI Hackathon Y2026 (Theme 02)**.

---

<p align="center">
  <strong>Built with ❤️ for Samsung PRISM GenAI Hackathon Y2026</strong>
</p>
