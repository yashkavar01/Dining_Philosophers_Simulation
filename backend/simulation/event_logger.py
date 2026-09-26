"""
Thread-safe, append-only event log shared by every philosopher thread and
the deadlock detector. All mutation happens under a single lock, so events
logged by five concurrent threads still end up with a strictly increasing,
gap-free id sequence. Consumers (the Flask API) read incrementally via
`get_since(last_id)` so the browser never re-downloads the whole log.
"""
from __future__ import annotations

import threading
import time
from typing import List, Optional

from .models import Event


class EventLogger:
    def __init__(self, max_events: int = 5000):
        self._lock = threading.Lock()
        self._events: List[Event] = []
        self._next_id = 0
        self._start_time = time.monotonic()
        self._max_events = max_events

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._next_id = 0
            self._start_time = time.monotonic()

    def log(self, event_type, message: str, philosopher_id: Optional[int] = None, data: Optional[dict] = None) -> Event:
        with self._lock:
            evt = Event(
                id=self._next_id,
                timestamp=round(time.monotonic() - self._start_time, 3),
                philosopher_id=philosopher_id,
                event_type=event_type.value if hasattr(event_type, "value") else event_type,
                message=message,
                data=data or {},
            )
            self._next_id += 1
            self._events.append(evt)
            if len(self._events) > self._max_events:
                self._events.pop(0)
            return evt

    def get_since(self, since_id: int = -1) -> List[dict]:
        with self._lock:
            return [
                {
                    "id": e.id,
                    "timestamp": e.timestamp,
                    "philosopher_id": e.philosopher_id,
                    "event_type": e.event_type,
                    "message": e.message,
                    "data": e.data,
                }
                for e in self._events
                if e.id > since_id
            ]

    def count(self) -> int:
        with self._lock:
            return len(self._events)

    def elapsed(self) -> float:
        with self._lock:
            return round(time.monotonic() - self._start_time, 3)
