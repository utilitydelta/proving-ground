#!/usr/bin/env python3
"""Repo hygiene. Exit 1 on any violation.

  scripts/lint.py             what `finish` runs
  scripts/lint.py --cheap     what the pre-commit hook runs: scratch over budget is a warning, not a failure
  scripts/lint.py --adoption  only the adoption checks below; the template itself fails them by design

Checks:
  - INDEX.md: session lines (in `## Sessions`, naming a session-vN-...) over 150 characters, any other line over 400
  - .claude/skills/*/SKILL.md over 120 lines or 12 KB (a skill that long gets skimmed; detail goes in references/)
  - untracked files loose at the repo root, outside ROOT_ALLOWED
  - sessions/*/scratch plus .run/ over SCRATCH_BUDGET from project.env (summed in Python: no du, so it runs on macOS)
  - scripts/decisions.py check, scripts/risks.py check and scripts/findings.py check
  - harness/coverage.tsv: exists with at least one data row; every row has a known tier, a numeric budget_s, a
    command that reads $TREE (or ${TREE}) and does not wrap scripts/run.sh, and a plant column that is empty or an
    existing patch path; every harness/**/plants/*.patch and examples/*/plants/*.patch that no row names has a
    `# check:` line (a row's plant is graded by the row's command, scripts/coverage-plants.sh)
  - frozen sessions: a session whose line is in HEAD's INDEX `## Sessions` has been through `finish`. From the commit
    that added its INDEX line to the working tree (later commits, staged, unstaged and untracked alike, so a
    `--no-verify` commit is caught at the next lint) it may change only `status:` and `adopted_in:` lines in
    findings/*.md and lines inside a `## Changed by` section of units/*.md. Best effort: judged line by line on a
    -U0 diff, so a hand-crafted change can pass. Outside a git checkout of this repo (a `git archive` copy) it prints
    a SKIP line on stderr.

Adoption (--adoption): HUMAN_REPO exists and no longer points into examples/; every AGENTS.md `## Project` line is
filled (no <...> placeholder); docs/workload-shapes.md exists without its EXAMPLE ROW marker, or the Workload shapes
line says none; docs/ARCHITECTURE.md's Gate row no longer says Stub; no non-comment line of scripts/gate.sh mentions
examples/kv-python; once HUMAN_REPO is out of examples/, no line outside examples/ refers to the example
(`examples/`, `kv-python`, `kv-example`), except comment lines in non-Markdown files, the README's `## Adopting it`
section, sessions/, scripts/lint.py and scripts/test_*; `git remote get-url origin` is not TEMPLATE_ORIGIN
(project.env).

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
TIERS = ("probe", "targeted", "quick", "harness", "full")
EXAMPLE_MARKER = "EXAMPLE ROW"
EXAMPLE_REF = re.compile(r"examples/|kv-example|kv-python")
EXAMPLE_EXEMPT = {"scripts/lint.py"}
TREE_REF = re.compile(r"\$TREE\b|\$\{TREE\}")


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
    dirs = [p for p in (root / "sessions").glob("*/scratch") if p.is_dir()]
    dirs += [root / ".run"] if (root / ".run").is_dir() else []
    total = sum(tree_bytes(p) for p in dirs)
    if total <= budget:
        return []
    return [f"sessions/*/scratch and .run/ hold {total >> 20} MB, over SCRATCH_BUDGET {env['SCRATCH_BUDGET']}; Tend "
            "clears session scratch, scripts/clean-tmp.sh clears .run"]


def registers(root):
    out = []
    env = dict(os.environ, DECISIONS_DIR=str(root / "decisions"), RISKS_DIR=str(root / "risks"),
               SESSIONS_DIR=str(root / "sessions"))
    for script in ("decisions.py", "risks.py", "findings.py"):
        run = subprocess.run([sys.executable, str(SCRIPTS / script), "check"], capture_output=True, text=True,
                             errors="replace", env=env)
        if run.returncode:
            # Problem lines, then one line that always says the script failed: a crash prints no problem lines.
            out += [f"{script} check: {line}" for line in run.stdout.splitlines()[:-1]]
            tail = " | ".join(line.strip() for line in run.stderr.strip().splitlines()[-3:]) or "no stderr"
            out.append(f"{script} check exited {run.returncode}: {tail}")
    return out


def coverage(root):
    table = root / "harness" / "coverage.tsv"
    if not table.is_file():
        return ["harness/coverage.tsv: missing; the harness tier grades its rows (header: glob, command, tier, "
                "budget_s, plant)"]
    out, data, referenced = [], 0, set()
    for n, line in enumerate(table.read_text().splitlines(), 1):
        if n == 1 or not line.strip() or line.startswith("#"):
            continue
        data += 1
        cols = line.split("\t")
        if len(cols) != 5:
            out.append(f"harness/coverage.tsv:{n}: {len(cols)} columns, expected glob, command, tier, budget_s, plant")
            continue
        _glob, command, tier, budget, plant = cols
        if not TREE_REF.search(command):
            out.append(f"harness/coverage.tsv:{n}: command does not read $TREE; a fixed path grades the live tree, "
                       "never the snapshot or the planted copy")
        if "scripts/run.sh" in command:
            out.append(f"harness/coverage.tsv:{n}: command wraps scripts/run.sh; rows are bare, the runner wraps them")
        if plant.strip():
            referenced.add((root / plant.strip()).resolve())
        if tier not in TIERS:
            out.append(f"harness/coverage.tsv:{n}: tier {tier!r} not one of {', '.join(TIERS)}")
        if not re.fullmatch(r"\d+(\.\d+)?", budget.strip()):
            out.append(f"harness/coverage.tsv:{n}: budget_s {budget!r} is not a measured number of seconds")
        if plant.strip() and not (plant.strip().endswith(".patch") and (root / plant.strip()).is_file()):
            out.append(f"harness/coverage.tsv:{n}: plant {plant!r} is not an existing .patch path")
    if not data:
        out.append("harness/coverage.tsv: no data rows; every harness lands with a row (the template ships the "
                   "example's)")
    patches = sorted(root.glob("harness/**/plants/*.patch")) + sorted(root.glob("examples/*/plants/*.patch"))
    for patch in patches:
        if patch.resolve() in referenced:
            continue
        head = []
        for line in patch.read_text().splitlines():
            if line.startswith(("diff ", "--- ", "Index: ")):
                break
            head.append(line)
        if not any(line.startswith("# check: ") and line[9:].strip() for line in head):
            out.append(f"{patch.relative_to(root)}: no '# check: <command>' line before the diff")
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
        print("lint: SKIP frozen sessions: not a git checkout of this repo with a committed INDEX.md", file=sys.stderr)
        return []
    frozen = {m.group(0) for _n, line in section(head_index.splitlines(), "## Sessions")
              for m in SESSION_NAME.finditer(line)}
    out = []
    for name in sorted(frozen):
        added = (git(root, "log", "--format=%H", "--reverse", f"-S{name}", "--", "INDEX.md") or "").split()
        if not added:
            continue
        out += frozen_changes(root, name, added[0])
    return out


def frozen_changes(root, name, base):
    """Changes to sessions/<name> since commit <base>, committed or not, that a finished session may not take."""
    folder = f"sessions/{name}"
    changed = (git(root, "diff", base, "--name-only", "--", folder) or "").splitlines()
    untracked = (git(root, "ls-files", "--others", "--exclude-standard", "--", folder) or "").splitlines()
    out = []
    for rel in sorted(set(changed + untracked)):
        old = git(root, "show", f"{base}:{rel}")
        new_path = root / rel
        if old is None:
            out.append(f"{rel}: new file in finished session {name}; sessions are frozen after finish")
            continue
        if not new_path.is_file():
            out.append(f"{rel}: deleted or replaced in finished session {name}")
            continue
        diff = git(root, "diff", base, "-U0", "--", rel) or ""
        new = new_path.read_text()
        olds, news = old.splitlines(), new.splitlines()
        old_heads, new_heads = headings_by_line(old), headings_by_line(new)
        for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            o, oc, nw, nc = int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)
            if any(not allowed_change(rel, k, olds, old_heads) for k in range(o, o + oc)) or \
                    any(not allowed_change(rel, k, news, new_heads) for k in range(nw, nw + nc)):
                out.append(f"{rel}: finished session {name} is frozen; only a finding's status/adopted_in and a "
                           "unit's ## Changed by may change")
                break
    return out


def template_origin(root, env):
    """origin's URL when it points at TEMPLATE_ORIGIN (owner/name), else None."""
    template = env.get("TEMPLATE_ORIGIN", "").strip().strip("/")
    url = (git(root, "remote", "get-url", "origin") or "").strip()
    if template and url and re.search(r"[:/]" + re.escape(template) + r"(\.git)?/?$", url):
        return url
    return None


