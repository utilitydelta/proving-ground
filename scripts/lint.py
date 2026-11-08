#!/usr/bin/env python3
"""Repo hygiene. Exit 1 on any violation.

  scripts/lint.py           what `finish` runs
  scripts/lint.py --cheap   what the pre-commit hook runs: scratch over budget is a warning, not a failure

Checks:
  - INDEX.md lines over 400 characters (a row that long is a report pasted into the index)
  - .claude/skills/*/SKILL.md over 120 lines or 12 KB (a skill that long gets skimmed; detail goes in references/)
  - untracked files loose at the repo root, outside ROOT_ALLOWED
  - sessions/*/scratch over SCRATCH_BUDGET from project.env
  - scripts/decisions.py check and scripts/risks.py check

PROJECT_ROOT overrides the repo root (tests).
"""
import os
import pathlib
import re
import subprocess
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("PROJECT_ROOT") or SCRIPTS.parent)
INDEX_LINE_MAX = 400
SKILL_LINES_MAX = 120
SKILL_BYTES_MAX = 12 * 1024
ROOT_ALLOWED = {"README.md", "AGENTS.md", "CLAUDE.md", "INDEX.md", "project.env", ".gitignore", "LICENSE"}
UNITS = {"": 1, "K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}


def project_env(root):
    """KEY=value lines of project.env; values unquoted, $HOME expanded, nothing else."""
    env = {}
    path = root / "project.env"
    if not path.is_file():
        return env
    for line in path.read_text().splitlines():
        m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line.strip())
        if m:
            env[m.group(1)] = m.group(2).strip().strip("'\"").replace("$HOME", os.environ.get("HOME", ""))
    return env


def size_bytes(text):
    m = re.fullmatch(r"(\d+)([KMGT]?)", text.strip().upper())
    return int(m.group(1)) * UNITS[m.group(2)] if m else None


def index_lines(root):
    path = root / "INDEX.md"
    if not path.is_file():
        return []
    return [f"INDEX.md:{n}: {len(line)} characters (max {INDEX_LINE_MAX})"
            for n, line in enumerate(path.read_text().splitlines(), 1) if len(line) > INDEX_LINE_MAX]


def skills(root):
    out = []
    for path in sorted((root / ".claude" / "skills").glob("*/SKILL.md")):
        data = path.read_bytes()
        lines = data.count(b"\n")
        rel = path.relative_to(root)
        if lines > SKILL_LINES_MAX:
            out.append(f"{rel}: {lines} lines (max {SKILL_LINES_MAX})")
        if len(data) > SKILL_BYTES_MAX:
            out.append(f"{rel}: {len(data)} bytes (max {SKILL_BYTES_MAX})")
    return out


def loose_files(root):
    try:
        listed = subprocess.run(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
                                capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []
    return [f"{name}: untracked file loose at the repo root; move it into a session, docs/ or delete it"
            for name in listed if "/" not in name and name not in ROOT_ALLOWED]


def scratch(root, env):
    budget = size_bytes(env.get("SCRATCH_BUDGET", ""))
    dirs = [str(p) for p in (root / "sessions").glob("*/scratch") if p.is_dir()]
    if budget is None or not dirs:
        return []
    out = subprocess.run(["du", "-sbc", *dirs], capture_output=True, text=True).stdout.splitlines()
    total = int(out[-1].split()[0]) if out else 0
    if total <= budget:
        return []
    return [f"sessions/*/scratch holds {total >> 20} MB, over SCRATCH_BUDGET {env['SCRATCH_BUDGET']}; Tend clears it"]


def registers(root):
    out = []
    env = dict(os.environ, DECISIONS_DIR=str(root / "decisions"), RISKS_DIR=str(root / "risks"))
    for script in ("decisions.py", "risks.py"):
        run = subprocess.run([sys.executable, str(SCRIPTS / script), "check"], capture_output=True, text=True, env=env)
        if run.returncode:
            out += [f"{script} check: {line}" for line in run.stdout.splitlines()[:-1]]
    return out


def main(args):
    cheap = "--cheap" in args
    env = project_env(ROOT)
    errors = index_lines(ROOT) + skills(ROOT) + loose_files(ROOT) + registers(ROOT)
    warnings = []
    (warnings if cheap else errors).extend(scratch(ROOT, env))
    for w in warnings:
        print(f"lint: warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"lint: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
