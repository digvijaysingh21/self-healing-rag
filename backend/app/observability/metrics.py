"""
backend/app/observability/metrics.py

Prometheus metrics registry for the entire application.

All metrics are defined here as module-level singletons.
Import directly wherever needed:

    from app.observability.metrics import (
        RAG_QUERY_LATENCY,
        RAG_CRITIC_SCORE,
        RAG_RETRY_COUNT,
    )

init_metrics()        → called once at startup from app/main.py
mount_metrics_endpoint() → mounts /metrics ASGI endpoint on FastAPI app
"""

import structlog
from fastapi import FastAPI
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
    REGISTRY,
)

logger = structlog.get_logger(__name__)


# ── Query metrics ──────────────────────────────────────────

RAG_QUERY_TOTAL = Counter(
    name="rag_query_total",
    documentation="Total number of RAG queries received",
    labelnames=["status"],        # success | fallback | error
)

RAG_QUERY_LATENCY = Histogram(
    name="rag_query_duration_seconds",
    documentation="End-to-end RAG query latency in seconds",
    labelnames=["provider"],      # openai | anthropic | groq
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 30.0],
)


# ── Critic metrics ─────────────────────────────────────────

RAG_CRITIC_FAITHFULNESS = Histogram(
    name="rag_critic_faithfulness",
    documentation="RAGAS faithfulness score per query (0.0 to 1.0)",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

RAG_CRITIC_RELEVANCE = Histogram(
    name="rag_critic_relevance",
    documentation="RAGAS answer relevance score per query (0.0 to 1.0)",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

RAG_CRITIC_GROUNDEDNESS = Histogram(
    name="rag_critic_groundedness",
    documentation="RAGAS groundedness score per query (0.0 to 1.0)",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

RAG_CRITIC_PASS_TOTAL = Counter(
    name="rag_critic_pass_total",
    documentation="Total critic evaluations by outcome",
    labelnames=["outcome"],       # pass | retry | fallback
)


# ── Retry metrics ──────────────────────────────────────────

RAG_RETRY_COUNT = Histogram(
    name="rag_retry_count",
    documentation="Number of critic retries per query",
    buckets=[0, 1, 2, 3],
)


# ── Retrieval metrics ──────────────────────────────────────

RAG_RETRIEVAL_LATENCY = Histogram(
    name="rag_retrieval_duration_seconds",
    documentation="Hybrid retrieval latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

RAG_CHUNKS_RETRIEVED = Histogram(
    name="rag_chunks_retrieved_total",
    documentation="Number of chunks retrieved per query",
    buckets=[1, 3, 5, 7, 10, 15, 20],
)


# ── Ingestion metrics ──────────────────────────────────────

RAG_DOCUMENTS_INGESTED = Counter(
    name="rag_documents_ingested_total",
    documentation="Total documents successfully ingested",
    labelnames=["file_type"],     # pdf | docx | txt | url
)

RAG_INGESTION_LATENCY = Histogram(
    name="rag_ingestion_duration_seconds",
    documentation="Document ingestion latency in seconds",
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

RAG_CHUNKS_CREATED = Counter(
    name="rag_chunks_created_total",
    documentation="Total chunks created across all ingested documents",
)


# ── LLM metrics ────────────────────────────────────────────

RAG_LLM_TOKENS_USED = Counter(
    name="rag_llm_tokens_total",
    documentation="Total LLM tokens consumed",
    labelnames=["provider", "model", "token_type"],
)

RAG_LLM_LATENCY = Histogram(
    name="rag_llm_duration_seconds",
    documentation="LLM generation latency in seconds",
    labelnames=["provider", "model"],
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0],
)

RAG_LLM_ERRORS = Counter(
    name="rag_llm_errors_total",
    documentation="Total LLM provider errors",
    labelnames=["provider", "error_type"],
)


# ── Session metrics ────────────────────────────────────────

RAG_ACTIVE_SESSIONS = Gauge(
    name="rag_active_sessions",
    documentation="Number of active conversation sessions",
)

RAG_SESSION_TURNS = Histogram(
    name="rag_session_turns_total",
    documentation="Number of turns per session",
    buckets=[1, 2, 3, 5, 10, 20, 50],
)


# ── App info ───────────────────────────────────────────────

RAG_APP_INFO = Gauge(
    name="rag_app_info",
    documentation="Application metadata",
    labelnames=["version", "env"],
)


# ── init_metrics ───────────────────────────────────────────

def init_metrics() -> None:
    """
    Called once from app/main.py lifespan on startup.
    Sets the app info gauge so Prometheus has version metadata.
    """
    from app.config import settings

    RAG_APP_INFO.labels(
        version="0.1.0",
        env=settings.app_env,
    ).set(1)

    logger.info(
        "prometheus_metrics_initialised",
        metrics_count=len(list(REGISTRY._names_to_collectors)),
    )


# ── mount_metrics_endpoint ─────────────────────────────────

def mount_metrics_endpoint(app: FastAPI) -> None:
    """
    Mounts /metrics as a sub-application on the FastAPI app.
    Prometheus scrapes this endpoint every 15s.
    """
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    logger.info("metrics_endpoint_mounted", path="/metrics")