# Hermes plugin: agent-drift-guard

Standalone Hermes plugin implementing the 0-turn passive-awareness pattern for
cross-agent radio. Buffers inbound radio while a session is mid-turn (a tool
call is running) and injects it at the next tool-result boundary — no extra LLM
turn is spawned.

## Install (local)

```bash
# 1. install the library (editable)
pip install -e /path/to/agent-drift-guard

# 2. symlink the plugin into Hermes plugins dir
ln -s /path/to/agent-drift-guard/hermes_plugin/agent-drift-guard \
      ~/.hermes/plugins/agent-drift-guard
```

On Windows (no symlink): copy the folder
`hermes_plugin/agent-drift-guard` into `%HERMES_HOME%\plugins\`.

## How it wires in

| Hook | Behavior |
|------|----------|
| `pre_gateway_dispatch` | Cross-agent radio (`[radio]` prefix or bot source) arriving while the session has a running agent is buffered and the inbound event is skipped. User / idle / slash commands pass through. |
| `transform_tool_result` | At the tool-result boundary, buffered messages for that session are appended to the result string under `[drift-guard site=tool_result_appendix]`. Empty drain is a no-op. |

## Notes

- One guard per session key (never a process-wide singleton).
- Busy detection reads `gateway._running_agents` (private). If a future Hermes
  exposes `session_is_busy(session_key)`, prefer that over the private access.
- This plugin does NOT modify Hermes core. The drift-guard library is optional.
