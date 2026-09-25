# Samsung Smart Guided Troubleshooting Engine
**Samsung PRISM GenAI Hackathon Y2026 — Theme 02**

An ultra-low latency, schema-validated, intelligent diagnostic reasoning system designed for Samsung Galaxy devices. The engine ingests user troubleshooting complaints along with authoritative Samsung Internal Information Store (SIIS) articles, delivering actionable, step-by-step diagnostic workflows paired with verbatim Samsung Galaxy OneUI Settings deeplinks (`bixby://...`).

---

## 1. Project Purpose
Modern device troubleshooting frequently suffers from high user cognitive load, fragmented Settings menus, and conversational AI hallucinations (invented steps or invalid web URLs). 

This project provides a high-reliability, production-grade engine that:
1. **Enforces Strict SIIS Grounding**: Derives troubleshooting actions and steps strictly from authoritative SIIS articles without inventing nonexistent procedures.
2. **Guarantees Schema Compliance**: Validates all diagnostic responses against the authoritative `ContextDeeplinkResponse` schema via a zero-bypass **Validation Firewall**.
3. **Achieves Ultra-Low Latency via Dual-Tier Fast-Path Cache**:
   - P95 repeat query latency: **< 1.0 ms** (Target: $\le 300\text{ ms}$).
   - Canonical repeat cache hit rate: **100.0%** (Target: $\ge 90\%$).
   - Paraphrase semantic cache hit rate: **92.5%** (Target: $\ge 80\%$).
4. **Protects Deep Link Integrity & Eliminates Web URL Leaks**:
   - Verbatim retrieval from the 578-entry `deeplinks.json` catalog.
   - Zero web URL leaks (`http://`, `https://`, `www.`, markdown links) across all responses.
   - Grounded `bixby://dummy_positive` fallback with concrete Settings screen references when catalog confidence is low.

---

## 2. Architecture

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
                                         ▼
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
                             │      │  - Gemini Generative Extractor  │
                             │      │  - Deterministic Fallback Model │
                             │      │  - Grounding Checker & Filter   │
                             │      └────────────────┬────────────────┘
                             │                       │
                             │                       ▼
                             │      ┌─────────────────────────────────┐
                             │      │    Deeplink Catalog Resolver    │
                             │      │  - 578 Authoritative URIs       │
                             │      │  - Semantic & Polarity Matching │
                             │      │  - Verbatim Copying & Fallback  │
                             │      └────────────────┬────────────────┘
                             │                       │
                             ▼                       ▼
                     ┌───────────────────────────────────────┐
                     │       Zero-Bypass Validation          │
                     │              Firewall                 │
                     │  - Schema Invariants & Regex Formats  │
                     │  - Action Ordering (auto/man/crit)    │
                     │  - Zero-URL Leak Sanitizer            │
                     └───────────────────┬───────────────────┘
                                         │
                                         ▼
                             [ ContextDeeplinkResponse ]
```

### Core Architectural Layers
1. **Validation Firewall (`app/core/firewall.py`)**: Authoritative schema validator and security boundary. Guarantees word counts (Title: 2–3 words, Description: 5–7 words starting with "It will"), Goal regex compliance, action ordering (`auto` $\to$ `manual` $\to$ `critical`), and zero URL leaks.
2. **Deeplink Resolver (`app/services/deeplink_matcher.py`)**: Dual-pass lexical and dense semantic matcher binding step groups to verbatim `bixby://` catalog entries. Preserves validation metadata (`key`, `resultType`, `condition`, `value`) without hallucination.
3. **Fast-Path Semantic Cache (`app/cache/semantic_cache.py`)**: Dual-tier exact and dense vector cache using `sentence-transformers/all-MiniLM-L6-v2`. Protects against cross-article false positives via SHA-256 SIIS fingerprinting and opposing intent detection (`enable` vs `disable`, `backup` vs `restore`).
4. **Cold-Path Generalization Engine (`app/services/extractor/engine.py`)**: Extracts structured diagnostic plans from unseen SIIS articles using Google Gemini with an automated, zero-downtime deterministic fallback engine.

---

## 3. Dataset Files
- **`deeplinks.json`**: Authoritative Samsung OneUI Deeplink Catalog containing 578 valid device settings URIs and associated validation triggers.
- **`siis_responses.json`**: 20 canonical Samsung Internal Information Store articles across multiple device categories (Galaxy S-series, Z Fold/Flip, Galaxy Tab, OneUI).
- **`input.txt`**: The 20 canonical evaluator user problem queries.
- **`sample_output.json`**: Authoritative baseline schema reference.
- **`schema.py`**: Pydantic schema contract defining `ContextDeeplinkResponse`, `Goal`, `Action`, `StepGroup`, `ActionableDeeplink`, and `ValidationDeeplink`.

---

## 4. Installation

### Prerequisites
- Python 3.10+ (Tested on Python 3.11 and 3.14)
- Node.js 18+ & npm 9+ (for building the frontend)
- Git

### Setup Virtual Environment
```bash
# Clone repository
git clone <repo-url>
cd Samsung-SmartGuide

# Create and activate python virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

---

## 5. Environment Variables
Create a `.env` file in the project root (copied from `.env.example`):
```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|:---|:---:|:---:|:---|
| `GEMINI_API_KEY` | Optional | `""` | Google Gemini API Key for cold-path reasoning. If omitted, engine runs in deterministic fallback mode with zero downtime. |
| `GEMINI_MODEL` | Optional | `gemini-2.5-flash` | Gemini model identifier. |
| `ENGINE_VERSION` | Optional | `1.0.0` | Semantic engine version token for cache invalidation. |
| `SEMANTIC_CACHE_THRESHOLD` | Optional | `0.65` | Cosine similarity threshold for Tier-2 semantic cache hit. |
| `DEEPLINK_CONFIDENCE_THRESHOLD` | Optional | `0.35` | Minimum similarity score required to bind a catalog deeplink. |

