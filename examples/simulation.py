"""Minimal end-to-end simulation for agent-drift-guard.

Purpose: prove the 0-turn concept works, and let the *runtime model* decide
what to build next (thread-safety vs message policy) instead of guessing.

Two independent probes:

  1. demo_asyncio()      - the realistic Hermes model: one event loop, a radio
                           coroutine calling on_message() while an agent loop
                           runs steps and drains at boundaries. Asserts the
                           0-turn invariants: no message is delivered before it
                           was sent, none mid-step, none lost, none duplicated.

  2. probe_threaded()    - stresses the buffer from real OS threads (radio on a
                           separate thread from the agent). Reports whether the
                           current plain-list buffer loses messages. This is the
                           empirical answer to "do we need thread-safety (#1)?"

Run:  python examples/simulation.py
"""

import asyncio
import random
import sys
import threading

from drift_guard.buffer import DriftGuardBuffer


# --------------------------------------------------------------------------
# Probe 1 - realistic asyncio single-loop model (Hermes-style)
# --------------------------------------------------------------------------
async def demo_asyncio(n_messages: int = 200, n_steps: int = 60) -> None:
    guard = DriftGuardBuffer()
    current_step = 0
    sent: dict[int, int] = {}          # msg_id -> step index when it was sent
    delivered: dict[int, int] = {}     # msg_id -> step index it was drained at
    radio_done = asyncio.Event()

    async def radio() -> None:
        # Fire messages at arbitrary times, including mid-step.
        for msg_id in range(n_messages):
            await asyncio.sleep(random.uniform(0, 0.002))
            sent[msg_id] = current_step
            guard.on_message(msg_id)   # 0-turn: buffer only, never call model
        radio_done.set()

    async def agent() -> None:
        nonlocal current_step
        step = 0
        # Keep stepping until the radio is done AND the buffer is empty.
        while not (radio_done.is_set() and guard.pending_count() == 0):
            current_step = step
            # Simulate a step doing work (a tool call / inference).
            await asyncio.sleep(0.001)
            # Safe boundary: drain and "inject".
            for msg_id in guard.on_step_end():
                assert msg_id not in delivered, f"duplicate delivery: {msg_id}"
                delivered[msg_id] = step
            step += 1
        return

    await asyncio.gather(radio(), agent())

    # Invariants -----------------------------------------------------------
    assert set(delivered) == set(sent), (
        f"loss/extra: sent={len(sent)} delivered={len(delivered)}"
    )
    for msg_id, deliver_step in delivered.items():
        # A message is withheld until a boundary at or after it was sent.
        assert deliver_step >= sent[msg_id], (
            f"msg {msg_id} delivered at step {deliver_step} "
            f"but was sent at step {sent[msg_id]} (delivered in the past?)"
        )

    print(
        f"[asyncio]  {len(sent)} sent, {len(delivered)} delivered, "
        f"0 lost, 0 dup, 0 mid-step  -> 0-turn invariant holds"
    )


# --------------------------------------------------------------------------
# Probe 2 - threaded stress (radio thread separate from agent thread)
# --------------------------------------------------------------------------
def probe_threaded(n_producers: int = 8, per_producer: int = 4000) -> int:
    guard = DriftGuardBuffer()
    total_sent = n_producers * per_producer
    received: list = []
    stop = threading.Event()

    def producer() -> None:
        for _ in range(per_producer):
            guard.on_message(1)

    def consumer() -> None:
        # Drain in a tight loop the whole time producers are running.
        while not stop.is_set():
            received.extend(guard.on_step_end())
        received.extend(guard.on_step_end())  # final drain

    # Force frequent thread switches so the (real but tiny) window between
    # `list(self._pending)` and `self._pending.clear()` in on_step_end() is
    # actually hit. Default switch interval (~5ms) almost never lands there.
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
        received.extend(guard.on_step_end())  # catch any last stragglers
    finally:
        sys.setswitchinterval(old_interval)

    lost = total_sent - len(received)
    verdict = "RACE: messages lost" if lost else "no loss observed"
    print(
        f"[threaded] {total_sent} sent, {len(received)} received, "
        f"{lost} lost  -> {verdict}"
    )
    return lost


if __name__ == "__main__":
    random.seed(0)
    asyncio.run(demo_asyncio())

    # Run the threaded probe a few times; races are timing-dependent.
    worst = max(probe_threaded() for _ in range(5))

    print("\n--- decision ---")
    print(
        "#1 thread-safety: NEEDED" if worst else
        "#1 thread-safety: not triggered in this run (re-run; still needed if "
        "radio ever runs off the agent's loop)"
    )
    print(
        "concurrency model: asyncio single-loop is safe as-is (cooperative); "
        "a lock is required only when on_message() is called from another thread."
    )
    print(
        "#3 message policy (staleness/coalesce): defer. The asyncio probe shows "
        "no loss/dup/staleness with a plain FIFO, so no policy is justified yet."
    )
