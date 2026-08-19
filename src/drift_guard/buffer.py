"""Framework-neutral core of agent-drift-guard.

The buffer never calls the model. It only stores messages until the runtime
signals a safe step boundary, then hands them back for injection.
"""


class DriftGuardBuffer:
    """Buffers cross-agent messages and releases them at step boundaries."""

    def __init__(self) -> None:
        self._pending: list = []

    def on_message(self, msg) -> None:
        """Record an incoming message. Does NOT invoke the model (0-turn)."""
        self._pending.append(msg)

    def on_step_end(self) -> list:
        """Called at a safe boundary (tool call complete, etc).

        Returns pending messages for the runtime to inject into context, then
        clears the buffer.
        """
        if not self._pending:
            return []
        flushed = list(self._pending)
        self._pending.clear()
        return flushed

    def pending_count(self) -> int:
        return len(self._pending)
