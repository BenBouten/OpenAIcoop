"""Timing utilities for the simulation package."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def timed_section() -> Iterator[float]:
    """Context manager yielding elapsed time once the block completes."""
    start = time.perf_counter()
    yield 0.0
    elapsed = time.perf_counter() - start
    _ = elapsed  # Placeholder to silence linters until real usage.
