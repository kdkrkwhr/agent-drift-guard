"""Mock-TDD tests for the agent-drift-guard Hermes plugin (7 cases).

These cover the plugin's behaviour with mocked radio input — no Coral/network,
no real Hermes core. The plugin package is loaded by path (see conftest.py),
exactly as Hermes loads it, so relative imports resolve as in production.

Coverage:
  C1 on_session_start creates a per-session guard
  C2 buffered radio message is injected into tool result at the boundary
  C3 empty buffer leaves the tool result unchanged (0-turn no-op)
  C4 multiple buffered messages all appear, in order, exactly once
  C5 on_session_end stops the watcher and clears guard state
  C6 post_tool_call is observ-only (no injection, no mutation)
  C7 transform_tool_result on an unstarted session is a safe no-op
"""

from __future__ import annotations

import threading

from hermes_plugin_agent_drift_guard import inject_at_boundary
from hermes_plugin_agent_drift_guard.radio import RadioWatcher
from hermes_plugin_agent_drift_guard.session_guards import SessionGuards
from drift_guard.adapters.hermes import HermesDriftGuard


# ---------------------------------------------------------------------------
# C1 — on_session_start creates a per-session guard
# ---------------------------------------------------------------------------
def test_on_session_start_creates_session_guard(agd):
    agd._on_session_start(session_id="sess-1")
    guard = agd._guards.get("sess-1")
    assert guard is not None
    assert isinstance(guard, HermesDriftGuard)

    # A different session gets its own, independent guard.
    agd._on_session_start(session_id="sess-2")
    assert agd._guards.get("sess-2") is not agd._guards.get("sess-1")


# ---------------------------------------------------------------------------
# C2 — buffered radio message is injected into tool result at the boundary
# ---------------------------------------------------------------------------
def test_buffered_message_injected_into_tool_result(agd):
    agd._on_session_start(session_id="sess-3")
    guard = agd._guards.get("sess-3")
    guard.on_radio_message("agent-2: status?")

    original = '{"ok": true}'
    out = agd._on_transform_tool_result(tool_name="web_search", result=original, session_id="sess-3")

    assert out is not None
    assert "agent-2: status?" in out
    assert original in out


# ---------------------------------------------------------------------------
# C3 — empty buffer leaves the tool result unchanged (0-turn no-op)
# ---------------------------------------------------------------------------
def test_empty_buffer_leaves_result_unchanged(agd):
    # Session started but nothing buffered yet -> result unchanged (0-turn no-op).
    agd._on_session_start(session_id="sess-4")
    original = "result text"
    out = agd._on_transform_tool_result(tool_name="x", result=original, session_id="sess-4")
    assert out == original


# ---------------------------------------------------------------------------
# C4 — multiple buffered messages all appear, in order, exactly once
# ---------------------------------------------------------------------------
def test_multiple_buffered_messages_injected_in_order(agd):
    agd._on_session_start(session_id="sess-5")
    guard = agd._guards.get("sess-5")
    for msg in ["m1", "m2", "m3"]:
        guard.on_radio_message(msg)

    out = agd._on_transform_tool_result(tool_name="x", result="base", session_id="sess-5")

    # Order preserved and each present exactly once.
    assert out.index("m1") < out.index("m2") < out.index("m3")
    assert out.count("m1") == 1 and out.count("m2") == 1 and out.count("m3") == 1
    # After injection the buffer is drained (0-turn flush).
    assert guard.buffer.pending_count() == 0


# ---------------------------------------------------------------------------
# C5 — on_session_end stops the watcher and clears guard state
# ---------------------------------------------------------------------------
def test_on_session_end_clears_guard(agd):
    agd._on_session_start(session_id="sess-6")
    assert agd._guards.get("sess-6") is not None
    agd._on_session_end(session_id="sess-6")
    assert agd._guards.get("sess-6") is None


# ---------------------------------------------------------------------------
# C6 — post_tool_call is observer-only (no injection, no mutation)
# ---------------------------------------------------------------------------
def test_post_tool_call_is_observer_only(agd):
    agd._on_session_start(session_id="sess-7")
    guard = agd._guards.get("sess-7")
    guard.on_radio_message("should-not-appear-yet")

    ret = agd._on_post_tool_call(
        tool_name="write_file",
        args={"path": "/tmp/x"},
        result="done",
        session_id="sess-7",
    )
    # Observer hook returns None and performs no injection.
    assert ret is None
    # Buffer untouched — nothing was drained.
    assert guard.buffer.pending_count() == 1


# ---------------------------------------------------------------------------
# C7 — transform_tool_result on an unstarted session is a safe no-op
# ---------------------------------------------------------------------------
def test_transform_on_unstarted_session_is_noop(agd):
    # No guard was created for this session id.
    out = agd._on_transform_tool_result(tool_name="x", result="safe", session_id="no-such-session")
    assert out is None
    # Registry still usable afterwards.
    agd._on_session_start(session_id="sess-8")
    assert agd._guards.get("sess-8") is not None


# ---------------------------------------------------------------------------
# Extra: inject_at_boundary unit + RadioWatcher producer sanity (pure, no Hermes)
# ---------------------------------------------------------------------------
def test_inject_at_boundary_appends_and_drains():
    guard = HermesDriftGuard()
    guard.on_radio_message("hello")
    out = inject_at_boundary(guard, "base")
    assert "hello" in out
    assert guard.buffer.pending_count() == 0


def test_radio_watcher_forwards_to_on_message():
    # Finite source: emit a few messages then return nothing forever.
    sent = iter(["a", "b"])
    def source():
        try:
            return [next(sent)]
        except StopIteration:
            return []
    received = []
    watcher = RadioWatcher(source=source, on_message=received.append)
    t = threading.Thread(target=watcher.run, daemon=True)
    t.start()
    # The watcher drains the finite source then keeps polling idly; join with
    # a timeout so the test never hangs, then stop the loop.
    t.join(timeout=2.0)
    watcher.stop()
    t.join(timeout=2.0)
    assert received == ["a", "b"]
