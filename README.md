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

The library defines two hooks. Any agent runtime can implement them:

```python
buffer = DriftGuardBuffer()

# Called whenever a radio/message arrives. Does NOT call the model.
buffer.on_message(msg)

# Called at a safe boundary (e.g. tool call complete). Injects pending messages.
buffer.on_step_end()
```

That is the whole contract. Adapters are just implementations of these two
hooks for each runtime.

## Status

Early research. Hermes reference implementation first; other runtimes later
via adapters. No benchmarks published yet (measured during research phase).

## Related

- Concept blog post: 0-turn 패턴, 에이전트가 서로 방해하지 않고 대화하는 법
- Spring AI PR #2967 (async context propagation, 0-turn passive awareness)
- Hermes Agent PR #87441 (opt-in tool, passive infra)
