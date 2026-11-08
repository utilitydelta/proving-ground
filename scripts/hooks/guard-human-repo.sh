#!/usr/bin/env bash
# Claude Code PreToolUse hook for Edit, Write, MultiEdit, NotebookEdit and Bash (.claude/settings.json). Refuses a file
# edit under HUMAN_REPO and, best effort, a Bash command that writes there: redirects, tee, sed/perl/awk in place,
# mv/cp/rsync/tar/unzip/patch into it, git beyond reads. Running tests and tools in the human repo stays allowed.
# Fails closed on unreadable hook input or an unset HUMAN_REPO. The full list: shell_guard.py. Lead is bot-owned and
# not guarded. It catches slips, not adversaries; the factory jail is the hard boundary.
exec python3 "$(dirname "$0")/shell_guard.py" human-repo
