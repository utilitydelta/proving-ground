#!/usr/bin/env bash
# Claude Code PreToolUse hook for Edit, Write, NotebookEdit and Bash (.claude/settings.json). Refuses a file edit
# under HUMAN_REPO and, best effort, a Bash command that would write there: shell writes, git beyond reads, package
# installs, formatters and fixers, builds that drop output in the tree, Python without a pycache prefix. The full list
# and what stays allowed: shell_guard.py. Lead is bot-owned and not guarded. It catches slips, not adversaries; the
# factory jail is the hard boundary.
exec python3 "$(dirname "$0")/shell_guard.py" human-repo
