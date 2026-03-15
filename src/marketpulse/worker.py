#!/usr/bin/env python
"""Worker entrypoint for processing RQ jobs."""

import logging
import os
import sys
from pathlib import Path

from rq import Connection, Worker

from marketpulse.core.config import get_settings
from marketpulse.core.queue import _get_rq_queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("marketpulse.worker")

def main():
    """Start the RQ worker."""
    settings = get_settings()
    redis_url = getattr(settings, "redis_url", None)
    if not redis_url:
        logger.error("REDIS_URL is not set. Worker cannot start.")
        sys.exit(1)

    queue = _get_rq_queue()
    if not queue:
        logger.error("Failed to initialize RQ queue. Ensure Redis is running and reachable.")
        sys.exit(1)
        
    logger.info("Starting RQ worker connecting to Redis: %s", redis_url)
    
    # Needs to be inside Connection context so worker knows which redis to use
    from marketpulse.core.queue import _redis_conn 
    with Connection(_redis_conn):
        worker = Worker([queue])
        worker.work(with_scheduler=True)

if __name__ == "__main__":
    # Add src to PYTHONPATH so jobs can resolve marketpulse module
    src_path = str(Path(__file__).parent.parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    main()
