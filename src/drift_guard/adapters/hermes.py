"""Hermes reference adapter for agent-drift-guard.

Shows how to wire DriftGuardBuffer into a Hermes agent: the background
wait_for_mention loop calls on_message(), and the tool executor calls
on_step_end() / drain_for_injection() after each tool call completes.
"""

from typing import Any, List, Sequence

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

    # --- Phase 1 additions ------------------------------------------------
    # Named for the injection site so adapters and the Hermes plugin can share
    # a vocabulary: "drain the buffer and hand it to the injection point".

    def drain_for_injection(self) -> List[Any]:
        """Return buffered messages for safe injection at a step boundary.

        Equivalent to on_tool_call_complete() but named for the consumer side
        (e.g. right before the model emits a response, or inside the
        transform_tool_result hook). Clears the buffer under lock.
        """
        return self.buffer.on_step_end()

    @staticmethod
    def append_to_tool_result(result: str, messages: Sequence[Any]) -> str:
        """Append buffered radio messages to a tool-result string.

        Used by the Hermes ``transform_tool_result`` hook: the plugin drains
        the buffer at a safe boundary and appends the deferred messages to the
        tool result so the model sees them *within* the step (0-turn, no extra
        model turn). When ``messages`` is empty the original result is returned
        unchanged.
        """
        if not messages:
            return result
        rendered = "\n".join(str(m) for m in messages)
        return f"{result}\n\n[drift-guard] deferred radio messages:\n{rendered}"
