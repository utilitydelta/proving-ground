#!/usr/bin/env bash
# Claude Code PreToolUse hook for Edit, Write, NotebookEdit and Bash (.claude/settings.json). Refuses a file edit
# under HUMAN_REPO and, best effort, a Bash write there: > and >> redirects, tee, sed -i, mv, cp, rm, touch, mkdir,
# chmod, ln, dd of=, and any git subcommand that is not read-only run in or -C at the human repo. Lead is bot-owned
# and not guarded. It catches slips, not adversaries; the factory jail is the hard boundary. Logic: shell_guard.py.
exec python3 "$(dirname "$0")/shell_guard.py" human-repo
