"""Hermes reference adapter for agent-drift-guard.

Shows how to wire DriftGuardBuffer into a Hermes agent: the background
wait_for_mention loop calls on_radio_message(), and the tool executor
calls drain_for_injection() after each tool call completes.

This module does not import Hermes. The runtime appends the returned
string at InjectionSite (default: tool result appendix) without invoking
the model (0-turn).
"""

from drift_guard.buffer import DriftGuardBuffer
from drift_guard.inject import DEFAULT_INJECTION_SITE, InjectionSite, format_injection
from drift_guard.message import CrossAgentMessage


class HermesDriftGuard:
    """Framing around DriftGuardBuffer for Hermes agent lifecycle."""

    def __init__(self) -> None:
        self.buffer = DriftGuardBuffer()

    def on_radio_message(self, msg: CrossAgentMessage) -> None:
        # 0-turn: just buffer, never call the model.
        self.buffer.on_message(msg)

    def on_tool_call_complete(self) -> list:
        return self.buffer.on_step_end()

    def drain_for_injection(
        self,
        *,
        site: InjectionSite = DEFAULT_INJECTION_SITE,
    ) -> str:
        return format_injection(self.on_tool_call_complete(), site=site)
