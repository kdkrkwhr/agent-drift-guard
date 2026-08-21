# Public API + Injection Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `drift_guard` an importable package with `CrossAgentMessage`, a 0-turn `format_injection` contract, and pytest coverage for freeze + concurrent flush.

**Architecture:** Buffer stays payload-agnostic. New `message.py` holds the recommended dataclass. New `inject.py` formats flushed `CrossAgentMessage` lists into a plain-text block tagged with `InjectionSite`. Hermes adapter gains `drain_for_injection` and still does not import Hermes.

**Tech Stack:** Python 3.10+, setuptools src layout, pytest.

## Global Constraints

- Python `>=3.10`; no new runtime dependencies.
- Package import name remains `drift_guard`; distribution name remains `agent-drift-guard` version `0.0.1`.
- `DriftGuardBuffer` stays payload-agnostic (`Any`); do not start requiring `CrossAgentMessage` inside the buffer.
- `format_injection` requires `CrossAgentMessage` items and raises `TypeError` otherwise.
- Default injection site is `InjectionSite.TOOL_RESULT_APPENDIX` (`"tool_result_appendix"`).
- Empty message list formats to `""`.
- Newlines in `content` are replaced with a single space.
- Empty `sender` omits the `from {sender}: ` prefix.
- FIFO order, no coalescing.
- Buffer lock + swap-under-lock in `on_step_end` stays; do not revert to list-copy-then-clear.
- No Hermes/runtime source dependency; no coalesce/staleness policy; no extra adapters.
- Do not add a LICENSE file.

## File map

- Create: `src/drift_guard/__init__.py`
- Create: `src/drift_guard/message.py`
- Create: `src/drift_guard/inject.py`
- Create: `src/drift_guard/adapters/__init__.py`
- Create: `tests/test_message.py`
- Create: `tests/test_inject.py`
- Create: `tests/test_hermes.py`
- Create: `tests/test_buffer_threads.py`
- Modify: `src/drift_guard/adapters/hermes.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Leave: `src/drift_guard/buffer.py` (behavior unchanged)
- Leave: `examples/simulation.py` (integer payloads still valid)

---

### Task 1: CrossAgentMessage + public package export

**Files:**
- Create: `tests/test_message.py`
- Create: `src/drift_guard/message.py`
- Create: `src/drift_guard/__init__.py`
- Create: `src/drift_guard/adapters/__init__.py`

**Interfaces:**
- Consumes: nothing
- Produces: `CrossAgentMessage(content: str, sender: str = "", ts: float | None = None)` frozen dataclass; `from drift_guard import CrossAgentMessage, DriftGuardBuffer`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from drift_guard import CrossAgentMessage, DriftGuardBuffer


def test_public_export_is_importable():
    buf = DriftGuardBuffer()
    msg = CrossAgentMessage(content="status?", sender="agent-2")
    buf.on_message(msg)
    assert buf.pending_count() == 1
    flushed = buf.on_step_end()
    assert flushed == [msg]


def test_cross_agent_message_defaults():
    msg = CrossAgentMessage(content="hello")
    assert msg.content == "hello"
    assert msg.sender == ""
    assert msg.ts is None


def test_cross_agent_message_is_frozen():
    msg = CrossAgentMessage(content="hello", sender="a", ts=1.0)
    with pytest.raises(AttributeError):
        msg.content = "mutated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_message.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `drift_guard` / `CrossAgentMessage` (no `__init__.py` / `message.py` yet).

- [ ] **Step 3: Write minimal implementation**

`src/drift_guard/message.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CrossAgentMessage:
    content: str
    sender: str = ""
    ts: float | None = None
```

`src/drift_guard/__init__.py`:

```python
from drift_guard.buffer import DriftGuardBuffer
from drift_guard.message import CrossAgentMessage

__all__ = [
    "CrossAgentMessage",
    "DriftGuardBuffer",
]
```

`src/drift_guard/adapters/__init__.py`: empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_message.py tests/test_buffer.py -v`
Expected: PASS (existing buffer tests still pass with string payloads).

- [ ] **Step 5: Commit**

```bash
git add src/drift_guard/__init__.py src/drift_guard/message.py src/drift_guard/adapters/__init__.py tests/test_message.py
git commit -m "feat: add CrossAgentMessage and public package exports"
```

---

### Task 2: InjectionSite + format_injection

**Files:**
- Create: `tests/test_inject.py`
- Create: `src/drift_guard/inject.py`
- Modify: `src/drift_guard/__init__.py`

