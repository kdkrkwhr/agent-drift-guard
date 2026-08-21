import pytest

from drift_guard import CrossAgentMessage, DriftGuardBuffer


def test_public_export_is_importable():
    buf = DriftGuardBuffer()
    msg = CrossAgentMessage(content="status?", sender="agent-2")
    buf.on_message(msg)
    assert buf.pending_count() == 1
    flushed = buf.on_step_end()
    assert flushed == [msg]


def test_cross_agent_message_defaults():
    msg = CrossAgentMessage(content="hello")
    assert msg.content == "hello"
    assert msg.sender == ""
    assert msg.ts is None


def test_cross_agent_message_is_frozen():
    msg = CrossAgentMessage(content="hello", sender="a", ts=1.0)
    with pytest.raises(AttributeError):
        msg.content = "mutated"
