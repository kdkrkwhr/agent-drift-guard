# Public API freeze + 0-turn injection contract

Date: 2026-08-21
Status: approved-to-implement (user chose A then B)

## Goal

Make `agent-drift-guard` importable as a package with a frozen public surface, then define how flushed messages are injected into an agent turn without starting a new LLM call.

## Non-goals

- Wiring into Hermes source (`wait_for_mention`, tool executor). That is step C.
- Message coalesce / staleness policy. Simulation already showed plain FIFO has no loss/dup.
- Extra runtime adapters (LangGraph, CrewAI, AutoGen).
- Publishing to PyPI or adding a license file.

## Current gaps

- No `__init__.py`, so `find_packages(where="src")` may not install `drift_guard`.
- `pyproject.toml` has only the build backend; no project metadata, pytest config, or pythonpath.
- `on_message(msg)` is untyped. Runtimes cannot agree on payload shape.
- `on_step_end()` returns a list and stops. 0-turn requires a documented injection site plus a formatter the runtime can append without calling the model.
- `HermesDriftGuard` is a two-method rename of the buffer. Keep it, but type it and expose drain-for-injection.
- Thread-safety exists in `DriftGuardBuffer` but is not locked by pytest.

## A. Public API

### Package layout

```
src/drift_guard/
  __init__.py          # public exports
  buffer.py            # DriftGuardBuffer (payload-agnostic)
  message.py           # CrossAgentMessage
  inject.py            # InjectionSite + format_injection
  adapters/
    __init__.py
    hermes.py          # HermesDriftGuard
```

Public exports from `drift_guard`:

```python
from drift_guard import (
    CrossAgentMessage,
    DriftGuardBuffer,
    InjectionSite,
    format_injection,
    DEFAULT_INJECTION_SITE,
)
```

`drift_guard.adapters.hermes.HermesDriftGuard` stays as the Hermes-facing import. Not re-exported from the top level (keeps the core framework-neutral).

### CrossAgentMessage

```python
@dataclass(frozen=True)
class CrossAgentMessage:
    content: str
    sender: str = ""
    ts: float | None = None  # unix seconds; caller-supplied; buffer never stamps
```

Frozen so a buffered message cannot be mutated in place by a producer or consumer. `sender` and `ts` are optional because some radios only have text.

### DriftGuardBuffer stays payload-agnostic

The buffer does not inspect messages. It stores whatever the caller passes and returns it in FIFO order.

```python
class DriftGuardBuffer:
    def on_message(self, msg: Any) -> None: ...
    def on_step_end(self) -> list[Any]: ...
    def pending_count(self) -> int: ...
```

Rationale: the 0-turn contract is about *when* messages are released, not what they are. Existing tests and `examples/simulation.py` (integer ids) keep working. The recommended payload for real adapters is `CrossAgentMessage`.

Thread-safety: keep the existing lock. Swap-under-lock in `on_step_end` is required. Add a pytest that stresses concurrent `on_message` / `on_step_end` and asserts no loss.

### Packaging

Move project metadata into `pyproject.toml`. Keep `setup.py` as a thin wrapper so existing `pip install -e .` still works.

- name: `agent-drift-guard`
- version: `0.0.1`
- requires-python: `>=3.10`
- description: one sentence from README
- optional extra `dev`: `pytest>=7`
- `[tool.setuptools.packages.find] where = ["src"]`
- `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["src"]`

No new runtime dependencies.

## B. Injection contract

### Rule

A flushed message is injected into the *current turn's context* at a step boundary. The runtime MUST NOT invoke the model as a result of injection. The next model call is the one the agent was already going to make (continuation after the tool, or the next step). That is 0-turn.

The library never mutates a runtime's transcript. It only:

1. Holds messages until `on_step_end()`.
2. Formats them into a string the runtime appends at a chosen site.

### Injection sites

```python
class InjectionSite(str, Enum):
    TOOL_RESULT_APPENDIX = "tool_result_appendix"
    SYSTEM_REMINDER = "system_reminder"
    PENDING_USER = "pending_user"

DEFAULT_INJECTION_SITE = InjectionSite.TOOL_RESULT_APPENDIX
```

| Site | Where the runtime appends | Why it is / isn't default |
|---|---|---|
| `TOOL_RESULT_APPENDIX` | Suffix on the tool result that just completed | Default. Same turn, no new user role, prompt-cache friendly vs a new system message. |
| `SYSTEM_REMINDER` | A system/developer note before the next continuation | Allowed. May bust prefix cache on some stacks. |
| `PENDING_USER` | A user-role message queued for the same turn | Allowed. Dangerous: some runtimes treat a new user message as a new turn. |

Default is `TOOL_RESULT_APPENDIX`. If `on_step_end()` runs at a boundary that is not a tool result (e.g. end of a pure-inference step), the runtime should fall back to `SYSTEM_REMINDER` rather than inventing a fake tool result. The formatter itself does not know the boundary type; the runtime picks `site`.

### Formatter

```python
def format_injection(
    messages: Sequence[CrossAgentMessage],
    *,
    site: InjectionSite = DEFAULT_INJECTION_SITE,
) -> str:
    ...
```

Behavior:

- Empty `messages` → `""`. Runtime must treat empty string as "append nothing".
- Non-`CrossAgentMessage` items are rejected with `TypeError`. The buffer is agnostic; the formatter is not. Adapters convert before calling this.
- Order is FIFO, one bullet per message. No coalescing.
- Output is plain text. Site does not change the text body in v0; it is metadata for the runtime. Including the site name in a header so a dumped transcript is self-describing:

```
[drift-guard site=tool_result_appendix]
- from agent-2: status?
- from agent-3: ack
```

If `sender` is empty: `- content` (no `from :` prefix).

Content is not escaped beyond keeping it on one visual bullet. Newlines in `content` are replaced with a single space so a tool-result appendix cannot break role framing.

### Hermes adapter (still a framing layer)

```python
class HermesDriftGuard:
    def on_radio_message(self, msg: CrossAgentMessage) -> None: ...
    def on_tool_call_complete(self) -> list[CrossAgentMessage]: ...
    def drain_for_injection(
        self,
        *,
        site: InjectionSite = DEFAULT_INJECTION_SITE,
    ) -> str: ...
```

`on_radio_message` still does not call the model. `drain_for_injection` is `format_injection(on_tool_call_complete(), site=site)`.

No import of Hermes. Wiring remains a comment + README.

## Tests

- Existing buffer tests keep passing with string payloads.
- `from drift_guard import DriftGuardBuffer, CrossAgentMessage, format_injection` works after install/pythonpath.
- `CrossAgentMessage` is frozen (assignment raises).
- `format_injection([]) == ""`.
- Two messages format FIFO with senders.
- Empty sender omits `from`.
- Newlines in content collapse to spaces.
- Non-`CrossAgentMessage` → `TypeError`.
- Concurrent producers + consumer: sent count == received count.
- Hermes `drain_for_injection` returns the formatted block and clears the buffer.

## Docs

README Core API section: show `CrossAgentMessage`, the two hooks, and `format_injection` with the default site. State the 0-turn rule in one paragraph. Point adapters at `drain_for_injection`.

## Error handling

- Buffer: no validation (agnostic).
- Formatter: `TypeError` on wrong item type; no other errors.
- Empty drain is success, not an error.

## Success criteria

1. `pip install -e .` (or pytest via pythonpath) imports `drift_guard`.
2. Pytest covers buffer, formatter, freeze, and the concurrent flush.
3. Injection site default is `tool_result_appendix`, documented as 0-turn.
4. No Hermes/runtime source dependency.
)
