"""
SmartSpend - Shared Cache Module
Centralised TTL cache used by both main.py and expense router.
"""

import threading
import time
import logging
from backend.utils.file_handler import read_json

logger  = logging.getLogger(__name__)

_cache      : dict         = {}
_cache_lock : threading.Lock = threading.Lock()
_CACHE_TTL  : int          = 60   # seconds


def cached_read(path: str) -> list | dict:
    """Return cached JSON data, refreshing if older than TTL."""
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(path)
        if entry and (now - entry["ts"]) < _CACHE_TTL:
            return entry["data"]
        try:
            data = read_json(path)
        except Exception as exc:
            logger.error("cached_read: could not read %s — %s", path, exc)
            # Return stale data rather than crashing if we have it
            if entry:
                logger.warning("cached_read: serving stale data for %s", path)
                return entry["data"]
            raise
        _cache[path] = {"data": data, "ts": now}
        return data


def invalidate(path: str) -> None:
    """Evict a path from the cache (call after every write)."""
    with _cache_lock:
        _cache.pop(path, None)
    logger.debug("Cache invalidated: %s", path)