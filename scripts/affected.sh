#!/usr/bin/env bash
# The targeted checks for what changed in the human repo: the commands from harness/coverage.tsv whose glob matches a
# path changed in HUMAN_REPO since <base-ref>.
#
#   scripts/affected.sh [--run] [base-ref]         (default HEAD: uncommitted and untracked changes only)
#
# Changed paths: `git diff --name-only <base>` (committed since base, staged and unstaged) plus untracked files not
# ignored. coverage.tsv columns: glob, command, tier, budget_s, plant; lines starting with # are comments. Globs are
# relative to HUMAN_REPO: `*` and `?` stay within one path segment, `**` crosses them. Each matching command once,
# tiers in the order probe, targeted, quick, harness, full (an unknown tier last). With no match it says so and names
# the quick gate. COVERAGE overrides the table's path (tests).
#
# Commands name the tree as $TREE, never a path. Here TREE is HUMAN_REPO, the live tree: targeted runs see the
# human's uncommitted edits (the gate is what snapshots). Without --run each command is printed ready to paste:
# `TREE=<HUMAN_REPO> bash -c '<command>'`. With --run each runs through scripts/run.sh (harness and full rows with -H)
# from this repo's root, one `OK|FAIL|BLIND <secs>s <command>` line each (lib/verdict.sh) with the log's tail when not
# OK, logs under RUN_DIR/logs/affected-<time>-<pid>/, exit as a gate does.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
# shellcheck source=lib/verdict.sh
source "$ROOT/scripts/lib/verdict.sh"
run=0
[[ ${1:-} == --run ]] && { run=1; shift; }
(( $# <= 1 )) || { sed -n 5p "$0" >&2; exit 2; }
base=${1:-HEAD}
table=${COVERAGE:-$ROOT/harness/coverage.tsv}
[[ -d $HUMAN_REPO ]] || { echo "affected: HUMAN_REPO $HUMAN_REPO is not a directory" >&2; exit 2; }
[[ -f $table ]] || { echo "affected: no coverage table at $table" >&2; exit 2; }
changed=$( { git -C "$HUMAN_REPO" diff --name-only --relative "$base" --
             git -C "$HUMAN_REPO" ls-files --others --exclude-standard; } | sort -u) \
    || { echo "affected: git failed in $HUMAN_REPO (is $base a ref there?)" >&2; exit 2; }

# tier<TAB>command per matching row, cheapest tier first.
hits=$(CHANGED=$changed python3 - "$table" "$HUMAN_REPO" <<'PY'
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
        hits.setdefault(command, (rank, n, tier))
if not hits:
    print(f"affected: no coverage row matches the {len(changed)} changed path(s); run the quick gate: "
          f"scripts/gate.sh {human} quick", file=sys.stderr)
    sys.exit(0)
for command in sorted(hits, key=hits.get):
    print(f"{hits[command][2]}\t{command}")
PY
)
[[ -n $hits ]] || exit 0
export TREE=$HUMAN_REPO
if (( ! run )); then
    while IFS=$'\t' read -r _tier command; do
        printf 'TREE=%q bash -c %q\n' "$TREE" "$command"
    done <<< "$hits"
    exit 0
fi
blind=0 failed=0 i=0
logs=$RUN_DIR/logs/affected-$(date +%Y%m%d-%H%M%S)-$$
mkdir -p "$logs"
while IFS=$'\t' read -r tier command; do
    i=$(( i + 1 ))
    flags=()
    [[ $tier == harness || $tier == full ]] && flags=(-H -t "$HEAVY_TIMEOUT_MAX")
    began=$(now)
    set +e
    (cd "$ROOT" && "$ROOT/scripts/run.sh" ${flags[@]+"${flags[@]}"} -l "$logs/$i.log" -- bash -c "$command") \
        < /dev/null 2> /dev/null
    rc=$?
    set -e
    verdict=$(verdict_of "$rc")
    echo "$verdict $(secs "$began" "$(now)")s $command"
    case $verdict in BLIND) blind=$(( blind + 1 )) ;; FAIL) failed=$(( failed + 1 )) ;; esac
    [[ $verdict == OK ]] || tail -n 15 "$logs/$i.log" | sed 's/^/    /'
done <<< "$hits"
echo "affected: logs $logs" >&2
gate_exit "$blind" "$failed"
