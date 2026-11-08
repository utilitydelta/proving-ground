#!/usr/bin/env python3
"""List and lint the risk register in risks/.

  scripts/risks.py            every risk, highest score first
  scripts/risks.py list       the same
  scripts/risks.py open       score 5 and up that is neither controlled nor accepted: owes a control or the human's call
  scripts/risks.py check      exit 1 on a malformed file or an unfilled skeleton placeholder (scripts/skeleton.py)

Files are risks/RNNN-<slug>.md with a '# RNNN: <title>' line. RISKS_DIR overrides the folder (tests).
check judges every *.md but README.md (a misnamed or non-UTF-8 file is a problem) and enforces AGENTS.md: score ==
likelihood x consequence, both 1-5, status in the enum. Status and control agree at any score: controlled and proposed
name a control (not `none`), open may say none. open and proposed pass at any score: they are the queue. controlled or accepted at 12 and up needs a control (not `none`) and cites a decision
that exists in decisions/. accepted at 5 to 11 cites a decision that exists and has been made (not open, not
decided_by none). DECISIONS_DIR overrides where cited decisions are looked up.
Columns: id, score, likelihood x consequence, status, decision, title.
"""
import os
import pathlib
import re
import sys

import decisions
from skeleton import placeholder_problems, read_register, register_files

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = pathlib.Path(os.environ.get("RISKS_DIR") or ROOT / "risks")
STATUS = ("controlled", "accepted", "proposed", "open")
REQUIRED = ("likelihood", "consequence", "score", "control", "status", "decision", "session", "evidence")
DECISION_ID = re.compile(r"\bD-\d+\b")


NAME = re.compile(r"R\d+-.+\.md")
NO_CONTROL = ("none", "")


def load(path):
    text, unreadable = read_register(path)
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fields = {k: v.strip() for k, v in re.findall(r"^(\w+):[ \t]*(.*)$", m.group(1), re.M)} if m else {}
    title = re.search(r"^# (R\d+): (.*)$", text, re.M)
    fields["id"], fields["title"] = (title.group(1), title.group(2)) if title else (path.stem, "")
    fields["path"] = path
    fields["frontmatter"] = bool(m)
    fields["unreadable"], fields["text"] = unreadable, text
    return fields


def number(d, key):
    value = d.get(key, "")
    return int(value) if value.isdigit() else None


def decision_index():
    """D-NNN -> its fields, for every decision on disk."""
    folder = decisions.DIR
    return {d["id"]: d for d in map(decisions.load, register_files(folder))}


def problems(d, known):
    if d["unreadable"]:
        return [d["unreadable"]]
    if not NAME.fullmatch(d["path"].name):
        return [f"file name {d['path'].name} is not RNNN-<slug>.md"]
    if not d["frontmatter"]:
        return ["no --- frontmatter block"]
    out = [f"missing {k}" for k in REQUIRED if not d.get(k)]
    lik, con, score = number(d, "likelihood"), number(d, "consequence"), number(d, "score")
    for key, value in (("likelihood", lik), ("consequence", con)):
        if value is None or not 1 <= value <= 5:
            out.append(f"{key} {d.get(key)!r} not 1-5")
    if lik and con and score != lik * con:
        out.append(f"score {d.get('score')!r} is not {lik} x {con} = {lik * con}")
    status = d.get("status")
    if status not in STATUS:
        out.append(f"status {status!r} not one of {', '.join(STATUS)}")
    control = d.get("control", "none").strip().lower()
    if status in ("controlled", "proposed") and control in NO_CONTROL:
        out.append(f"{status} with control: none; name the control it has or proposes")
    cited = DECISION_ID.findall(d.get("decision", ""))
    missing = [c for c in cited if c not in known]
    if score is not None and status in ("controlled", "accepted") and score >= 12:
        if status == "accepted" and control in NO_CONTROL:
            out.append(f"{status} at score {score} with control: none; 12 and up needs a control")
        if not cited or missing:
            out.append(f"{status} at score {score} must cite an existing decision (decision: {d.get('decision')!r})")
    if score is not None and 5 <= score <= 11 and status == "accepted":
        made = [c for c in cited if c in known and known[c].get("status") != "open"
                and known[c].get("decided_by") not in ("none", None)]
        if not made:
            out.append(f"accepted at score {score} must cite the decision that accepted it, existing and made "
                       f"(not open, not decided_by none); decision: {d.get('decision')!r}")
    if not d["title"]:
        out.append("no '# RNNN: title' line")
    elif d["id"] != d["path"].name.split("-")[0]:
        out.append(f"id {d['id']} does not match file name")
    return out + placeholder_problems(d["text"])


def score_of(d):
    return number(d, "score") or 0


def show(rs):
    for r in rs:
        print(f"{r['id']}\t{r.get('score')}\t{r.get('likelihood')}x{r.get('consequence')}\t{r.get('status')}\t"
              f"{r.get('decision')}\t{r['title']}")


def check(rs):
    known = decision_index()
    bad = [(r["path"].name, p) for r in rs for p in problems(r, known)]
    ids = [r["id"] for r in rs]
    bad += [(i, "duplicate id") for i in sorted({i for i in ids if ids.count(i) > 1})]
    for name, p in bad:
        print(f"{name}: {p}")
    print(f"{len(rs)} risks, {len(bad)} problems")
    return 1 if bad else 0


def main(args):
    rs = [load(p) for p in register_files(DIR)]
    rs.sort(key=lambda r: (-score_of(r), r["path"].name))
    cmd = args[0] if args else "list"
    if cmd == "list":
        show(rs)
    elif cmd == "open":
        show([r for r in rs if score_of(r) >= 5 and r.get("status") not in ("controlled", "accepted")])
    elif cmd == "check":
        return check(rs)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
