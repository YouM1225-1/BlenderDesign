---
name: graft
description: Locate symbols and trace cross-module call relationships in this repository using its local graft index. Useful for unfamiliar code paths, refactors, and impact analysis.
---

# Graft code navigation

Use the index when it helps answer a code-navigation question. For a known file,
documentation, configuration, or an exhaustive text search, read directly or use
`rg`. The graph is a retrieval aid; source and tests establish actual behavior.

| Need | Command |
|---|---|
| Repository orientation | `graft map` |
| Locate an unfamiliar behavior | `graft ask "<question with real identifiers>" --source` |
| Symbol occurrences in indexed files | `graft grep "<short symbol>"` |
| File signatures | `graft skeleton <file>` |
| Callers before a signature change or deletion | `graft callers <symbol> --depth 2` |
| Wider refactor impact | `graft callers <symbol> --depth all` |
| Outgoing dependencies | `graft callers <symbol> --direction out` |

Use the matching MCP tool when available. Choose the operation that answers the
question, inspect its result, then continue. Weak hits, missing paths, truncated
spans or dynamic calls justify reading source and searching references; do not
keep rephrasing the same query or assume indexed hits are exhaustive.

Check installed command help if an option is unavailable. Do not promise fixed
latency, token savings, or freshness across tool versions. Report retrieval details
only when they matter to the task.

Follow the repository's `AGENTS.md`: after the last repository edit run
`graft build .`, then require `graft check .` to exit 0 before delivery. Rebuild
after subsequent edits. Use wiring mode unless the user requests `--deep`;
`graft/` is a regenerable local cache and must not be committed.
