import threading
import time

from drift_guard.adapters.hermes import HermesRadioEvent, HermesTurn


def test_wait_for_mention_does_not_call_model():
    turn = HermesTurn()
    turn.wait_for_mention(HermesRadioEvent(text="status?", sender="agent-2"))
    assert turn.model_calls == 0
    assert turn.transcript == []
    assert turn.guard.buffer.pending_count() == 1


def test_radio_during_tool_is_hidden_until_complete():
    turn = HermesTurn()
    turn.request_tool()
    turn.wait_for_mention({"text": "status?", "sender": "agent-2"})
    turn.wait_for_mention({"text": "ack", "sender": "agent-3"})
    assert turn.model_calls == 1
    assert turn.transcript == []

    content = turn.complete_tool("shell", "ok")
    assert turn.model_calls == 1
    assert content == (
        "ok\n"
        "[drift-guard site=tool_result_appendix]\n"
        "- from agent-2: status?\n"
        "- from agent-3: ack"
    )
    assert turn.transcript == [
        {"role": "tool", "name": "shell", "content": content}
    ]
    assert turn.guard.buffer.pending_count() == 0


def test_complete_tool_without_radio_leaves_result():
    turn = HermesTurn()
    turn.request_tool()
    content = turn.complete_tool("read", "file contents")
    assert content == "file contents"
    assert turn.model_calls == 1


def test_threaded_radio_during_tool_loses_nothing():
    turn = HermesTurn()
    turn.request_tool()
    n = 50
    errors: list[BaseException] = []

    def radio() -> None:
        try:
            for i in range(n):
                turn.wait_for_mention({"text": f"m{i}", "sender": "agent-2"})
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    thread = threading.Thread(target=radio)
    thread.start()
    time.sleep(0.01)
    thread.join()
    assert errors == []

    content = turn.complete_tool("shell", "done")
    assert turn.model_calls == 1
    for i in range(n):
        assert f"- from agent-2: m{i}" in content
    assert content.count("- from agent-2:") == n
