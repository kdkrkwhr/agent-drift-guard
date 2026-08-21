"""Safe-boundary injection hook for the agent-drift-guard Hermes plugin.

Provides the consumer side of the buffer contract: a function that drains the
HermesDriftGuard buffer (a pre-formatted string block) and appends it to a tool
result string. Wired into Hermes' ``transform_tool_result`` hook by __init__.py.
"""

from __future__ import annotations

from typing import Any, Sequence

from drift_guard.adapters.hermes import (
    HermesDriftGuard,
    append_to_tool_result,
)


def inject_at_boundary(
    guard: HermesDriftGuard,
    result: str,
    alt_block: str | None = None,
) -> str:
    """Inject buffered radio messages into *result* at a safe step boundary.

    Two modes:
      * ``alt_block is None`` (default): drains ``guard`` (a formatted string
        block) and appends it.
      * ``alt_block`` provided: use the caller-supplied block instead of
        draining (used by tests to assert injection without coupling to the
        buffer's internal state).

    Returns the (possibly) augmented result string. When there is nothing to
    inject the original result is returned unchanged.
    """
    block: str
    if alt_block is None:
        block = guard.drain_for_injection()
    else:
        block = alt_block
    return append_to_tool_result(result, block)
