#!/usr/bin/env python3
"""List and lint the risk register in risks/.

  scripts/risks.py            every risk, highest score first
  scripts/risks.py list       the same
  scripts/risks.py open       score 5 and up that is neither controlled nor accepted: owes a control or the human's call
  scripts/risks.py check      exit 1 on a malformed file

Files are risks/RNNN-<slug>.md with a '# RNNN: <title>' line. RISKS_DIR overrides the folder (tests).
check enforces AGENTS.md: score == likelihood x consequence, both 1-5, status in the enum, 12 and up controlled
or backed by a decision, accepted at 5 to 11 citing the decision that accepted it.
Columns: id, score, likelihood x consequence, status, decision, title.
"""
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = pathlib.Path(os.environ.get("RISKS_DIR") or ROOT / "risks")
STATUS = ("controlled", "accepted", "proposed", "open")
REQUIRED = ("likelihood", "consequence", "score", "control", "status", "decision", "session", "evidence")
DECISION_ID = re.compile(r"\bD-\d+\b")


def load(path):
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fields = {k: v.strip() for k, v in re.findall(r"^(\w+):[ \t]*(.*)$", m.group(1), re.M)} if m else {}
    title = re.search(r"^# (R\d+): (.*)$", text, re.M)
    fields["id"], fields["title"] = (title.group(1), title.group(2)) if title else (path.stem, "")
    fields["path"] = path
    fields["frontmatter"] = bool(m)
    return fields


def number(d, key):
    value = d.get(key, "")
    return int(value) if value.isdigit() else None


def problems(d):
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
    cites = bool(DECISION_ID.search(d.get("decision", "")))
    if score is not None and score >= 12 and status != "controlled" and not cites:
        out.append(f"score {score} needs a control: status controlled or a decision behind it")
    if score is not None and 5 <= score <= 11 and status == "accepted" and not cites:
        out.append(f"accepted at score {score} without the decision that accepted it")
    if not d["title"]:
        out.append("no '# RNNN: title' line")
    elif d["id"] != d["path"].name.split("-")[0]:
        out.append(f"id {d['id']} does not match file name")
    return out


def score_of(d):
    return number(d, "score") or 0


def show(rs):
    for r in rs:
        print(f"{r['id']}\t{r.get('score')}\t{r.get('likelihood')}x{r.get('consequence')}\t{r.get('status')}\t"
              f"{r.get('decision')}\t{r['title']}")


def check(rs):
    bad = [(r["path"].name, p) for r in rs for p in problems(r)]
    ids = [r["id"] for r in rs]
    bad += [(i, "duplicate id") for i in sorted({i for i in ids if ids.count(i) > 1})]
    for name, p in bad:
        print(f"{name}: {p}")
    print(f"{len(rs)} risks, {len(bad)} problems")
    return 1 if bad else 0


def main(args):
    rs = [load(p) for p in DIR.glob("R[0-9]*.md")] if DIR.is_dir() else []
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
