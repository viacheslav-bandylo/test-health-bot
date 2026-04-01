"""Per-user rate limiting and message validation."""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[int, list[float]] = defaultdict(list)

    def is_allowed(self, chat_id: int) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds

        # Prune expired timestamps
        self._requests[chat_id] = [
            t for t in self._requests[chat_id] if t > cutoff
        ]

        if len(self._requests[chat_id]) >= self._max_requests:
            return False

        self._requests[chat_id].append(now)
        return True


def validate_message_length(text: str, max_length: int = 500) -> str:
    """Truncate message to max_length."""
    return text[:max_length]
