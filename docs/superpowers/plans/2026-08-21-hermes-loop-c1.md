# C1 Hermes Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce Hermes radio + tool-complete hooks in-repo and document the real wiring points, without installing Hermes Agent.

**Architecture:** Extend `adapters/hermes.py` with `HermesRadioEvent`, `from_hermes_radio`, `append_to_tool_result`, and `HermesTurn`. Tests lock 0-turn invariants. `docs/hermes-wiring.md` names the upstream files.

**Tech Stack:** Python 3.10+, pytest. No new dependencies.

## Global Constraints

- Python `>=3.10`; no hermes-agent (or any new) runtime dependency.
- Do not re-export Hermes types from `drift_guard` top-level `__init__.py`.
- `on_radio_message` must still accept `CrossAgentMessage` (existing tests).
- `wait_for_mention` / radio must not increment `HermesTurn.model_calls`.
- `complete_tool` must not increment `HermesTurn.model_calls`.
- Default injection site remains `tool_result_appendix`.
- Empty drain leaves the tool result string unchanged.
- FIFO, no coalescing.

## File map

- Modify: `src/drift_guard/adapters/hermes.py`
- Create: `tests/test_hermes_radio.py`
- Create: `tests/test_hermes_loop.py`
- Create: `examples/hermes_loop.py`
- Create: `docs/hermes-wiring.md`
- Modify: `README.md`

---

### Task 1: from_hermes_radio + append_to_tool_result

**Files:**
- Create: `tests/test_hermes_radio.py`
- Modify: `src/drift_guard/adapters/hermes.py`

**Interfaces:**
- Produces: `HermesRadioEvent(text, sender="", ts=None)`, `from_hermes_radio(event) -> CrossAgentMessage`, `append_to_tool_result(tool_result: str, block: str) -> str`

- [ ] **Step 1: Write failing tests** in `tests/test_hermes_radio.py` (see implementation below).
- [ ] **Step 2:** `python3 -m pytest tests/test_hermes_radio.py -v` — FAIL (names missing).
- [ ] **Step 3:** Add types/helpers to `hermes.py`. Route `on_radio_message` through `from_hermes_radio`.
- [ ] **Step 4:** pytest radio + existing `tests/test_hermes.py` PASS.
- [ ] **Step 5:** Commit `feat: map Hermes radio events to CrossAgentMessage`

---

### Task 2: HermesTurn 0-turn loop

**Files:**
- Create: `tests/test_hermes_loop.py`
- Modify: `src/drift_guard/adapters/hermes.py`

**Interfaces:**
- Produces: `HermesTurn` with `wait_for_mention`, `request_tool`, `complete_tool`, `transcript`, `model_calls`

- [ ] **Step 1: Write failing loop tests.**
- [ ] **Step 2:** pytest FAIL on missing `HermesTurn`.
- [ ] **Step 3:** Implement `HermesTurn`.
- [ ] **Step 4:** pytest PASS.
- [ ] **Step 5:** Commit `feat: add HermesTurn reference loop`

---

### Task 3: Example + wiring guide + README

**Files:**
- Create: `examples/hermes_loop.py`
- Create: `docs/hermes-wiring.md`
- Modify: `README.md`

- [ ] **Step 1:** Write example and docs (no production behavior change).
- [ ] **Step 2:** `python3 examples/hermes_loop.py` prints model_calls=1 and the appendix.
- [ ] **Step 3:** Commit `docs: add Hermes wiring guide and loop example`

---

Exact production code for Tasks 1–2 is the implementation in `src/drift_guard/adapters/hermes.py` shown in the spec. Tests are written first in the session; this plan is the contract, not a placeholder.
)
