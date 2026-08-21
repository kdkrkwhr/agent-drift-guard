from drift_guard import CrossAgentMessage, InjectionSite
from drift_guard.adapters.hermes import HermesDriftGuard


def test_on_radio_message_does_not_flush():
    guard = HermesDriftGuard()
    guard.on_radio_message(
        CrossAgentMessage(content="status?", sender="agent-2")
    )
    assert guard.buffer.pending_count() == 1


def test_drain_for_injection_formats_and_clears():
    guard = HermesDriftGuard()
    guard.on_radio_message(
        CrossAgentMessage(content="status?", sender="agent-2")
    )
    text = guard.drain_for_injection()
    assert text == (
        "[drift-guard site=tool_result_appendix]\n"
        "- from agent-2: status?"
    )
    assert guard.buffer.pending_count() == 0
    assert guard.drain_for_injection() == ""


def test_drain_for_injection_honors_site():
    guard = HermesDriftGuard()
    guard.on_radio_message(CrossAgentMessage(content="x", sender="a"))
    text = guard.drain_for_injection(site=InjectionSite.PENDING_USER)
    assert text.startswith("[drift-guard site=pending_user]\n")
