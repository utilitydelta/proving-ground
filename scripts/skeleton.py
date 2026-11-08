#!/usr/bin/env python3
"""Register skeletons: the one source for what scripts/new-id.sh writes and what the checks call unfilled.

  scripts/skeleton.py render <decision|risk|finding> <num> <title> <session> <date>   prints the skeleton

decisions.py, risks.py and findings.py import placeholder_problems(): a line still holding one of the literal
placeholder strings below is unfilled. Only these exact strings count, so prose such as Vec<u8>, <path> in a quoted
command, or anything inside backticks passes.
"""
import re
import sys

TEMPLATES = {
    "decision": """---
status: open
decided_by: none
touches: <path::Symbol in the human repo, lead or a harness>
revisit_when: <the event that reopens it>
session: {session}
---
# D-{num}: {title}

<Why, in a sentence or two. Alternatives and why not. Evidence: command or file.>

## History
- {date} {session}: opened
""",
    "risk": """---
likelihood: <1-5>
consequence: <1-5>
score: <likelihood x consequence>
control: none
status: open
decision: none
session: {session}
evidence: <command, test or tape that shows the scenario>
---
# R{num}: {title}

<What happens, step by step. Why this likelihood and consequence. The control and its cost in state, or why none.>

## History
- {date} {session}: raised
""",
    "finding": """---
class: <one-way-door | time-sink | regression | two-way-door>
status: open
touches: <path::Symbol in the human repo>
evidence: <one command that reproduces it from this repo>
---
<Claim in one sentence. Evidence output. What the human might do about it.>
""",
}

PLACEHOLDERS = sorted({m for t in TEMPLATES.values() for m in re.findall(r"<[^<>\n]+>", t)}, key=len, reverse=True)
BACKTICKED = re.compile(r"`[^`\n]*`")


def placeholder_problems(text):
    """One line per line still holding a skeleton placeholder, text inside backticks ignored."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        bare = BACKTICKED.sub("", line)
        hit = next((p for p in PLACEHOLDERS if p in bare), None)
        if hit:
            out.append(f"line {n} still holds a skeleton placeholder: {hit}")
    return out


def main(args):
    if len(args) == 6 and args[0] == "render" and args[1] in TEMPLATES:
        kind, num, title, session, date = args[1:]
        sys.stdout.write(TEMPLATES[kind].format(num=num, title=title, session=session, date=date))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