---

## 6. How to Run Backend
Run FastAPI with hot-reloading:
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 7. How to Run Frontend
In development mode (proxies API requests to port 8000):
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173/` in your browser.

---

## 8. How to Run Unified Application
The FastAPI backend directly mounts and serves the production-compiled React frontend at `GET /`:
```bash
# 1. Compile frontend build (already pre-built in repository)
cd frontend
npm run build
cd ..

# 2. Launch FastAPI
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/` in your web browser. The entire application (User Troubleshooter + Evaluator Dashboard + Backend API) is served seamlessly from a single port.

---

## 9. API Contract

### Health Check: `GET /health`
- **Response**: `200 OK`
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

### Troubleshoot Diagnostic: `POST /v1/troubleshoot`
- **Request Headers**: `Content-Type: application/json`
- **Response Headers**:
  - `X-Process-Time-Ms`: Server execution duration in milliseconds.
  - `X-Cache-Hit`: `true` or `false`.
  - `X-Cache-Type`: `exact`, `semantic`, or `miss`.
  - `X-Extraction-Path`: `fast_path_exact`, `fast_path_semantic`, or `cold_path`.

---

## 10. Example Request
```bash
curl -X POST "http://127.0.0.1:8000/v1/troubleshoot" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "My Samsung A115G tablet screen flashes and then goes completely blank whenever I tap to open an email in Gmail",
       "siis_response": {
         "title": "Email server not responding on Samsung phone or tablet",
         "content": "Verify your internet connection. Swipe down to open Quick settings, tap Connections, then tap Wi-Fi."
       }
     }'
```

---

## 11. Example Response
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
                "Verify active Wi-Fi connection status to access email servers."
              ],
              "actionableDeeplink": {
                "deeplink": "bixby://masked/act/b3ed3ed663",
                "description": "Enables data backup to Samsung Cloud via device Settings on the device.",
                "message": "Enable Back up data (Samsung Cloud)",
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

---

## 12. Testing
Run the complete automated test suites:

### Backend Pytest Suite (86 tests)
```bash
python -m pytest tests/ -v
```
*Covers Validation Firewall, Deeplink Resolver, Fast-Path Cache, Cold-Path Engine, API Contracts, and Frontend Integration.*

### Frontend Test Suite (11 tests)
```bash
cd frontend
npm test
```
*Covers typed API handling, response parsing, telemetry HUD, action checklist, and responsive styles.*

---

## 13. Benchmarking
Run the official benchmarking suite:
```bash
python scripts/benchmark_engine.py
```
This script measures:
- Startup / prewarming latency.
- 100 repeated canonical queries (P50, P95, P99, Hit Rate).
- 200 diverse query paraphrases (P50, P95, P99, Hit Rate).
- 12 unseen generalization scenarios across battery, connectivity, and hardware.
- Official 12-Gate Schema & Quality validation.

Results are saved to `results/benchmark_metrics.json`.

---

## 14. Docker Usage

### Build and Run Container
```bash
# Build Docker image
docker build -t samsung-smartguide:latest .

# Run container
docker run -p 8000:8000 \
  -e GEMINI_API_KEY="" \
  samsung-smartguide:latest
```

### Docker Compose
```bash
docker compose up -d
```
Access the application at `http://localhost:8000/`.

---

## 15. Limitations
1. **Opaque Deep Link Execution**: Deeplinks use the Samsung OneUI internal scheme (`bixby://masked/...`). They trigger native Settings app pages only when executed on a physical Samsung Galaxy device running OneUI. On non-Samsung devices or desktop web browsers, the UI presents a deep link inspector with a step-by-step fallback checklist.
2. **Cold-Path Token Limits**: When running with Gemini API enabled, extremely large SIIS articles (> 20,000 characters) are automatically truncated to the most relevant diagnostic sections to stay within rate limits.
3. **Upstream Starlette TestClient Notices**: Python 3.14 emits two deprecation warnings from upstream `starlette.testclient` (`httpx` import deprecation and `anyio.abc.BlockingPortal` alias), which do not affect runtime stability.

---

## 16. Hackathon Live Demo Flow

When presenting the live evaluation demo to judges:
1. **Startup & Readiness Check**:
   - Navigate to `http://127.0.0.1:8000/health`. Show that the server returns `{"status": "ok", "ready": true, "catalog_size": 578}`.
2. **Interactive Diagnostic Troubleshooter**:
   - Open `http://127.0.0.1:8000/`. Point out the green live connection indicator.
   - Select Scenario 1 ("Email server not responding").
   - Click **Run Instant Diagnosis**. Show the instant response (`< 1 ms`, `EXACT HIT`).
   - Click the **Paraphrase** quick button ("Gmail crash screen blackout"). Show `SEMANTIC HIT` in ~15 ms with the live telemetry HUD.
   - Demonstrate the interactive step checklist and the **Deep Link Inspector** displaying the verbatim `bixby://` URI.
3. **Cross-Article Safety & Isolation**:
   - Show that sending the exact same query with a cracked screen SIIS article cleanly rejects the email cache and produces a screen damage plan.
4. **Generalization on Unseen Scenarios**:
   - Enter an unseen issue (e.g. Battery Drain or S Pen disconnect). Show cold-path extraction in ~35 ms grounded strictly in the supplied text.
5. **Evaluator Dashboard**:
   - Switch to the **Evaluator Dashboard** tab. Show real-time KPI cards: 100% repeat hit rate, 92.5% paraphrase hit rate, sub-millisecond P95 latency, and the live historical telemetry log.
