"""
backend/app/logging_config.py

Configures structlog for the entire application.
Called once at the very top of app/main.py before
any other import that uses structlog.get_logger().

In development: pretty colored console output.
In production:  JSON lines — one JSON object per log line,
                ready for ingestion by Datadog / CloudWatch / Loki.
"""

import logging
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    """
    Sets up structlog with the right processors for the environment.
    Call this exactly once, at app startup, before any logger is used.
    """

    # Shared processors — run in every environment
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development or settings.is_test:
        # Pretty colored output for local development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production log aggregation
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libraries
    # (sqlalchemy, uvicorn, httpx) go through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )