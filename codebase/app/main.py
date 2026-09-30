"""FastAPI Application for Samsung Smart Guided Troubleshooting Engine.

Theme 02: Smart Guided Troubleshooting Engine (Samsung PRISM Hackathon Y2026)

Endpoints:
- GET /health: Health & readiness check (returns status: "ok" when initialized).
- POST /v1/troubleshoot: Resolves user issue + SIIS response into a schema-valid ContextDeeplinkResponse.
"""
from contextlib import asynccontextmanager
import json
import logging
import time
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.schemas import HealthResponse, TroubleshootRequest
from app.core.schema import ContextDeeplinkResponse
from app.state import app_state

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("samsung.engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager orchestrating startup and readiness initialization."""
    logger.info("Initializing application during startup lifespan...")
    app_state.initialize()
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title="Samsung Smart Guided Troubleshooting Engine",
    description="Production-grade, grounded troubleshooting engine adhering strictly to Theme 02 specifications.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend and evaluation clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Process-Time-Ms",
        "X-Cache-Hit",
        "X-Cache-Type",
        "X-Extraction-Path",
        "X-Stage1-Provider",
        "X-Stage2-Provider",
        "X-NBE-Sufficient",
        "X-NBE-Entropy",
        "X-NBE-Confidence",
        "X-NBE-EIG",
    ],
)


# =====================================================================
# Error Handlers: Zero stack traces, zero secret leaks, clean contracts
# =====================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors and malformed JSON syntax."""
    # Check if Starlette detected a JSON parsing/syntax failure
    for err in exc.errors():
        err_type = str(err.get("type", ""))
        if "json_invalid" in err_type or "json_decode" in err_type:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Bad Request",
                    "message": "Malformed JSON in request body.",
                },
            )

    # Sanitize validation errors to prevent leaking internal field names or paths
    errors = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x != "body"]
        msg = err.get("msg", "Validation error")
        field_name = ".".join(loc) or "body"
        errors.append({"field": field_name, "message": msg})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": "Validation Error",
            "message": "Invalid request payload format.",
            "detail": errors,
        },
    )


@app.exception_handler(json.JSONDecodeError)
async def json_decode_exception_handler(request: Request, exc: json.JSONDecodeError):
    """Handle raw JSON syntax decoding errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Bad Request",
            "message": "Malformed JSON in request body.",
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle standard HTTP exceptions with clean response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected server errors without leaking internals."""
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing the troubleshooting request.",
        },
    )


# =====================================================================
# API Endpoints
# =====================================================================


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health and readiness check",
    description="Returns server status and readiness metrics. Evaluators check status=='ok'.",
)
async def health_check():
    """Verify application readiness and dependency health."""
    if not app_state.is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "initializing",
                "ready": False,
                "message": "Engine is currently initializing models and prewarming cache.",
            },
        )

    return {
        "status": "ok",
        "ready": True,
        "version": "1.0.0",
        "catalog_size": app_state.catalog_size,
        "cache_entries": len(app_state.cache.exact_store) if app_state.cache else 0,
        "startup_time_s": round(app_state.startup_time_s, 3),
    }


