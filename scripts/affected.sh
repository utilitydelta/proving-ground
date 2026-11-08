#!/usr/bin/env bash
# The targeted checks for what changed in the human repo: the commands from harness/coverage.tsv whose glob matches a
# path changed in HUMAN_REPO since <base-ref>.
#
#   scripts/affected.sh [--run] [--tier quick|harness|full] [base-ref]   (flags in any order; base default HEAD:
#                                                                        uncommitted and untracked changes only)
#
# Changed paths: `git diff --name-only <base>` (committed since base, staged and unstaged) plus untracked files not
# ignored. coverage.tsv columns: glob, command, tier, budget_s, plant; lines starting with # are comments. Globs are
# relative to HUMAN_REPO: `*` and `?` stay within one path segment, `**` crosses them. Only rows up to the max tier
# count: default quick (probe, targeted and quick rows), `--tier harness` or `--tier full` to go higher. Each matching
# command once, tiers in the order probe, targeted, quick, harness, full. With no match it says so and names the quick
# gate. COVERAGE overrides the table's path (tests).
#
# Commands name the tree as $TREE, never a path. Here TREE is HUMAN_REPO, the live tree: targeted runs see the
# human's uncommitted edits (the gate is what snapshots). Without --run each command is printed ready to paste:
# `TREE=<HUMAN_REPO> bash -c '<command>'`. With --run each runs through scripts/run.sh (harness and full rows with -H)
# from this repo's root, one `OK|FAIL|BLIND <secs>s <command>` line each (lib/verdict.sh) with the log's tail when not
# OK, logs under RUN_DIR/logs/affected-<time>-<pid>/, exit as a gate does. Under --run a changed path that no counted
# row covers is a blind spot: one `BLIND affected (...)` line naming the paths, and exit 2.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
# shellcheck source=lib/verdict.sh
source "$ROOT/scripts/lib/verdict.sh"
usage() { sed -n 5,6p "$0" >&2; exit 2; }
run=0 max_tier=quick base=
while (( $# )); do
    case $1 in
        --run) run=1; shift ;;
        --tier) [[ ${2:-} == @(quick|harness|full) ]] || usage; max_tier=$2; shift 2 ;;
        -*) usage ;;
        *) [[ -z $base ]] || usage; base=$1; shift ;;
    esac
done
base=${base:-HEAD}
table=${COVERAGE:-$ROOT/harness/coverage.tsv}
[[ -d $HUMAN_REPO ]] || { echo "affected: HUMAN_REPO $HUMAN_REPO is not a directory" >&2; exit 2; }
[[ -f $table ]] || { echo "affected: no coverage table at $table" >&2; exit 2; }
changed=$( { git -C "$HUMAN_REPO" diff --name-only --relative "$base" --
             git -C "$HUMAN_REPO" ls-files --others --exclude-standard; } | sort -u) \
    || { echo "affected: git failed in $HUMAN_REPO (is $base a ref there?)" >&2; exit 2; }

# tier<TAB>command per matching row, cheapest tier first.
# hit<TAB>tier<TAB>command per matching row, cheapest tier first, then blind<TAB>path per path no counted row covers.
hits=$(CHANGED=$changed python3 - "$table" "$HUMAN_REPO" "$max_tier" <<'PY'
import os, re, sys

TIERS = ["probe", "targeted", "quick", "harness", "full"]
table, human, max_tier = sys.argv[1], sys.argv[2], sys.argv[3]
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
        if cols[2] in TIERS and TIERS.index(cols[2]) <= TIERS.index(max_tier):
            rows.append((n, cols[0], cols[1], cols[2]))

if not changed:
    print(f"affected: nothing changed in {human} since the base; nothing to run", file=sys.stderr)
    sys.exit(0)
hits, covered = {}, set()
for n, glob, command, tier in rows:
    matched = {p for p in changed if pattern(glob).match(p)}
    if matched:
        covered |= matched
        hits.setdefault(command, (TIERS.index(tier), n, tier))
if not hits:
    print(f"affected: no coverage row up to tier {max_tier} matches the {len(changed)} changed path(s); run the "
          f"quick gate: scripts/gate.sh {human} quick", file=sys.stderr)
for command in sorted(hits, key=hits.get):
    print(f"hit\t{hits[command][2]}\t{command}")
for path in changed:
    if path not in covered:
        print(f"blind\t{path}")
PY
)
[[ -n $hits ]] || exit 0
export TREE=$HUMAN_REPO
uncovered=$(awk -F'\t' '$1 == "blind" { print $2 }' <<< "$hits")
commands=$(awk -F'\t' '$1 == "hit" { sub(/^hit\t/, ""); print }' <<< "$hits")
if (( ! run )); then
    [[ -n $uncovered ]] && echo "affected: no row up to tier $max_tier covers: $(paste -sd' ' <<< "$uncovered")" >&2
    while IFS=$'\t' read -r _tier command; do
        [[ -n $command ]] && printf 'TREE=%q bash -c %q\n' "$TREE" "$command"
    done <<< "$commands"
    exit 0
fi
blind=0 failed=0 i=0
logs=$RUN_DIR/logs/affected-$(date +%Y%m%d-%H%M%S)-$$
mkdir -p "$logs"
while IFS=$'\t' read -r tier command; do
    [[ -n $command ]] || continue
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
done <<< "$commands"
if [[ -n $uncovered ]]; then
    echo "BLIND affected ($(wc -l <<< "$uncovered") changed path(s) no row up to tier $max_tier covers:" \
        "$(paste -sd' ' <<< "$uncovered"))"
    blind=$(( blind + 1 ))
fi
echo "affected: logs $logs" >&2
gate_exit "$blind" "$failed"
