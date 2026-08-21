import pytest

from drift_guard import (
    CrossAgentMessage,
    DEFAULT_INJECTION_SITE,
    InjectionSite,
    format_injection,
)


def test_default_site_is_tool_result_appendix():
    assert DEFAULT_INJECTION_SITE is InjectionSite.TOOL_RESULT_APPENDIX
    assert InjectionSite.TOOL_RESULT_APPENDIX.value == "tool_result_appendix"


def test_format_injection_empty_is_blank():
    assert format_injection([]) == ""


def test_format_injection_fifo_with_senders():
    messages = [
        CrossAgentMessage(content="status?", sender="agent-2"),
        CrossAgentMessage(content="ack", sender="agent-3"),
    ]
    text = format_injection(messages)
    assert text == (
        "[drift-guard site=tool_result_appendix]\n"
        "- from agent-2: status?\n"
        "- from agent-3: ack"
    )


def test_format_injection_omits_empty_sender():
    text = format_injection([CrossAgentMessage(content="hello")])
    assert "- hello" in text
    assert "from :" not in text


def test_format_injection_collapses_newlines_in_content():
    text = format_injection(
        [CrossAgentMessage(content="line1\nline2", sender="a")]
    )
    assert "\n- from a: line1 line2" in text
    assert "line1\nline2" not in text


def test_format_injection_rejects_non_message():
    with pytest.raises(TypeError):
        format_injection(["raw string"])


def test_format_injection_site_is_header_only():
    text = format_injection(
        [CrossAgentMessage(content="x", sender="a")],
        site=InjectionSite.SYSTEM_REMINDER,
    )
    assert text.startswith("[drift-guard site=system_reminder]\n")
    assert "- from a: x" in text
