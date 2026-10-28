# session-relay

Claude Code desktop mod, shipped inside the yide plugin (loaded through `modules` in yide's `hooks/hooks.json`; its state is owned by the plugin name `yide`). Two jobs:

1. A cold session (idle for an hour or more, so its prompt cache has expired) that receives an automated report (a side session ending its turn, a subagent hand-back, a task notification) is not woken up. The mod starts a fresh continuation session with the old session's last report plus the incoming event as its brief, detaches it so it never reports back to the cold session, and drops the event in the cold session.
2. When the context reaches 400K tokens, a band above the prompt offers a "开新 session 续" button, and `/relay-now` does the same from the keyboard: the last assistant message is used as the handover.

The python hook `~/.claude/tools/token-audit/context_guard.py` stays beneath as the fallback for everything this mod does not handle.

Do not also load this folder through `CLAUDE_CODE_PLUGIN_DIRS`: with yide installed that would load it twice.
