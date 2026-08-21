"""Hermes reference adapter for agent-drift-guard.

Shows how to wire DriftGuardBuffer into a Hermes agent: the background
wait_for_mention loop calls on_radio_message(), and the tool executor
calls drain_for_injection() after each tool call completes.

This module does not import Hermes. The runtime appends the returned
string at InjectionSite (default: tool result appendix) without invoking
the model (0-turn).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from drift_guard.buffer import DriftGuardBuffer
from drift_guard.inject import DEFAULT_INJECTION_SITE, InjectionSite, format_injection
from drift_guard.message import CrossAgentMessage


@dataclass(frozen=True)
class HermesRadioEvent:
    """Gateway-shaped inbound radio/mention payload (no Hermes import)."""

    text: str
    sender: str = ""
    ts: float | None = None


def from_hermes_radio(
    event: CrossAgentMessage | HermesRadioEvent | Mapping[str, Any],
) -> CrossAgentMessage:
    if isinstance(event, CrossAgentMessage):
        return event
    if isinstance(event, HermesRadioEvent):
        return CrossAgentMessage(content=event.text, sender=event.sender, ts=event.ts)
    if isinstance(event, Mapping):
        text = event.get("text", event.get("content"))
        if not isinstance(text, str):
            raise TypeError(
                "Hermes radio mapping needs a str 'text' or 'content' field"
            )
        sender = event.get("sender") or ""
        ts = event.get("ts")
        return CrossAgentMessage(content=text, sender=str(sender), ts=ts)
    raise TypeError(
        f"from_hermes_radio expects CrossAgentMessage, HermesRadioEvent, "
        f"or mapping, got {type(event)!r}"
    )


def append_to_tool_result(tool_result: str, block: str) -> str:
    """Append a drained injection block to a tool result. Empty block is a no-op."""
    if not block:
        return tool_result
    if not tool_result:
        return block
    return f"{tool_result}\n{block}"


class HermesDriftGuard:
    """Framing around DriftGuardBuffer for Hermes agent lifecycle."""

    def __init__(self) -> None:
        self.buffer = DriftGuardBuffer()

    def on_radio_message(
        self,
        msg: CrossAgentMessage | HermesRadioEvent | Mapping[str, Any],
    ) -> None:
        # 0-turn: just buffer, never call the model.
        self.buffer.on_message(from_hermes_radio(msg))

    def on_tool_call_complete(self) -> list:
        return self.buffer.on_step_end()

    def drain_for_injection(
        self,
        *,
        site: InjectionSite = DEFAULT_INJECTION_SITE,
    ) -> str:
        return format_injection(self.on_tool_call_complete(), site=site)


class HermesTurn:
    """One Hermes-shaped turn: radio buffers, tool complete injects, no extra LLM call."""

    def __init__(self) -> None:
        self.guard = HermesDriftGuard()
        self.transcript: list[dict[str, str]] = []
        self.model_calls = 0

    def wait_for_mention(
        self,
        event: CrossAgentMessage | HermesRadioEvent | Mapping[str, Any],
    ) -> None:
        self.guard.on_radio_message(event)

    def request_tool(self) -> None:
        """Count the model call that emitted tool_calls. Radio must not call this."""
        self.model_calls += 1

    def complete_tool(self, name: str, result: str) -> str:
        content = append_to_tool_result(result, self.guard.drain_for_injection())
        self.transcript.append({"role": "tool", "name": name, "content": content})
        return content
