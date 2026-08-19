"""Hermes reference adapter for agent-drift-guard.

Shows how to wire DriftGuardBuffer into a Hermes agent: the background
wait_for_mention loop calls on_message(), and the tool executor calls
on_step_end() after each tool call completes.
"""

from drift_guard.buffer import DriftGuardBuffer


class HermesDriftGuard:
    """Framing around DriftGuardBuffer for Hermes agent lifecycle."""

    def __init__(self) -> None:
        self.buffer = DriftGuardBuffer()

    # Wire this into the background message watcher (wait_for_mention.sh style).
    def on_radio_message(self, msg) -> None:
        # 0-turn: just buffer, never call the model.
        self.buffer.on_message(msg)

    # Wire this into tool_dispatch_helpers / tool_executor after run_once.
    def on_tool_call_complete(self) -> list:
        return self.buffer.on_step_end()
