"""Per-session guard state for the agent-drift-guard Hermes plugin.

Hermes fires ``on_session_start`` / ``on_session_end`` per session. We keep one
HermesDriftGuard per session id so radio messages buffered during a session are
scoped to that session and cleaned up on end. A radio watcher is optional and
tied to a threading.Event that is set on session end.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional

from drift_guard.adapters.hermes import HermesDriftGuard

from .radio import NullRadio, RadioWatcher


class SessionGuards:
    """Registry of HermesDriftGuard instances keyed by session id."""

    def __init__(self) -> None:
        self._guards: Dict[str, HermesDriftGuard] = {}
        self._watchers: Dict[str, RadioWatcher] = {}
        self._lock = threading.Lock()

    def start(self, session_id: str, source=None) -> HermesDriftGuard:
        """Create (or return existing) guard for *session_id* and start a watcher.

        *source* is a RadioSource callable returning new messages. When omitted a
        NullRadio is used (no background polling) — the guard still works for
        manually buffered messages (e.g. from tests or a synchronous radio).
        """
        source = source or NullRadio().poll
        with self._lock:
            guard = self._guards.get(session_id)
            if guard is None:
                guard = HermesDriftGuard()
                self._guards[session_id] = guard
            # (Re)start a watcher only if one isn't already running for this id.
            if session_id not in self._watchers:
                watcher = RadioWatcher(source=source, on_message=guard.on_radio_message)
                self._watchers[session_id] = watcher
                threading.Thread(target=watcher.run, name=f"drift-{session_id}", daemon=True).start()
        return guard

    def get(self, session_id: str) -> Optional[HermesDriftGuard]:
        with self._lock:
            return self._guards.get(session_id)

    def end(self, session_id: str) -> None:
        """Stop any watcher and drop the guard for *session_id*."""
        with self._lock:
            watcher = self._watchers.pop(session_id, None)
            if watcher is not None:
                watcher.stop()
            self._guards.pop(session_id, None)
