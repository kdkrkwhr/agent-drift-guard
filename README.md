# agent-drift-guard

0-turn passive awareness for multi-agent systems.

Multi-agent setups break when a message arrives mid-reasoning. Small/budget
models are especially vulnerable: an incoming message during a tool call or
inference step derails the response (Reasoning Drift). This library buffers
incoming messages and injects them only at safe step boundaries, without
triggering an extra LLM turn (0-turn).

## Why

Most frameworks deliver cross-agent messages by immediately invoking the model.
That wastes tokens and, on small models, corrupts context. agent-drift-guard
keeps the model unaware of the message until it finishes its current step.

## Core API (framework-neutral)

The library defines two hooks plus a formatter. Any agent runtime can implement them:

```python
from drift_guard import (
    CrossAgentMessage,
    DriftGuardBuffer,
    format_injection,
)

buffer = DriftGuardBuffer()

# Called whenever a radio/message arrives. Does NOT call the model.
buffer.on_message(CrossAgentMessage(content="status?", sender="agent-2"))

# Called at a safe boundary (e.g. tool call complete). Injects pending messages.
block = format_injection(buffer.on_step_end())
# Runtime appends `block` to the current turn (default: last tool result).
# Empty string means append nothing. Never start a new LLM turn.
```

That is the whole contract. Adapters are just implementations of these hooks
for each runtime.

### 0-turn injection

Flushed messages are appended to the *current* turn. The runtime must not
invoke the model as a result of injection.

Default site: `tool_result_appendix` (suffix on the tool result that just
finished). Alternatives: `system_reminder`, `pending_user` (the latter can
look like a new turn on some stacks — avoid unless the runtime is known to
keep it in-turn).

Hermes framing: `HermesDriftGuard.drain_for_injection()` buffers from the
radio and returns the formatted block after each tool call. It does not
import Hermes. The in-repo loop is `HermesTurn`
(`python examples/hermes_loop.py`). Patch points for a real Hermes tree:
[`docs/hermes-wiring.md`](docs/hermes-wiring.md).
Upstream handoff (new PR, do not reuse #87441):
[`docs/hermes-upstream-work-plan.md`](docs/hermes-upstream-work-plan.md).
**Give this to a small/free coding agent (Hermes repo only, very explicit):**
[`docs/HERMES_AGENT_EXECUTOR_PLAN.md`](docs/HERMES_AGENT_EXECUTOR_PLAN.md).

## Status

Early research. Hermes reference implementation first; other runtimes later
via adapters. No benchmarks published yet (measured during research phase).

## Related

- Concept blog post: 0-turn 패턴, 에이전트가 서로 방해하지 않고 대화하는 법
- Spring AI PR #2967 (async context propagation, 0-turn passive awareness)
- Hermes Agent PR #87441 (opt-in tool, passive infra)
