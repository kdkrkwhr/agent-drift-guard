# Hermes wiring (0-turn radio)

This repo does **not** vendor [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
The reference loop is `HermesTurn` in `src/drift_guard/adapters/hermes.py`.
Run it with `python examples/hermes_loop.py`.

Hermes already has the same *timing* for user follow-ups:
`busy_input_mode: steer` injects after the next tool call and does not start a
new turn (`gateway/run.py` → `running_agent.steer(...)`). Cross-agent radio
should use that timing, not `interrupt()` + `run_conversation()`.

## Hook 1 — radio / mention (do not call the model)

**Where:** inbound path in `gateway/run.py` and the platform adapter
(`gateway/platforms/base.py`). Today a message that arrives while the agent is
busy typically interrupts or starts another `run_conversation()`.

**Instead:** buffer only.

```python
from drift_guard.adapters.hermes import HermesDriftGuard

guard = HermesDriftGuard()  # one instance per agent turn/session

# inside wait_for_mention / busy inbound, when the payload is cross-agent radio:
guard.on_radio_message({
    "text": event.text,       # or event.content
    "sender": event.sender,   # or sender_name
    "ts": event.ts,           # optional unix seconds
})
# Do NOT call run_conversation(), interrupt(), or any LLM client here.
```

`on_radio_message` accepts `CrossAgentMessage`, `HermesRadioEvent`, or a mapping
with `text`/`content`.

## Hook 2 — tool complete (append, still no extra turn)

**Where:** `agent/tool_executor.py`, after a tool result string is built and
before it is appended to `messages` (both sequential and concurrent paths).

```python
from drift_guard.adapters.hermes import append_to_tool_result

block = guard.drain_for_injection()  # "" if nothing pending
tool_result = append_to_tool_result(tool_result, block)
messages.append({"role": "tool", "content": tool_result, ...})
```

The next model call is the one Hermes was already going to make to continue
the turn after tools. That is 0-turn: the radio did not add an LLM invocation.

If `complete_tool` runs at a boundary that is not a tool result, pass
`site=InjectionSite.SYSTEM_REMINDER` to `drain_for_injection` rather than
inventing a fake tool message.

## What not to do

- Do not treat radio as a new user turn (`role=user` + `run_conversation()`).
- Do not use `pending_user` unless the runtime is known to keep that message
  inside the current turn. On Hermes it often looks like a new turn.
- Do not install this library as a reason to ship Hermes; the dependency goes
  the other way: a Hermes tree may depend on `agent-drift-guard`.

## Check

`HermesTurn` in tests asserts:

- `wait_for_mention` never increments `model_calls`
- radio text is absent from `transcript` until `complete_tool`
- FIFO appendix on the tool result
- a radio thread during a tool loses no messages
