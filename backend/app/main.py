"""
backend/app/main.py

FastAPI application entry point.
Defines the app instance, mounts all routers, registers middleware,
and handles startup / shutdown lifecycle events.

This is the file uvicorn points to: uvicorn app.main:app
"""

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import configure_logging

# Configure logging before anything else runs
configure_logging()

logger = structlog.get_logger(__name__)


# ── Lifespan ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup → yield → Shutdown
    Everything before yield runs on startup.
    Everything after yield runs on shutdown.
    """

    # ── STARTUP ───────────────────────────────────────────
    logger.info(
        "starting_up",
        env=settings.app_env,
        host=settings.app_host,
        port=settings.app_port,
    )

    # Verify DB connection
    try:
        from app.db import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database_connected")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise

    # Initialise Prometheus metrics
    try:
        from app.observability.metrics import init_metrics
        init_metrics()
        logger.info("metrics_initialised")
    except Exception as e:
        logger.error("metrics_init_failed", error=str(e))
        raise

    # Enable LangSmith tracing if configured
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        import os
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        logger.info(
            "langsmith_tracing_enabled",
            project=settings.langchain_project,
        )

    logger.info("application_ready")

    yield

    # ── SHUTDOWN ──────────────────────────────────────────
    logger.info("shutting_down")
    from app.db import engine
    await engine.dispose()
    logger.info("database_disconnected")
    logger.info("shutdown_complete")


# ── App instance ───────────────────────────────────────────

app = FastAPI(
    title="Self-Healing RAG Pipeline",
    description=(
        "A production-grade Retrieval-Augmented Generation system "
        "that critiques its own output and retries on low-quality answers. "
        "Built with LangGraph, pgvector, and multi-provider LLM routing."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── Mount Prometheus /metrics ──────────────────────────────

from app.observability.metrics import mount_metrics_endpoint
mount_metrics_endpoint(app)


# ── CORS ───────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing middleware ──────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
    return response


# ── Request ID middleware ──────────────────────────────────

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Global exception handler ───────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
            "path": str(request.url.path),
        },
    )


# ── Routers ────────────────────────────────────────────────
# Only health is active in Phase 1.
# Others will be uncommented as phases complete.

from app.api.health import router as health_router
app.include_router(health_router, tags=["health"])

