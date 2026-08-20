"""Framework-neutral core of agent-drift-guard.

The buffer never calls the model. It only stores messages until the runtime
signals a safe step boundary, then hands them back for injection.
"""

import threading


class DriftGuardBuffer:
    """Buffers cross-agent messages and releases them at step boundaries.

    Thread-safe: the radio (producer) and the agent loop (consumer) may run on
    different threads, so every access to the pending list is guarded by a lock.
    """

    def __init__(self) -> None:
        self._pending: list = []
        self._lock = threading.Lock()

    def on_message(self, msg) -> None:
        """Record an incoming message. Does NOT invoke the model (0-turn)."""
        with self._lock:
            self._pending.append(msg)

    def on_step_end(self) -> list:
        """Called at a safe boundary (tool call complete, etc).

        Returns pending messages for the runtime to inject into context, then
        clears the buffer. Swap-under-lock so a concurrent on_message() can
        never be dropped between the read and the reset.
        """
        with self._lock:
            flushed = self._pending
            self._pending = []
        return flushed

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)
