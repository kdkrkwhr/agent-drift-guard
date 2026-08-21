"""Safe-boundary injection hook for the agent-drift-guard Hermes plugin.

Provides the consumer side of the buffer contract: a function that drains the
HermesDriftGuard buffer and appends the deferred radio messages to a tool
result string. Wired into Hermes' ``transform_tool_result`` hook by __init__.py.
"""

from __future__ import annotations

from typing import Any, List, Sequence

from drift_guard.adapters.hermes import HermesDriftGuard


def inject_at_boundary(
    guard: HermesDriftGuard,
    result: str,
    alt_messages: Sequence[Any] | None = None,
) -> str:
    """Inject buffered radio messages into *result* at a safe step boundary.

    Two modes:
      * ``alt_messages is None`` (default): drains ``guard`` and appends.
      * ``alt_messages`` provided: use the caller-supplied list instead of
        draining (used by tests to assert injection without coupling to the
        buffer's internal state).

    Returns the (possibly) augmented result string. When there is nothing to
    inject the original result is returned unchanged.
    """
    messages: Sequence[Any]
    if alt_messages is None:
        messages = guard.drain_for_injection()
    else:
        messages = alt_messages
    return HermesDriftGuard.append_to_tool_result(result, list(messages))
