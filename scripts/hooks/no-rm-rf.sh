#!/usr/bin/env bash
# Claude Code PreToolUse hook for Bash (.claude/settings.json). Refuses a recursive delete (rm -r, find -delete,
# find -exec rm, xargs rm, git clean -x) unless its target is a literal path resolving inside this repo's
# sessions/<session>/scratch/ or .run/tmp/ (.run/out/ too). A rule that lived only in briefs failed five times in the
# source repo; a hook does not forget. It catches slips, not adversaries. Logic and limits: shell_guard.py.
exec python3 "$(dirname "$0")/shell_guard.py" no-rm-rf
