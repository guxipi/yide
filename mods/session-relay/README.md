# session-relay

Claude Code desktop mod, shipped inside the yide plugin (loaded through `modules` in yide's `hooks/hooks.json`; its state is owned by the plugin name `yide`). This folder is the only source: the old single-machine copy at `~/.claude/mods/session-relay` is retired, do not edit or load it.

1. **Cold session, automated report.** A session idle for an hour or more (prompt cache expired) that receives an automated report (a side session ending its turn, a subagent hand-back, a task notification) is not woken up. The mod starts a fresh continuation with the old session's last report plus the event as its brief, detaches it so it never reports back, and drops the event.
2. **Fat session.** At 400K tokens the session is compacted in place (`$.session.compact` with a keep-list) when a main turn ends. The host refuses a compaction while a turn still runs, so a refusal is retried once five seconds later, and otherwise at the next turn end (at most once per two minutes). There is no button: unattended long sessions never stop. `/relay-now` opens a continuation by hand.

Gates (from the 10-28 / 10-29 misfires):

- **Running turn = warm.** `turn.start` / `turn.complete` keep a `running:<sid>` mark; while a main turn runs (mark under six hours old) nothing is relayed, however long ago the previous turn ended.
- **Retired lead.** A cold session whose last assistant message says it has handed over / been replaced (`RETIRED_RE`, self-referential only) drops the event and opens nothing.
- **One continuation per session.** Cold-path decisions run one at a time. Before `start_session` a `pending` placeholder goes into `relay:<sid>`; events that arrive meanwhile are queued in `relayQueue:<sid>` and forwarded with `send_message` once the continuation exists.
- **Relayed = retired.** Once `relay:<sid>` names a continuation, every later automated event to the old session is forwarded to it, warm or cold, until the person types in the old session (`userAt:<sid>` newer than the relay). If the forward fails (continuation archived) the record is dropped and the event is judged afresh.
- Any error in the decision lets the event through rather than lose it.

Tests: `claude plugin test <yide repo>` (hooks/relay.test.ts). The python hook `~/.claude/tools/token-audit/context_guard.py` stays beneath as the fallback.
