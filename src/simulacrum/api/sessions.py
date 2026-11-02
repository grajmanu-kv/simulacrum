"""In-memory session store with LRU eviction.

State is per-process: run a single worker, and expect sessions to vanish on restart. Persisting
sessions is a deliberate non-goal of v0.1 (the run log already makes any session reproducible).
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from simulacrum.engine import Engine
from simulacrum.errors import SessionNotFound


@dataclass
class Session:
    id: str
    engine: Engine
    spec_name: str
    created_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class SessionStore:
    def __init__(self, max_sessions: int):
        self.max_sessions = max_sessions
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._lock = threading.Lock()

    def add(self, engine: Engine, spec_name: str) -> Session:
        s = Session(uuid.uuid4().hex[:12], engine, spec_name)
        with self._lock:
            self._items[s.id] = s
            while len(self._items) > self.max_sessions:
                self._items.popitem(last=False)  # least recently used
        return s

    def get(self, sid: str) -> Session:
        with self._lock:
            s = self._items.get(sid)
            if s is None:
                raise SessionNotFound("unknown session (it may have been evicted); create a new world")
            self._items.move_to_end(sid)
            return s

    def __len__(self) -> int:
        return len(self._items)
