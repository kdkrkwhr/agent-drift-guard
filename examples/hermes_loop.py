"""Hermes-shaped 0-turn loop (no Hermes Agent install).

Radio (`wait_for_mention`) only buffers. The tool executor appends flushed
messages to the tool result. That does not start a new LLM turn.

Run:  python examples/hermes_loop.py
"""

from drift_guard.adapters.hermes import HermesRadioEvent, HermesTurn


def main() -> None:
    turn = HermesTurn()

    # The model already decided to call a tool (this is the only LLM call).
    turn.request_tool()
    print(f"model_calls after request_tool: {turn.model_calls}")

    # Mentions arrive mid-tool. Must not invoke the model.
    turn.wait_for_mention(HermesRadioEvent(text="status?", sender="agent-2"))
    turn.wait_for_mention({"text": "ack", "sender": "agent-3"})
    print(f"model_calls after radio:        {turn.model_calls}")
    print(f"transcript during tool:         {turn.transcript}")

    content = turn.complete_tool("shell", "ok")
    print(f"model_calls after complete_tool: {turn.model_calls}")
    print("tool result:")
    print(content)


if __name__ == "__main__":
    main()
