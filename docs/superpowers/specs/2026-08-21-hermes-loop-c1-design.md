# C1: Hermes-shaped loop and wiring guide

Date: 2026-08-21
Status: approved-to-implement (user chose C1, proceed immediately)

## Goal

Prove the two Hermes hook points in this repo, without installing
`NousResearch/hermes-agent`. A radio event must never start an LLM turn.
A completed tool call is the only place flushed messages enter the transcript.

## Non-goals

- Cloning, pip-installing, or running Hermes Agent.
- Cloud environment changes, API keys, gateway processes.
- Opening a PR against `NousResearch/hermes-agent`.
- Message coalesce / staleness policy.
- Other runtime adapters.

## Hermes facts this slice copies

- Inbound path: gateway radio / mention (`gateway/run.py`, platform adapters).
  Today a busy session typically interrupts or starts `run_conversation()`.
- Tool path: `agent/tool_executor.py` appends `role=tool` results, then the
  agent continues the *same* turn.
- Closest built-in analog: `busy_input_mode: steer` — user text is injected
  after the next tool call, no new turn. C1 is the same timing for
  *cross-agent radio*, not user `/steer`.

## Design

### 1. Radio event → CrossAgentMessage

Keep conversion in `src/drift_guard/adapters/hermes.py` (not the core
package export). Core stays framework-neutral.

```python
@dataclass(frozen=True)
class HermesRadioEvent:
    text: str
    sender: str = ""
    ts: float | None = None
```

`from_hermes_radio(event) -> CrossAgentMessage`

Accepted inputs:

- `CrossAgentMessage` — returned as-is
- `HermesRadioEvent` — `text`→`content`, `sender`, `ts`
- `Mapping` with `text` or `content` (str), optional `sender` and `ts`

Anything else → `TypeError`.

`HermesDriftGuard.on_radio_message` converts through `from_hermes_radio`
before buffering, so a gateway-shaped dict works at the hook.

### 2. Tool-result appendix helper

```python
def append_to_tool_result(tool_result: str, block: str) -> str:
    ...
```

Empty `block` returns `tool_result` unchanged. Non-empty block is appended
with a newline. This is what `tool_executor` should do after
`drain_for_injection()`. It does not call the model.

### 3. Reference loop: HermesTurn

A tiny stand-in for one Hermes turn, used by tests and the example:

```python
class HermesTurn:
    guard: HermesDriftGuard
    transcript: list[dict]   # {role, name, content}
    model_calls: int

    def wait_for_mention(self, event) -> None:  # radio; must not bump model_calls
    def request_tool(self) -> None:             # the model call that emitted tool_calls
    def complete_tool(self, name, result) -> str:
        # drain + append_to_tool_result; must not bump model_calls
```

Invariants:

- `wait_for_mention` never increments `model_calls`.
- Messages that arrive between `request_tool` and `complete_tool` are absent
  from `transcript` until `complete_tool`.
- After `complete_tool`, they appear FIFO in that tool's `content`, under the
  `[drift-guard site=tool_result_appendix]` header.
- `complete_tool` with an empty buffer leaves `result` unchanged.
- A radio thread may call `wait_for_mention` while the agent thread is in a
  tool; no message is lost.

### 4. Example

`examples/hermes_loop.py` — scripted scenario, prints model_calls and the
final tool result. Run: `python examples/hermes_loop.py`.

### 5. Wiring guide

`docs/hermes-wiring.md` — copy-paste patch points for a real Hermes tree:

1. Busy inbound in `gateway/run.py` / platform adapter: `wait_for_mention` /
   `on_radio_message`; do **not** call `run_conversation()` or `interrupt()`
   for cross-agent radio.
2. After each tool result is built in `agent/tool_executor.py` (sequential and
   concurrent): `append_to_tool_result(result, guard.drain_for_injection())`.
3. Map to steer: same injection timing as `busy_input_mode: steer`, different
   payload (radio vs user follow-up).

Snippet uses this library's public adapter API. No Hermes imports in this repo.

## Tests

New: `tests/test_hermes_radio.py`, `tests/test_hermes_loop.py`.
Existing `tests/test_hermes.py` must keep passing (`on_radio_message` still
accepts `CrossAgentMessage`).

## Success criteria

1. Pytest covers convert, appendix helper, 0-turn loop, and threaded radio.
2. Example runs and prints `model_calls` unchanged across radio events.
3. Wiring guide names the two Hermes files and the do-not-invoke-model rule.
4. `drift_guard` still has no hermes-agent dependency.
)
