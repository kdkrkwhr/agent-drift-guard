from dataclasses import dataclass


@dataclass(frozen=True)
class CrossAgentMessage:
    content: str
    sender: str = ""
    ts: float | None = None