**Interfaces:**
- Consumes: `CrossAgentMessage`
- Produces: `InjectionSite` str enum with `TOOL_RESULT_APPENDIX`, `SYSTEM_REMINDER`, `PENDING_USER`; `DEFAULT_INJECTION_SITE = InjectionSite.TOOL_RESULT_APPENDIX`; `format_injection(messages, *, site=DEFAULT_INJECTION_SITE) -> str`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from drift_guard import (
    CrossAgentMessage,
    DEFAULT_INJECTION_SITE,
    InjectionSite,
    format_injection,
)


def test_default_site_is_tool_result_appendix():
    assert DEFAULT_INJECTION_SITE is InjectionSite.TOOL_RESULT_APPENDIX
    assert InjectionSite.TOOL_RESULT_APPENDIX.value == "tool_result_appendix"


def test_format_injection_empty_is_blank():
    assert format_injection([]) == ""


def test_format_injection_fifo_with_senders():
    messages = [
        CrossAgentMessage(content="status?", sender="agent-2"),
        CrossAgentMessage(content="ack", sender="agent-3"),
    ]
    text = format_injection(messages)
    assert text == (
        "[drift-guard site=tool_result_appendix]\n"
        "- from agent-2: status?\n"
        "- from agent-3: ack"
    )


def test_format_injection_omits_empty_sender():
    text = format_injection([CrossAgentMessage(content="hello")])
    assert "- hello" in text
    assert "from :" not in text


def test_format_injection_collapses_newlines_in_content():
    text = format_injection(
        [CrossAgentMessage(content="line1\nline2", sender="a")]
    )
    assert "\n- from a: line1 line2" in text
    assert "line1\nline2" not in text


def test_format_injection_rejects_non_message():
    with pytest.raises(TypeError):
        format_injection(["raw string"])


def test_format_injection_site_is_header_only():
    text = format_injection(
        [CrossAgentMessage(content="x", sender="a")],
        site=InjectionSite.SYSTEM_REMINDER,
    )
    assert text.startswith("[drift-guard site=system_reminder]\n")
    assert "- from a: x" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_inject.py -v`
Expected: FAIL with `ImportError` for `format_injection` / `InjectionSite`.

- [ ] **Step 3: Write minimal implementation**

`src/drift_guard/inject.py`:

```python
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
```

Update `src/drift_guard/__init__.py`:

```python
from drift_guard.buffer import DriftGuardBuffer
from drift_guard.inject import (
    DEFAULT_INJECTION_SITE,
    InjectionSite,
    format_injection,
)
from drift_guard.message import CrossAgentMessage

