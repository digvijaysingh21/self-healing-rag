"""
backend/app/logging_config.py

Configures structlog for the entire application.
Called once at the very top of app/main.py before
any other import that uses structlog.get_logger().

In development: pretty colored console output.
In production:  JSON lines ready for Datadog / CloudWatch / Loki.
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

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development or settings.is_test:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
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

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )