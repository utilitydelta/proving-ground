#!/usr/bin/env bash
# The targeted checks for what changed in the human repo: the commands from harness/coverage.tsv whose glob matches a
# path changed in HUMAN_REPO since <base-ref>.
#
#   scripts/affected.sh [base-ref]         (default HEAD: uncommitted and untracked changes only)
#
# Changed paths: `git diff --name-only <base>` (committed since base, staged and unstaged) plus untracked files not
# ignored. coverage.tsv columns: glob, command, tier, budget_s, plant; lines starting with # are comments. Globs are
# relative to HUMAN_REPO: `*` and `?` stay within one path segment, `**` crosses them. Prints each matching command
# once, tiers in the order probe, targeted, quick, harness, full (an unknown tier last). With no match it says so and
# names the quick gate. COVERAGE overrides the table's path (tests).
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
(( $# <= 1 )) || { sed -n 6p "$0" >&2; exit 2; }
base=${1:-HEAD}
table=${COVERAGE:-$ROOT/harness/coverage.tsv}
[[ -d $HUMAN_REPO ]] || { echo "affected: HUMAN_REPO $HUMAN_REPO is not a directory" >&2; exit 2; }
[[ -f $table ]] || { echo "affected: no coverage table at $table" >&2; exit 2; }
changed=$( { git -C "$HUMAN_REPO" diff --name-only --relative "$base" --
             git -C "$HUMAN_REPO" ls-files --others --exclude-standard; } | sort -u) \
    || { echo "affected: git failed in $HUMAN_REPO (is $base a ref there?)" >&2; exit 2; }

CHANGED=$changed python3 - "$table" "$HUMAN_REPO" <<'PY'
import os, re, sys

TIERS = ["probe", "targeted", "quick", "harness", "full"]
table, human = sys.argv[1], sys.argv[2]
changed = [p for p in os.environ["CHANGED"].splitlines() if p]


def pattern(glob):
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out + r"\Z")


rows = []
with open(table) as f:
    for n, line in enumerate(f, 1):
        line = line.rstrip("\n")
        if n == 1 or not line.strip() or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 3:
            sys.exit(f"affected: {table}:{n}: expected glob, command, tier, budget_s, plant separated by tabs")
        rows.append((n, cols[0], cols[1], cols[2]))

if not changed:
    print(f"affected: nothing changed in {human} since the base; nothing to run", file=sys.stderr)
    sys.exit(0)
hits = {}
for n, glob, command, tier in rows:
    if any(pattern(glob).match(p) for p in changed):
        rank = TIERS.index(tier) if tier in TIERS else len(TIERS)
        hits.setdefault(command, (rank, n))
if not hits:
    print(f"affected: no coverage row matches the {len(changed)} changed path(s); run the quick gate: "
          f"scripts/gate.sh {human} quick", file=sys.stderr)
    sys.exit(0)
for command in sorted(hits, key=hits.get):
    print(command)
PY
