# src/utils/decorators.py — Utility decorators

from __future__ import annotations

import functools
import time
import logging
from typing import Any, Callable

logger = logging.getLogger("uvmgen")


def timer(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("%s completed in %.4fs", func.__name__, elapsed)
        return result

    return wrapper


def log_call(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.debug("Calling %s (args=%s, kwargs=%s)", func.__name__, args, kwargs)
        result = func(*args, **kwargs)
        logger.debug("%s returned", func.__name__)
        return result

    return wrapper
