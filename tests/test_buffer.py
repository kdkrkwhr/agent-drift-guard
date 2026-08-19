from drift_guard.buffer import DriftGuardBuffer


def test_on_message_does_not_invoke_model():
    buf = DriftGuardBuffer()
    buf.on_message("agent-2: status?")
    # No flush yet, nothing returned. Model stays unaware.
    assert buf.pending_count() == 1


def test_on_step_end_flushes_and_clears():
    buf = DriftGuardBuffer()
    buf.on_message("a")
    buf.on_message("b")
    flushed = buf.on_step_end()
    assert flushed == ["a", "b"]
    assert buf.pending_count() == 0


def test_on_step_end_empty_is_safe():
    buf = DriftGuardBuffer()
    assert buf.on_step_end() == []
