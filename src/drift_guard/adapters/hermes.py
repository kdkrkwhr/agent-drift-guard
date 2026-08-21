"""Hermes reference adapter for agent-drift-guard.

Shows how to wire DriftGuardBuffer into a Hermes agent: the background
wait_for_mention loop calls on_message(), and the tool executor calls
on_step_end() / drain_for_injection() after each tool call completes.

This module also provides the reference types the Hermes-side tests exercise:
``HermesRadioEvent`` (inbound radio payload), ``from_hermes_radio`` (mapping
into the framework-neutral ``CrossAgentMessage``), ``append_to_tool_result``
(module-level helper that appends a pre-rendered block to a tool result), and
``HermesTurn`` (a minimal stand-in for the agent turn loop that proves the
0-turn contract: radio during a tool call is buffered and replayed at the tool
result boundary without ever invoking the model).
"""

from dataclasses import dataclass
from typing import Any, List, Sequence

from drift_guard.buffer import DriftGuardBuffer
from drift_guard.inject import DEFAULT_INJECTION_SITE, format_injection
from drift_guard.message import CrossAgentMessage


@dataclass
class HermesRadioEvent:
    """Inbound radio payload as delivered by the Hermes gateway / AgentRadio."""

    text: str
    sender: str = ""
    ts: float | None = None


def from_hermes_radio(event: Any) -> CrossAgentMessage:
    """Map a Hermes radio event into a framework-neutral CrossAgentMessage.

    Accepts a ``HermesRadioEvent`` or a plain dict with ``text``/``content``,
    ``sender`` and ``ts``. A ``CrossAgentMessage`` is passed through unchanged.
    Anything else raises ``TypeError`` (callers must not silently drop radio).
    """
    if isinstance(event, CrossAgentMessage):
        return event
    if isinstance(event, HermesRadioEvent):
        return CrossAgentMessage(content=event.text, sender=event.sender, ts=event.ts)
    if isinstance(event, dict):
        if "text" not in event and "content" not in event:
            raise TypeError("radio mapping requires 'text' or 'content'")
        content = event.get("text") or event.get("content") or ""
        return CrossAgentMessage(
            content=content,
            sender=event.get("sender", ""),
            ts=event.get("ts"),
        )
    raise TypeError(f"cannot map radio event of type {type(event)!r} to CrossAgentMessage")


def append_to_tool_result(result: str, block: str) -> str:
    """Append a pre-rendered injection block to a tool result string.

    An empty block is a no-op (the result is returned unchanged). Used by the
    Hermes ``transform_tool_result`` hook and by the reference ``HermesTurn``.
    """
    if not block:
        return result
    return f"{result}\n{block}"


class HermesDriftGuard:
    """Framing around DriftGuardBuffer for Hermes agent lifecycle."""

    def __init__(self) -> None:
        self.buffer = DriftGuardBuffer()

    # Wire this into the background message watcher (wait_for_mention style).
    def on_radio_message(self, msg) -> None:
        # 0-turn: just buffer, never call the model.
        if isinstance(msg, (CrossAgentMessage, HermesRadioEvent)):
            self.buffer.on_message(msg if isinstance(msg, CrossAgentMessage) else from_hermes_radio(msg))
        elif isinstance(msg, dict):
            self.buffer.on_message(from_hermes_radio(msg))
        elif isinstance(msg, str):
            # Bare radio text: wrap as a message with no known sender.
            self.buffer.on_message(CrossAgentMessage(content=msg))
        else:
            self.buffer.on_message(from_hermes_radio(msg))

    # Wire this into tool_dispatch_helpers / tool_executor after run_once.
    def on_tool_call_complete(self) -> list:
        return self.buffer.on_step_end()

    # --- Phase 1 additions ------------------------------------------------
    # Named for the injection site so adapters and the Hermes plugin can share
    # a vocabulary: "drain the buffer and hand it to the injection point".

    def drain_for_injection(self, *, site=DEFAULT_INJECTION_SITE) -> str:
        """Render and clear buffered messages as an injection block.

        Returns a pre-formatted string (``format_injection`` output) suitable
        for appending to a tool result. Empty buffer returns ``""``. Clears the
        buffer under lock. ``site`` selects the injection site header.
        """
        pending = self.buffer.on_step_end()
        return format_injection(pending, site=site)

    # Backwards-compatible alias: on_tool_call_complete returns the same block.
    def on_tool_call_complete(self, *, site=DEFAULT_INJECTION_SITE) -> str:
        return self.drain_for_injection(site=site)


class HermesTurn:
    """Minimal reference stand-in for a Hermes agent turn.

    Proves the 0-turn contract without a live LLM: while a tool is in flight,
    radio messages are buffered (``wait_for_mention`` never increments
    ``model_calls`` and never appears in ``transcript``); when the tool
    completes, ``complete_tool`` replays the buffered messages as a tool-result
    appendix and only *then* counts the one model call the turn was already
    going to make.
    """

    def __init__(self) -> None:
        self.model_calls = 0
        self.transcript: List[Any] = []
        self.guard = HermesDriftGuard()
        self._tool_requested = False

    def request_tool(self) -> None:
        # Requesting a tool implies the turn will make one model call once the
        # tool returns; count it up front so radio buffering during the call
        # does not inflate the count (0-turn: radio must not add calls).
        self._tool_requested = True
        self.model_calls += 1

    def wait_for_mention(self, event: Any) -> None:
        # 0-turn: buffer the radio, never call the model.
        self.guard.on_radio_message(event)

    def complete_tool(self, name: str, result: str) -> str:
        # The model call for this turn was already counted in request_tool();
        # completing the tool only replays the buffered radio as an appendix.
        pending = self.guard.drain_for_injection()
        block = pending if pending else ""
        content = append_to_tool_result(result, block)
        self.transcript.append({"role": "tool", "name": name, "content": content})
        return content