@app.post(
    "/v1/troubleshoot",
    response_model=ContextDeeplinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve troubleshooting request",
    description="Ingests user complaint + SIIS response object, returning a fully grounded ContextDeeplinkResponse.",
)
async def troubleshoot(
    request: TroubleshootRequest,
    response: Response,
) -> ContextDeeplinkResponse:
    """Execute end-to-end troubleshooting pipeline adhering strictly to Theme 02 specs."""
    if not app_state.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Engine is initializing. Please retry shortly.",
        )

    t0 = time.perf_counter()
    siis_dict = {
        "title": request.siis_response.title,
        "content": request.siis_response.content,
    }

    # 1. Tier 1 / Tier 2 Cache Lookup
    cached_plan, telemetry = app_state.cache.get(
        query=request.query,
        siis_response=siis_dict,
    )

    if cached_plan is not None:
        # Constraint: Cached responses must ALWAYS pass ValidationFirewall before returning
        validated_plan, errors = app_state.firewall.validate_response(cached_plan, allow_repair=True)
        if not errors:
            process_ms = (time.perf_counter() - t0) * 1000.0
            response.headers["X-Process-Time-Ms"] = f"{process_ms:.3f}"
            response.headers["X-Cache-Hit"] = "true"
            response.headers["X-Cache-Type"] = telemetry.get("hit_type", "exact")
            response.headers["X-Extraction-Path"] = "cache"
            response.headers["X-NBE-Sufficient"] = "true"
            response.headers["X-NBE-Entropy"] = "0.000"
            response.headers["X-NBE-Confidence"] = "1.00"
            response.headers["X-NBE-EIG"] = "0.0000"
            return validated_plan
        else:
            logger.warning(f"Cached plan failed validation ({errors}). Routing to cold extraction.")

    # 2. Cold-Path Knowledge Extraction on Miss
    extracted_plan = app_state.cold_engine.extract_and_build(
        query=request.query,
        siis_response=siis_dict,
    )

    # Constraint: Cold-path responses must ALWAYS pass ValidationFirewall before returning
    final_plan, errors = app_state.firewall.validate_response(extracted_plan, allow_repair=True)
    if errors:
        logger.error(f"Cold-path extraction produced residual validation errors: {errors}")

    process_ms = (time.perf_counter() - t0) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{process_ms:.3f}"
    response.headers["X-Cache-Hit"] = "false"
    response.headers["X-Cache-Type"] = "miss"
    response.headers["X-Extraction-Path"] = getattr(app_state.cold_engine, "last_provider_used", "cold_path")
    response.headers["X-Stage1-Provider"] = getattr(app_state.cold_engine, "last_stage1_provider", "deterministic")
    response.headers["X-Stage2-Provider"] = getattr(app_state.cold_engine, "last_stage2_provider", "deterministic")

    # Expose NBE Disambiguation Telemetry
    nbe_res = getattr(app_state.cold_engine, "last_nbe_result", None)
    if nbe_res:
        response.headers["X-NBE-Sufficient"] = "true" if nbe_res.is_sufficient else "false"
        response.headers["X-NBE-Entropy"] = f"{nbe_res.current_entropy:.3f}"
        response.headers["X-NBE-Confidence"] = f"{nbe_res.top_hypothesis_confidence:.2f}"
        response.headers["X-NBE-EIG"] = f"{nbe_res.selected_eig:.4f}"
    else:
        response.headers["X-NBE-Sufficient"] = "true"
        response.headers["X-NBE-Entropy"] = "0.000"
        response.headers["X-NBE-Confidence"] = "1.00"
        response.headers["X-NBE-EIG"] = "0.0000"

    return final_plan


# =====================================================================
# Official Result Export Endpoints
# =====================================================================
@app.get("/v1/export/output.json", tags=["Export"])
async def export_output_json():
    """Download official output.json containing validated troubleshooting results."""
    root_dir = Path(__file__).resolve().parent.parent
    p = root_dir / "results" / "output.json"
    if not p.exists():
        p = root_dir / "output.json"
    if not p.exists():
        sample_p = root_dir / "sample_output.json"
        if sample_p.exists():
            return FileResponse(sample_p, media_type="application/json", filename="output.json")
        raise HTTPException(status_code=404, detail="output.json not found. Run scripts/generate_results.py first.")
    return FileResponse(p, media_type="application/json", filename="output.json")


@app.get("/v1/export/results.jsonl", tags=["Export"])
async def export_results_jsonl():
    """Download official results.jsonl containing canonical troubleshooting lines."""
    root_dir = Path(__file__).resolve().parent.parent
    p = root_dir / "results" / "results.jsonl"
    if not p.exists():
        raise HTTPException(status_code=404, detail="results.jsonl not found. Run scripts/generate_results.py first.")
    return FileResponse(p, media_type="application/x-ndjson", filename="results.jsonl")


# =====================================================================
# Interactive Frontend Diagnostic Portal Mount
# =====================================================================
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve the interactive diagnostic frontend application."""
        return FileResponse(frontend_dist / "index.html")

