#!/usr/bin/env python3
"""Repo hygiene. Exit 1 on any violation.

  scripts/lint.py             what `finish` runs
  scripts/lint.py --cheap     what the pre-commit hook runs: scratch over budget is a warning, not a failure
  scripts/lint.py --adoption  only the adoption checks below; the template itself fails them by design

Checks:
  - INDEX.md: session lines (in `## Sessions`, naming a session-vN-...) over 150 characters, any other line over 400
  - .claude/skills/*/SKILL.md over 120 lines or 12 KB (a skill that long gets skimmed; detail goes in references/)
  - untracked files loose at the repo root, outside ROOT_ALLOWED
  - sessions/*/scratch over SCRATCH_BUDGET from project.env (summed in Python: no du, so it runs on macOS too)
  - scripts/decisions.py check and scripts/risks.py check
  - frozen sessions: a session whose line is in HEAD's INDEX `## Sessions` has been through `finish`. Against HEAD
    (staged and unstaged, untracked included) it may change only `status:` and `adopted_in:` lines in findings/*.md
    and lines inside a `## Changed by` section of units/*.md. Best effort: judged line by line on a -U0 diff, so a
    hand-crafted change can pass; skipped outside a git checkout of this repo.

Adoption (--adoption): HUMAN_REPO exists and no longer points into examples/; AGENTS.md `## Project` holds no
<...> placeholder; docs/workload-shapes.md exists or the Workload shapes line says none; scripts/gate.sh no longer
delegates to the example.

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
SESSION_LINE_MAX = 150
SKILL_LINES_MAX = 120
SKILL_BYTES_MAX = 12 * 1024
ROOT_ALLOWED = {"README.md", "AGENTS.md", "CLAUDE.md", "INDEX.md", "project.env", ".gitignore", "LICENSE"}
UNITS = {"": 1, "K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}
SESSION_NAME = re.compile(r"session-v\d+-[a-z]+-[a-z0-9-]*[a-z0-9]")
PLACEHOLDER = re.compile(r"<[^<>\n]+>")


def project_env(root):
    """KEY=value lines of project.env; values unquoted, $HOME expanded, nothing else. The environment wins."""
    env = {}
    path = root / "project.env"
    if path.is_file():
        for line in path.read_text().splitlines():
            m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line.strip())
            if m:
                env[m.group(1)] = m.group(2).strip().strip("'\"").replace("$HOME", os.environ.get("HOME", ""))
    for key in env:
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def size_bytes(text):
    m = re.fullmatch(r"(\d+)([KMGT]?)", text.strip().upper())
    return int(m.group(1)) * UNITS[m.group(2)] if m else None


def section(lines, heading):
    """(line number, line) pairs under a `## heading`, up to the next `## `."""
    out, inside = [], False
    for n, line in enumerate(lines, 1):
        if line.startswith("## "):
            inside = line.strip() == heading
            continue
        if inside:
            out.append((n, line))
    return out


def index_lines(root):
    path = root / "INDEX.md"
    if not path.is_file():
        return []
    lines = path.read_text().splitlines()
    sessions = {n for n, line in section(lines, "## Sessions") if SESSION_NAME.search(line)}
    out = []
    for n, line in enumerate(lines, 1):
        limit = SESSION_LINE_MAX if n in sessions else INDEX_LINE_MAX
        if len(line) > limit:
            kind = "session line" if n in sessions else "line"
            out.append(f"INDEX.md:{n}: {kind} of {len(line)} characters (max {limit})")
    return out


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


def git(root, *args):
    """stdout of a git command in root, or None when root is not the top of a git checkout."""
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if pathlib.Path(top).resolve() != root.resolve():
            return None
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def loose_files(root):
    listed = git(root, "ls-files", "--others", "--exclude-standard")
    return [f"{name}: untracked file loose at the repo root; move it into a session, docs/ or delete it"
            for name in (listed or "").splitlines() if "/" not in name and name not in ROOT_ALLOWED]


def tree_bytes(path):
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass
    return total


def scratch(root, env):
    budget = size_bytes(env.get("SCRATCH_BUDGET", ""))
    if budget is None:
        return []
    total = sum(tree_bytes(p) for p in (root / "sessions").glob("*/scratch") if p.is_dir())
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


def headings_by_line(text):
    """The `## ` heading each line (1-based) sits under; index 0 unused."""
    current, out = None, [None]
    for line in text.splitlines():
        if line.startswith("## "):
            current = line.strip()
        out.append(current)
    return out


def allowed_change(rel, line_no, text_lines, headings):
    parts = rel.split("/")
    if len(parts) == 4 and parts[2] == "findings" and parts[3].endswith(".md"):
        return re.match(r"^(status|adopted_in):", text_lines[line_no - 1]) is not None
    if len(parts) == 4 and parts[2] == "units" and parts[3].endswith(".md"):
        return headings[line_no] == "## Changed by" or text_lines[line_no - 1].strip() == "## Changed by"
    return False


def frozen_sessions(root):
    head_index = git(root, "show", "HEAD:INDEX.md")
    if head_index is None:
        return []
    frozen = {m.group(0) for _n, line in section(head_index.splitlines(), "## Sessions")
              for m in SESSION_NAME.finditer(line)}
    if not frozen:
        return []
    changed = (git(root, "diff", "HEAD", "--name-only", "--", "sessions") or "").splitlines()
    untracked = (git(root, "ls-files", "--others", "--exclude-standard", "--", "sessions") or "").splitlines()
    out = []
    for rel in sorted(set(changed + untracked)):
        parts = rel.split("/")
        if len(parts) < 3 or parts[1] not in frozen:
            continue
        if rel in untracked:
            out.append(f"{rel}: new file in finished session {parts[1]}; sessions are frozen after finish")
            continue
        diff = git(root, "diff", "HEAD", "-U0", "--", rel) or ""
        old = git(root, "show", f"HEAD:{rel}")
        new_path = root / rel
        if old is None or not new_path.is_file():
            out.append(f"{rel}: deleted or replaced in finished session {parts[1]}")
            continue
        new = new_path.read_text()
        olds, news = old.splitlines(), new.splitlines()
        old_heads, new_heads = headings_by_line(old), headings_by_line(new)
        bad = False
        for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            o, oc, nw, nc = int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)
            if any(not allowed_change(rel, k, olds, old_heads) for k in range(o, o + oc)) or \
                    any(not allowed_change(rel, k, news, new_heads) for k in range(nw, nw + nc)):
                bad = True
                break
        if bad:
            out.append(f"{rel}: finished session {parts[1]} is frozen; only a finding's status/adopted_in and a "
                       "unit's ## Changed by may change")
    return out


def adoption(root, env):
    out = []
    human = env.get("HUMAN_REPO", "")
    path = pathlib.Path(human if os.path.isabs(human) else root / human) if human else None
    if path is None or not path.is_dir():
        out.append(f"HUMAN_REPO {human!r} is not a directory; point project.env at the human repo")
    elif path.resolve().is_relative_to((root / "examples").resolve()):
        out.append(f"HUMAN_REPO still points into examples/ ({human}); point project.env at the human repo")
    agents = root / "AGENTS.md"
    lines = agents.read_text().splitlines() if agents.is_file() else []
    project = section(lines, "## Project")
    for n, line in project:
        m = PLACEHOLDER.search(line)
        if m:
            out.append(f"AGENTS.md:{n}: ## Project still holds a placeholder {m.group(0)}")
    workload = [line for _n, line in project if "workload shapes" in line.lower()]
    if not (root / "docs" / "workload-shapes.md").is_file() and not any("none" in line.lower() for line in workload):
        out.append("docs/workload-shapes.md missing and AGENTS.md ## Project does not say workload shapes: none")
    gate = root / "scripts" / "gate.sh"
    if gate.is_file() and "examples/kv-python" in gate.read_text():
        out.append("scripts/gate.sh still delegates to examples/kv-python; write the project's product stages")
    return out


def main(args):
    env = project_env(ROOT)
    if "--adoption" in args:
        errors, warnings = adoption(ROOT, env), []
    else:
        errors = index_lines(ROOT) + skills(ROOT) + loose_files(ROOT) + registers(ROOT) + frozen_sessions(ROOT)
        warnings = []
        (warnings if "--cheap" in args else errors).extend(scratch(ROOT, env))
    for w in warnings:
        print(f"lint: warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"lint: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