__all__ = [
    "CrossAgentMessage",
    "DEFAULT_INJECTION_SITE",
    "DriftGuardBuffer",
    "InjectionSite",
    "format_injection",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_inject.py tests/test_message.py tests/test_buffer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/drift_guard/inject.py src/drift_guard/__init__.py tests/test_inject.py
git commit -m "feat: add 0-turn format_injection contract"
```

---

### Task 3: Hermes drain_for_injection

**Files:**
- Create: `tests/test_hermes.py`
- Modify: `src/drift_guard/adapters/hermes.py`

**Interfaces:**
- Consumes: `DriftGuardBuffer`, `CrossAgentMessage`, `format_injection`, `DEFAULT_INJECTION_SITE`, `InjectionSite`
- Produces: `HermesDriftGuard.on_radio_message(msg: CrossAgentMessage)`, `on_tool_call_complete() -> list`, `drain_for_injection(*, site=DEFAULT_INJECTION_SITE) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from drift_guard import CrossAgentMessage, InjectionSite
from drift_guard.adapters.hermes import HermesDriftGuard


def test_on_radio_message_does_not_flush():
    guard = HermesDriftGuard()
    guard.on_radio_message(
        CrossAgentMessage(content="status?", sender="agent-2")
    )
    assert guard.buffer.pending_count() == 1


def test_drain_for_injection_formats_and_clears():
    guard = HermesDriftGuard()
    guard.on_radio_message(
        CrossAgentMessage(content="status?", sender="agent-2")
    )
    text = guard.drain_for_injection()
    assert text == (
        "[drift-guard site=tool_result_appendix]\n"
        "- from agent-2: status?"
    )
    assert guard.buffer.pending_count() == 0
    assert guard.drain_for_injection() == ""


def test_drain_for_injection_honors_site():
    guard = HermesDriftGuard()
    guard.on_radio_message(CrossAgentMessage(content="x", sender="a"))
    text = guard.drain_for_injection(site=InjectionSite.PENDING_USER)
    assert text.startswith("[drift-guard site=pending_user]\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_hermes.py -v`
Expected: FAIL because `drain_for_injection` does not exist.

- [ ] **Step 3: Write minimal implementation**

Replace `src/drift_guard/adapters/hermes.py` with:

```python
"""Hermes reference adapter for agent-drift-guard.

Shows how to wire DriftGuardBuffer into a Hermes agent: the background
wait_for_mention loop calls on_radio_message(), and the tool executor
calls drain_for_injection() after each tool call completes.

This module does not import Hermes. The runtime appends the returned
string at InjectionSite (default: tool result appendix) without invoking
the model (0-turn).
"""

from drift_guard.buffer import DriftGuardBuffer
from drift_guard.inject import DEFAULT_INJECTION_SITE, InjectionSite, format_injection
from drift_guard.message import CrossAgentMessage


class HermesDriftGuard:
    """Framing around DriftGuardBuffer for Hermes agent lifecycle."""

    def __init__(self) -> None:
        self.buffer = DriftGuardBuffer()

    def on_radio_message(self, msg: CrossAgentMessage) -> None:
        # 0-turn: just buffer, never call the model.
        self.buffer.on_message(msg)

    def on_tool_call_complete(self) -> list:
        return self.buffer.on_step_end()

    def drain_for_injection(
        self,
        *,
        site: InjectionSite = DEFAULT_INJECTION_SITE,
    ) -> str:
        return format_injection(self.on_tool_call_complete(), site=site)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_hermes.py tests/test_inject.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/drift_guard/adapters/hermes.py tests/test_hermes.py
git commit -m "feat: add Hermes drain_for_injection helper"
```

---

### Task 4: Concurrent flush regression test

**Files:**
- Create: `tests/test_buffer_threads.py`

**Interfaces:**
- Consumes: `DriftGuardBuffer.on_message`, `on_step_end`
- Produces: pytest that asserts sent == received under concurrent producers + consumer

- [ ] **Step 1: Write the test**

This locks existing lock behavior (characterization). It must fail if the lock/swap is removed.

```python
import sys
import threading

from drift_guard import DriftGuardBuffer


def test_concurrent_on_message_and_on_step_end_loses_nothing():
    guard = DriftGuardBuffer()
    n_producers = 4
    per_producer = 500
    total_sent = n_producers * per_producer
    received: list = []
    stop = threading.Event()

    def producer() -> None:
        for _ in range(per_producer):
            guard.on_message(1)

    def consumer() -> None:
        while not stop.is_set():
            received.extend(guard.on_step_end())
        received.extend(guard.on_step_end())

    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=producer) for _ in range(n_producers)]
        con = threading.Thread(target=consumer)
        con.start()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stop.set()
        con.join()
        received.extend(guard.on_step_end())
    finally:
        sys.setswitchinterval(old_interval)

    assert len(received) == total_sent
    assert guard.pending_count() == 0
```

- [ ] **Step 2: Run test to verify it passes (lock already present)**

Run: `PYTHONPATH=src python -m pytest tests/test_buffer_threads.py -v`
Expected: PASS. If it fails with a count mismatch, restore swap-under-lock in `on_step_end`; do not "fix" the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_buffer_threads.py
git commit -m "test: lock concurrent on_message/on_step_end against loss"
```

---

### Task 5: Packaging metadata

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: existing setuptools src layout
- Produces: installable project metadata + pytest pythonpath so `python -m pytest` works without a manual `PYTHONPATH`

- [ ] **Step 1: Replace `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-drift-guard"
version = "0.0.1"
description = "0-turn passive awareness for multi-agent systems"
readme = "README.md"
requires-python = ">=3.10"

[project.optional-dependencies]
dev = ["pytest>=7"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Leave `setup.py` in place (thin wrapper already present).

- [ ] **Step 2: Run tests without PYTHONPATH**

Run: `python -m pytest -v`
Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add package metadata and pytest pythonpath"
```

---

### Task 6: README Core API

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: public exports from Task 1–3
- Produces: documented 0-turn injection rule and default site

- [ ] **Step 1: Replace the Core API section in `README.md` with:**

```markdown
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
import Hermes.
```

Keep the Why / Status / Related sections. Do not rewrite the whole README.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document public API and 0-turn injection contract"
```

---

## Self-review

1. Spec coverage: A (exports, message, packaging, thread test) → Tasks 1, 4, 5. B (sites, formatter, Hermes drain, README) → Tasks 2, 3, 6. Non-goals left out.
2. Placeholder scan: none.
3. Type consistency: `CrossAgentMessage`, `InjectionSite`, `DEFAULT_INJECTION_SITE`, `format_injection`, `drain_for_injection(*, site=...)` used the same way in every task.
)
