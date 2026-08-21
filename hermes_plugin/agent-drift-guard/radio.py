"""Background radio watcher for the agent-drift-guard Hermes plugin.

In production this wraps the Coral/AgentRadio ``wait_for_mention`` loop (or any
mcp_coral_wait_for_mention surface). For the Phase 1 plugin + mock-TDD scope we
keep it framework-agnostic: a ``RadioWatcher`` that polls a callable for new
messages and feeds them to a consumer, plus a ``NullRadio`` source for tests.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, List, Optional


# A "message" is any opaque payload (str, dict, Coral message object). We only
# ever store and replay it, never inspect its shape.
RadioSource = Callable[[], List[Any]]


class NullRadio:
    """Zero-message radio source. Used in tests and when no Coral link exists."""

    def poll(self) -> List[Any]:
        return []


def make_radio_source(poll_fn: Callable[[], List[Any]]) -> RadioSource:
    """Wrap a user polling callable into the RadioSource protocol."""
    return poll_fn


class RadioWatcher:
    """Polls a radio source and forwards every message to ``on_message``.

    The watcher is the *producer* in the buffer contract: it calls
    ``on_message`` (0-turn, never touches the model) and is independent of the
    agent's step loop. Safe to run on its own thread.
    """

    def __init__(
        self,
        source: RadioSource,
        on_message: Callable[[Any], None],
        stop: Optional[threading.Event] = None,
    ) -> None:
        self._source = source
        self._on_message = on_message
        self._stop = stop or threading.Event()

    def run(self) -> None:
        """Blocking poll loop. Returns when ``stop()`` is set."""
        while not self._stop.is_set():
            for msg in self._source():
                self._on_message(msg)
            # Yield so a daemon watcher over an idle (NullRadio) link does not
            # busy-spin and starve the GIL. Poll interval is tunable later.
            time.sleep(0.01)

    def stop(self) -> None:
        self._stop.set()
