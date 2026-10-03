"""In-memory sliding-window rate limits for the paid /ask endpoints."""

import threading
import time
from collections import deque
from collections.abc import Callable


class SlidingWindowLimiter:
    """
    Allow at most `limit` hits per `window` seconds for each key.

    State lives in this process only, which suits a single-instance demo.
    A limit of 0 disables the limiter.
    """

    def __init__(
        self, window: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int) -> float | None:
        """
        Record a hit for `key` and return None, or return the seconds to
        wait when the key has used up its limit (the hit is not recorded).
        """

        if limit <= 0:
            return None

        now = self._clock()

        with self._lock:
            hits = self._hits.setdefault(key, deque())

            while hits and hits[0] <= now - self.window:
                hits.popleft()

            if len(hits) >= limit:
                return hits[0] + self.window - now

            hits.append(now)

            # Forget idle keys so one-off visitors don't accumulate.
            if len(self._hits) > 10_000:
                cutoff = now - self.window
                self._hits = {k: v for k, v in self._hits.items() if v[-1] > cutoff}

            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
