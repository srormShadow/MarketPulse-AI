import logging
from typing import Any, Callable

from fastapi import BackgroundTasks

from marketpulse.core.config import get_settings

logger = logging.getLogger(__name__)

# Late-bind rq dependency so we can run without it locally
_rq_queue = None
_redis_conn = None


def _get_rq_queue():
    global _rq_queue, _redis_conn
    if _rq_queue is not None:
        return _rq_queue

    settings = get_settings()
    redis_url = getattr(settings, "redis_url", None)
    if not redis_url:
        return None

    try:
        import redis
        from rq import Queue

        _redis_conn = redis.from_url(redis_url, decode_responses=False)
        _rq_queue = Queue(connection=_redis_conn)
        return _rq_queue
    except ImportError:
        logger.warning("redis_url is set, but `redis` or `rq` is not installed. Disabling worker queue.")
        return None
    except Exception as exc:
        logger.warning("Failed to initialize RQ queue at %s: %s", redis_url, exc)
        return None


def enqueue_task(
    background_tasks: BackgroundTasks,
    func: Callable,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Queue a task via RQ (if configured), fallback to FastAPI BackgroundTasks.
    
    Returns True if passed to RQ, False if passed to BackgroundTasks.
    """
    queue = _get_rq_queue()
    if queue is not None:
        try:
            job = queue.enqueue(func, *args, **kwargs)
            logger.info("Enqueued RQ job %s calling %s", job.id, func.__name__)
            return True
        except Exception as exc:
            logger.error("Failed to enqueue RQ job %s, falling back to background thread. %s", func.__name__, exc)

    logger.debug("Falling back to FastAPI BackgroundTasks for %s", func.__name__)
    background_tasks.add_task(func, *args, **kwargs)
    return False
