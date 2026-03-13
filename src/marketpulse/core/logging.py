"""Logging configuration with optional structlog JSON output.

When ``LOG_FORMAT`` is set to ``"json"`` (recommended for production), logs are
emitted as structured JSON via structlog.  Otherwise, the default human-readable
format is used.
"""

import logging
from logging.config import dictConfig

from marketpulse.core.config import Settings


def configure_logging(settings: Settings) -> None:
    if settings.log_format.lower() == "json":
        _configure_structlog(settings)
    else:
        _configure_stdlib(settings)
    logging.getLogger(__name__).info("Logging configured (format=%s)", settings.log_format)


def _configure_stdlib(settings: Settings) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": settings.log_format
                    if settings.log_format.lower() != "json"
                    else "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": settings.log_level.upper(),
            },
        }
    )


def _configure_structlog(settings: Settings) -> None:
    try:
        import structlog

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Also configure stdlib logging for third-party libs
        _configure_stdlib(settings)
        logging.getLogger(__name__).info("Structured JSON logging enabled via structlog")
    except ImportError:
        logging.getLogger(__name__).warning("structlog not installed; falling back to stdlib logging")
        _configure_stdlib(settings)
