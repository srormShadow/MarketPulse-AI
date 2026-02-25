import logging
from logging.config import dictConfig

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": settings.log_format,
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
    logging.getLogger(__name__).info("Logging configured")
