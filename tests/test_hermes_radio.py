import pytest

from drift_guard import CrossAgentMessage
from drift_guard.adapters.hermes import (
    HermesDriftGuard,
    HermesRadioEvent,
    append_to_tool_result,
    from_hermes_radio,
)


def test_from_hermes_radio_event():
    event = HermesRadioEvent(text="status?", sender="agent-2", ts=1.5)
    msg = from_hermes_radio(event)
    assert msg == CrossAgentMessage(content="status?", sender="agent-2", ts=1.5)


def test_from_hermes_radio_mapping_text():
    msg = from_hermes_radio({"text": "ack", "sender": "agent-3", "ts": 2.0})
    assert msg == CrossAgentMessage(content="ack", sender="agent-3", ts=2.0)


def test_from_hermes_radio_mapping_content_fallback():
    msg = from_hermes_radio({"content": "hello", "sender": "a"})
    assert msg.content == "hello"
    assert msg.sender == "a"


def test_from_hermes_radio_passthrough_cross_agent_message():
    original = CrossAgentMessage(content="x", sender="a")
    assert from_hermes_radio(original) is original


def test_from_hermes_radio_rejects_unknown():
    with pytest.raises(TypeError):
        from_hermes_radio("raw string")
    with pytest.raises(TypeError):
        from_hermes_radio({"sender": "a"})


def test_on_radio_message_accepts_mapping():
    guard = HermesDriftGuard()
    guard.on_radio_message({"text": "status?", "sender": "agent-2"})
    assert guard.buffer.pending_count() == 1
    flushed = guard.buffer.on_step_end()
    assert flushed == [CrossAgentMessage(content="status?", sender="agent-2")]


def test_append_to_tool_result_empty_block_is_noop():
    assert append_to_tool_result("ok", "") == "ok"


def test_append_to_tool_result_joins_with_newline():
    block = "[drift-guard site=tool_result_appendix]\n- from a: x"
    assert append_to_tool_result("ok", block) == f"ok\n{block}"
