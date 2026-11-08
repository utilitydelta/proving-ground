#!/usr/bin/env python3
"""List, count and lint the findings in sessions/*/findings/.

  scripts/findings.py            every finding: path, class, status, touches
  scripts/findings.py stats      the INDEX.md `## Precision` table rows, findings by class and status
  scripts/findings.py check      exit 1 on a malformed finding or an unfilled skeleton placeholder (scripts/skeleton.py)

A finding is sessions/<session>/findings/NNN-<slug>.md with frontmatter class, status, touches and evidence
(sessions/README.md). check judges every *.md in a findings/ folder but README.md, so a misnamed or non-UTF-8 file
is a problem, never skipped; class and status in their enums, touches and evidence non-empty, adopted_in only on an
adopted finding. SESSIONS_DIR overrides the folder (tests).
"""
import os
import pathlib
import re
import sys

from skeleton import placeholder_problems, read_register, register_files

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = pathlib.Path(os.environ.get("SESSIONS_DIR") or ROOT / "sessions")
CLASSES = ("one-way-door", "time-sink", "regression", "two-way-door")
STATUS = ("open", "adopted", "rejected", "noise")
REQUIRED = ("class", "status", "touches", "evidence")
NAME = re.compile(r"\d+-.+\.md")


def load(path):
    text, unreadable = read_register(path)
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fields = {k: v.strip() for k, v in re.findall(r"^(\w+):[ \t]*(.*)$", m.group(1), re.M)} if m else {}
    return {**fields, "path": path, "frontmatter": bool(m), "text": text, "unreadable": unreadable}


def problems(f):
    if f["unreadable"]:
        return [f["unreadable"]]
    if not NAME.fullmatch(f["path"].name):
        return [f"file name {f['path'].name} is not NNN-<slug>.md"]
    if not f["frontmatter"]:
        return ["no --- frontmatter block"]
    out = [f"missing {k}" for k in REQUIRED if not f.get(k)]
    if f.get("class") and f["class"] not in CLASSES:
        out.append(f"class {f['class']!r} not one of {', '.join(CLASSES)}")
    if f.get("status") not in STATUS:
        out.append(f"status {f.get('status')!r} not one of {', '.join(STATUS)}")
    if f.get("adopted_in") and f.get("status") != "adopted":
        out.append(f"adopted_in on a finding with status {f.get('status')!r}")
    return out + placeholder_problems(f["text"])


def rel(path):
    try:
        return str(path.relative_to(DIR.parent))
    except ValueError:
        return str(path)


def stats(fs):
    print("| Class | Open | Adopted | Rejected | Noise |")
    print("|---|---|---|---|---|")
    for c in CLASSES:
        counts = [sum(1 for f in fs if f.get("class") == c and f.get("status") == s) for s in STATUS]
        print(f"| {c} | " + " | ".join(map(str, counts)) + " |")


def check(fs):
    bad = [(rel(f["path"]), p) for f in fs for p in problems(f)]
    for name, p in bad:
        print(f"{name}: {p}")
    print(f"{len(fs)} findings, {len(bad)} problems")
    return 1 if bad else 0


def main(args):
    fs = [load(p) for folder in sorted(DIR.glob("*/findings")) for p in register_files(folder)] if DIR.is_dir() else []
    cmd = args[0] if args else "list"
    if cmd == "list":
        for f in fs:
            print(f"{rel(f['path'])}\t{f.get('class')}\t{f.get('status')}\t{f.get('touches')}")
    elif cmd == "stats":
        stats(fs)
    elif cmd == "check":
        return check(fs)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
