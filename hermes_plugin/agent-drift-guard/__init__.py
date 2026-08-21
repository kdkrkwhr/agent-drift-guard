"""Hermes plugin entry point for agent-drift-guard.

Registers lifecycle hooks that implement the 0-turn drift-guard contract:

  * on_session_start      -> create a per-session HermesDriftGuard + radio watcher
  * post_tool_call        -> (observer; reserved for telemetry) - buffer is drained
                             in transform_tool_result instead, at the safe boundary
  * transform_tool_result -> drain the buffer and append deferred radio messages
                             to the tool result (0-turn injection)
  * on_session_end        -> stop the watcher and drop the session guard

The plugin never invokes the model. It only buffers incoming radio messages
during a step and replays them at a safe boundary.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .inject_hook import inject_at_boundary
from .session_guards import SessionGuards

# Process-wide registry of per-session guards. Hermes loads a plugin once per
# process; session scoping is handled inside SessionGuards.
_guards = SessionGuards()


def _session_id_from(kwargs: Dict[str, Any], fallback: str = "default") -> str:
    sid = kwargs.get("session_id") or kwargs.get("task_id") or fallback
    return str(sid)


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------
def _on_session_start(**kwargs: Any) -> None:
    session_id = _session_id_from(kwargs, fallback="default")
    # NullRadio by default; a real deployment would inject a Coral source here.
    _guards.start(session_id)


def _on_post_tool_call(
    tool_name: str = "",
    args: Optional[Dict[str, Any]] = None,
    result: Any = None,
    session_id: str = "",
    task_id: str = "",
    **_: Any,
) -> None:
    # Observer only in Phase 1. The actual injection happens in
    # transform_tool_result (after the result is finalised) so the deferred
    # messages land in the same step's context.
    return None


def _on_transform_tool_result(
    tool_name: str = "",
    result: Any = None,
    session_id: str = "",
    **_: Any,
) -> Optional[str]:
    # Safe-boundary injection: drain the session's buffer and append the
    # deferred radio messages to the tool result. 0-turn - no model call.
    sid = _session_id_from({"session_id": session_id}, fallback="default")
    guard = _guards.get(sid)
    if guard is None:
        return None
    if not isinstance(result, str):
        result = "" if result is None else str(result)
    return inject_at_boundary(guard, result)


def _on_session_end(session_id: str = "", **_: Any) -> None:
    sid = _session_id_from({"session_id": session_id}, fallback="default")
    _guards.end(sid)


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------
def register(ctx) -> None:
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("transform_tool_result", _on_transform_tool_result)
    ctx.register_hook("on_session_end", _on_session_end)
