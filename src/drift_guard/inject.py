from collections.abc import Sequence
from enum import Enum

from drift_guard.message import CrossAgentMessage


class InjectionSite(str, Enum):
    TOOL_RESULT_APPENDIX = "tool_result_appendix"
    SYSTEM_REMINDER = "system_reminder"
    PENDING_USER = "pending_user"


DEFAULT_INJECTION_SITE = InjectionSite.TOOL_RESULT_APPENDIX


def format_injection(
    messages: Sequence[CrossAgentMessage],
    *,
    site: InjectionSite = DEFAULT_INJECTION_SITE,
) -> str:
    if not messages:
        return ""
    lines = [f"[drift-guard site={site.value}]"]
    for msg in messages:
        if not isinstance(msg, CrossAgentMessage):
            raise TypeError(
                f"format_injection expects CrossAgentMessage, got {type(msg)!r}"
            )
        content = " ".join(msg.content.split())
        if msg.sender:
            lines.append(f"- from {msg.sender}: {content}")
        else:
            lines.append(f"- {content}")
    return "\n".join(lines)
