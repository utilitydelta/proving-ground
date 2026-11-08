#!/usr/bin/env bash
# Claude Code PreToolUse hook for Bash (registered in .claude/settings.json). Refuses a recursive rm whose target is
# built from a variable, a glob or a command substitution, or resolves outside a session's scratch/. A rule that
# lived only in briefs failed five times in the source repo; a hook does not forget.
#
#   stdin: the hook's JSON ({"tool_input": {"command": ...}, "cwd": ...}). Exit 0 allows, exit 2 blocks with the
#   reason on stderr, which Claude Code shows the agent.
#
# Allowed: `rm -r sessions/session-v3-task-x/scratch/run1` and the like, literal paths only. Anything else wanting a
# recursive delete makes a fresh `mktemp -d` under the session's scratch/ instead, and Tend clears scratch.
# Deliberately simple: it splits on ; && || | and newlines and reads each piece with shlex, so quoting tricks can get
# past it. It guards against slips, not against an agent trying to evade it.
set -euo pipefail
# shellcheck disable=SC2016
exec python3 -c '
import json, os, re, shlex, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
command = (data.get("tool_input") or {}).get("command") or ""
cwd = data.get("cwd") or os.getcwd()
SCRATCH = re.compile(r"/sessions/[^/]+/scratch/[^/]+")

def refuse(why):
    print(f"no-rm-rf: refused: {why}. Delete only literal paths under sessions/<session>/scratch/; for a fresh "
          "directory use mktemp -d there instead of deleting one.", file=sys.stderr)
    sys.exit(2)

for piece in re.split(r";|&&|\|\||\||\n", command):
    try:
        argv = shlex.split(piece)
    except ValueError:
        argv = piece.split()
    while argv and argv[0] in ("sudo", "command", "builtin", "env", "nice", "time"):
        argv = argv[1:]
    if not argv or os.path.basename(argv[0]) != "rm":
        continue
    flags = [a for a in argv[1:] if a.startswith("-") and a != "--"]
    if not any(f == "--recursive" or (not f.startswith("--") and re.search("[rR]", f)) for f in flags):
        continue
    targets = [a for a in argv[1:] if not a.startswith("-")]
    raw = piece
    if "$" in raw or "`" in raw:
        refuse(f"recursive rm on a path built from a variable or substitution: {piece.strip()}")
    for t in targets:
        if any(c in t for c in "*?[~"):
            refuse(f"recursive rm on a glob or ~ path: {t}")
        path = os.path.realpath(os.path.join(cwd, t))
        if not SCRATCH.search(path):
            refuse(f"recursive rm outside a session scratch/: {t}")
sys.exit(0)
'
