import time
from dataclasses import dataclass


@dataclass
class Clock:
    """Timestamp-derived timer. `elapsed = banked + (now - started_at while running)`.

    Timestamp-derived (not ticker-incremented) so N connected browsers cannot
    make it run N times too fast. `started_at is None` is exactly "not running".
    """

    duration: float | None = None
    banked: float = 0.0
    started_at: float | None = None

    def start(self) -> None:
        if self.started_at is None:
            self.started_at = time.monotonic()

    def stop(self) -> None:
        if self.started_at is not None:
            self.banked += time.monotonic() - self.started_at
            self.started_at = None

    def reset(self, duration: float | None = None) -> None:
        self.banked = 0.0
        self.started_at = None
        self.duration = duration

    def elapsed(self) -> float:
        live = time.monotonic() - self.started_at if self.started_at is not None else 0.0
        return self.banked + live

    def remaining(self) -> float | None:
        if self.duration is None:
            return None
        return self.duration - self.elapsed()

    @property
    def running(self) -> bool:
        return self.started_at is not None