def repo_files(root):
    """Tracked and untracked-not-ignored files, relative to root; a plain walk outside git."""
    listed = git(root, "ls-files", "-co", "--exclude-standard")
    if listed is not None:
        return sorted(set(listed.splitlines()))
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)


def example_references(root):
    """Non-comment lines outside examples/ that still point at the worked example. Exempt: the README's
    `## Adopting it` steps, this script and the tooling tests (they carry example paths as fixtures)."""
    out = []
    for rel in repo_files(root):
        if rel.startswith(("examples/", ".run/", "sessions/")) or rel in EXAMPLE_EXEMPT \
                or (rel.startswith("scripts/test_") and "/" not in rel[len("scripts/"):]):
            continue
        try:
            lines = (root / rel).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        heads = headings_by_line("\n".join(lines))
        for n, line in enumerate(lines, 1):
            if not EXAMPLE_REF.search(line):
                continue
            if not rel.endswith(".md") and line.lstrip().startswith("#"):
                continue
            if rel == "README.md" and heads[n] == "## Adopting it":
                continue
            out.append(f"{rel}:{n}: references examples/ or the kv example; point it at the project's own harness")
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
            out.append(f"AGENTS.md:{n}: ## Project still holds template text {m.group(0)}")
    workload = [line for _n, line in project if "workload shapes" in line.lower()]
    shapes = root / "docs" / "workload-shapes.md"
    says_none = any("none" in line.lower() and not PLACEHOLDER.search(line) for line in workload)
    if not shapes.is_file() and not says_none:
        out.append("docs/workload-shapes.md missing and AGENTS.md ## Project does not say workload shapes: none")
    elif shapes.is_file() and EXAMPLE_MARKER in shapes.read_text() and not says_none:
        out.append(f"docs/workload-shapes.md still holds its {EXAMPLE_MARKER} marker; write real shapes or say none")
    arch = root / "docs" / "ARCHITECTURE.md"
    for n, line in enumerate(arch.read_text().splitlines() if arch.is_file() else [], 1):
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) >= 3 and cells[0] == "Gate" and "Stub" in cells[2]:
            out.append(f"docs/ARCHITECTURE.md:{n}: Gate row still says Stub; describe the project's gate stages")
    gate = root / "scripts" / "gate.sh"
    for n, line in enumerate(gate.read_text().splitlines() if gate.is_file() else [], 1):
        if "examples/kv-python" in line and not line.lstrip().startswith("#"):
            out.append(f"scripts/gate.sh:{n}: still runs examples/kv-python; write the project's product stages")
    if path is not None and path.is_dir() and not path.resolve().is_relative_to((root / "examples").resolve()):
        out += example_references(root)
    url = template_origin(root, env)
    if url:
        out.append(f"git origin {url} is the template (TEMPLATE_ORIGIN); point origin at the project's own repo")
    return out


def main(args):
    env = project_env(ROOT)
    if "--adoption" in args:
        errors, warnings = adoption(ROOT, env), []
    else:
        errors = (index_lines(ROOT) + skills(ROOT) + loose_files(ROOT) + registers(ROOT) + coverage(ROOT)
                  + frozen_sessions(ROOT))
        warnings = []
        (warnings if "--cheap" in args else errors).extend(scratch(ROOT, env))
    for w in warnings:
        print(f"lint: warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"lint: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
