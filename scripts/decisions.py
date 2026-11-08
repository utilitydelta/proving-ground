#!/usr/bin/env python3
"""List and lint the decision register in decisions/.

  scripts/decisions.py                    every decision, one line each
  scripts/decisions.py provisional        decided by bot or human-asked: what close-off and debrief walk
  scripts/decisions.py open               open and deferred, with their triggers
  scripts/decisions.py touches <text>     decisions whose touches contains <text>
  scripts/decisions.py trigger <text>     decisions whose revisit_when contains <text>
  scripts/decisions.py stats              count by decided_by and status, overturn rate per source, provisional count
  scripts/decisions.py brief <session>    one prose line per decision of that session, owner and status spelled out
  scripts/decisions.py brief <text>       the same for decisions whose touches contains <text>
  scripts/decisions.py check              exit 1 on a malformed file

Files are decisions/NNN-<slug>.md with a '# D-NNN: <title>' line. DECISIONS_DIR overrides the folder (tests).
Columns: id, status, decided_by, touches, title.
"""
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIR = pathlib.Path(os.environ.get("DECISIONS_DIR") or ROOT / "decisions")
STATUS = ("open", "decided", "deferred", "confirmed", "overturned")
BY = ("bot", "human-asked", "human-informed", "none")
REQUIRED = ("status", "decided_by", "touches", "revisit_when", "session")
# A trigger is an event (a module lands, a bench exists). A session number is a date in disguise: nobody watches for it.
SESSION_TRIGGER = re.compile(r"\bsession-v?\d+\b", re.I)


def load(path):
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fields = {k: v.strip() for k, v in re.findall(r"^(\w+):[ \t]*(.*)$", m.group(1), re.M)} if m else {}
    title = re.search(r"^# (D-\d+): (.*)$", text, re.M)
    fields["id"], fields["title"] = (title.group(1), title.group(2)) if title else (path.stem, "")
    fields["path"] = path
    fields["frontmatter"] = bool(m)
    return fields


def problems(d):
    if not d["frontmatter"]:
        return ["no --- frontmatter block"]
    out = [f"missing {k}" for k in REQUIRED if not d.get(k)]
    if d.get("status") not in STATUS:
        out.append(f"status {d.get('status')!r} not one of {', '.join(STATUS)}")
    if d.get("decided_by") not in BY:
        out.append(f"decided_by {d.get('decided_by')!r} not one of {', '.join(BY)}")
    if not d["title"]:
        out.append("no '# D-NNN: title' line")
    elif d["id"] != "D-" + d["path"].name.split("-")[0]:
        out.append(f"id {d['id']} does not match file name")
    if d.get("status") == "overturned" and not d.get("replaced_by"):
        out.append("overturned without replaced_by")
    if d.get("status") == "confirmed" and d.get("decided_by") in ("bot", "none"):
        out.append(f"confirmed with decided_by {d.get('decided_by')}: confirmation is the human ruling by name")
    if SESSION_TRIGGER.search(d.get("revisit_when", "")):
        out.append(f"revisit_when names a session ({d['revisit_when']!r}); name the event that should reopen it")
    return out


def show(ds):
    for d in ds:
        print(f"{d['id']}\t{d.get('status')}\t{d.get('decided_by')}\t{d.get('touches')}\t{d['title']}")


def provisional(ds):
    return [d for d in ds if d.get("status") == "decided" and d.get("decided_by") in ("bot", "human-asked")]


def stats(ds):
    cols = STATUS
    print("decided_by\t" + "\t".join(cols) + "\toverturn rate")
    for by in BY:
        row = [sum(1 for d in ds if d.get("decided_by") == by and d.get("status") == c) for c in cols]
        confirmed, overturned = row[cols.index("confirmed")], row[cols.index("overturned")]
        ruled = confirmed + overturned
        rate = f"{overturned}/{ruled} ({100 * overturned // ruled}%)" if ruled else "-"
        print(by + "\t" + "\t".join(map(str, row)) + "\t" + rate)
    print(f"provisional\t{len(provisional(ds))}")


OWNER = {
    "bot": "a bot call nobody was asked about",
    "human-asked": "the human's answer to a bot question, given before reading the code",
    "human-informed": "the human's call, made with the code or evidence read",
    "none": "nobody has decided it",
}
STATE = {
    "decided": "provisional until the human confirms it by name",
    "confirmed": "confirmed by the human with the code in front of them",
    "overturned": "overturned",
    "deferred": "parked",
    "open": "open",
}


def brief(ds, key):
    for d in ds:
        wanted = d.get("session") == key if key.startswith("session-") else key in d.get("touches", "")
        if not wanted:
            continue
        tail = f", replaced by {d['replaced_by']}" if d.get("replaced_by") else ""
        when = f" Revisit when: {d.get('revisit_when')}." if d.get("status") in ("decided", "deferred", "open") else ""
        print(f"{d['id']}: {d['title']}. Owner: {OWNER.get(d.get('decided_by'), '?')}. "
              f"Status: {STATE.get(d.get('status'), '?')}{tail}.{when}\n")


def check(ds):
    bad = [(d["path"].name, p) for d in ds for p in problems(d)]
    ids = [d["id"] for d in ds]
    bad += [(i, "duplicate id") for i in sorted({i for i in ids if ids.count(i) > 1})]
    for name, p in bad:
        print(f"{name}: {p}")
    print(f"{len(ds)} decisions, {len(bad)} problems")
    return 1 if bad else 0


def main(args):
    ds = sorted((load(p) for p in DIR.glob("[0-9]*.md")), key=lambda d: d["path"].name) if DIR.is_dir() else []
    cmd = args[0] if args else "list"
    if cmd == "list":
        show(ds)
    elif cmd == "provisional":
        show(provisional(ds))
    elif cmd == "open":
        for d in ds:
            if d.get("status") in ("open", "deferred"):
                print(f"{d['id']}\t{d['status']}\t{d.get('revisit_when')}\t{d['title']}")
    elif cmd in ("touches", "trigger") and len(args) == 2:
        key = "touches" if cmd == "touches" else "revisit_when"
        show([d for d in ds if args[1] in d.get(key, "")])
    elif cmd == "stats":
        stats(ds)
    elif cmd == "brief" and len(args) == 2:
        brief(ds, args[1])
    elif cmd == "check":
        return check(ds)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
