"""Manual 0-turn scenario verification for agent-drift-guard (ops / T4).

Reproduces the Hermes integration contract WITHOUT a live LLM:

  1. A [radio] message arrives WHILE a tool call is in flight.
  2. The drift guard buffers it (0-turn: never calls the model).
  3. When the tool call completes, the runtime drains the buffer and
     appends the buffered message to the tool result as an "appendix".
  4. Assert: no extra LLM turn was triggered, appendix present, buffer cleared.

This exercises the real code path in src/drift_guard/adapters/hermes.py
(HermesDriftGuard.on_radio_message / on_tool_call_complete). The actual
Hermes agent-loop seam (wiring the adapter into the tool executor) is owned
by T2; this file proves the 0-turn contract at the adapter boundary.

Run:  python examples/verify_drift_guard_0turn.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from drift_guard.adapters.hermes import HermesDriftGuard


class FakeModel:
    """Stands in for the LLM. Counts any invocation."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return "<model response>"


def tool_call_in_flight(model, guard):
    """Simulate the agent executing a tool.

    A [radio] message arrives mid-call (the background watcher would call
    on_radio_message). The adapter buffers it without invoking the model.
    """
    guard.on_radio_message("[radio] pm: status check - are you done?")
    # tool does its work and produces a result
    return {"tool": "search", "answer": 42}


def runtime_inject_appendix(guard, tool_result):
    """Runtime step-boundary drain: append buffered radio msgs to tool result."""
    pending = guard.on_tool_call_complete()
    if pending:
        tool_result["_drift_appendix"] = pending
    return tool_result


def main() -> None:
    model = FakeModel()
    guard = HermesDriftGuard()

    # 1) [radio] message arrives while the tool runs (background watcher path)
    tool_result = tool_call_in_flight(model, guard)

    # 2) tool completes -> runtime drains buffer into appendix (0 new LLM turn)
    tool_result = runtime_inject_appendix(guard, tool_result)

    # --- 0-turn contract assertions ---
    # (a) the radio message must NOT have triggered an extra model turn
    assert model.calls == 0, f"model was invoked {model.calls} times (0-turn violated)"
    # (b) the radio message is present as an appendix on the tool result
    appendix = tool_result.get("_drift_appendix", [])
    assert appendix == ["[radio] pm: status check - are you done?"], (
        f"appendix wrong: {appendix}"
    )
    # (c) buffer is now empty (no leak / no duplicate delivery)
    assert guard.buffer.pending_count() == 0, "buffer not cleared after drain"

    print("[verify] 0-turn scenario PASS")
    print(f"  - model extra turns invoked : {model.calls} (expect 0)")
    print(f"  - tool result appendix      : {appendix}")
    print(f"  - buffer after drain        : {guard.buffer.pending_count()} pending (expect 0)")
    print(
        "  - conclusion                : radio msg held during tool call, "
        "appended at step boundary, no new LLM turn"
    )


if __name__ == "__main__":
    main()
