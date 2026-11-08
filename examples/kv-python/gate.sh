#!/usr/bin/env bash
# One pass/fail over a product tree, to the contract in scripts/gate.sh.
#
#   examples/kv-python/gate.sh <tree> [quick|harness|full]
#
#   quick    unit tests, sim 200 seeds
#   harness  every harness module compiles, every plant in plants/ applies and turns its check red
#   full     quick, harness, then a 2000-seed sweep (seeds 200..2199) as a heavy run
#
# The tree is snapshotted first, uncommitted edits included (git ls-files -co --exclude-standard, or a plain copy
# outside git), into a fresh mktemp -d under PG_TMP; every stage runs on the snapshot under scripts/run.sh with its
# own log and TREE set to the snapshot; run.sh exports PYTHONPYCACHEPREFIX. One line per
# stage: OK|FAIL|BLIND <stage> <secs>s (scripts/lib/verdict.sh).
# Stages run no-fail-fast. Exit 0 if every stage is OK, 2 if any is BLIND (a failed snapshot included), else 1.
# On exit 0 the run dir is removed; otherwise it is kept and printed on stderr (logs, tapes) for scripts/clean-tmp.sh.
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$here/../.." && pwd)
(( $# >= 1 )) || { sed -n 4p "$0" >&2; exit 2; }
tree=$(cd "$1" 2> /dev/null && pwd) || { echo "BLIND snapshot 0.00s"; echo "    gate: no tree at $1"; exit 2; }
tier=${2:-quick}
case $tier in quick|harness|full) ;; *) echo "gate: tier must be quick, harness or full, got $tier" >&2; exit 2 ;; esac
# shellcheck source=../../scripts/lib/verdict.sh
source "$root/scripts/lib/verdict.sh" 2> /dev/null \
    || { echo "BLIND verdict 0.00s"; echo "    gate: cannot source $root/scripts/lib/verdict.sh"; exit 2; }

harness=$here/harness
mkdir -p "${PG_TMP:=$root/.run/tmp}"
work=$(mktemp -d "$PG_TMP/kv-gate.XXXXXX") \
    || { echo "BLIND snapshot 0.00s"; echo "    gate: no temp dir under $PG_TMP"; exit 2; }
snap=$work/tree logs=$work/logs out=$work/out
mkdir -p "$snap" "$logs" "$out"

snapshot() {
    if git -C "$tree" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        # Tracked plus untracked-not-ignored, minus tracked files deleted in the worktree.
        (cd "$tree" && git ls-files -co --exclude-standard -z \
            | while IFS= read -r -d '' f; do [[ -e $f || -L $f ]] && printf '%s\0' "$f"; done \
            | tar --null -T - -cf -) | tar -C "$snap" -xf -
    else
        tar -C "$tree" --exclude=.git -cf - . | tar -C "$snap" -xf -
    fi
}
if ! snapshot 2> "$logs/snapshot.log"; then
    echo "BLIND snapshot 0.00s"
    echo "    gate: could not copy $tree into $snap"
    sed 's/^/    /' "$logs/snapshot.log"
    echo "gate: run dir kept: $work" >&2
    exit 2
fi
echo "gate: tree $tree, tier $tier, run dir $work" >&2

blind=0 failed=0
# stage <name> <timeout> <usage-is-blind> [run.sh flags...] -- <cmd...>
stage() {
    local name=$1 limit=$2 usage_blind=$3 began rc verdict
    shift 3
    local flags=()
    while [[ $1 != -- ]]; do flags+=("$1"); shift; done
    began=$(now)
    (cd "$root" && TREE=$snap \
        "$root/scripts/run.sh" -t "$limit" ${flags[@]+"${flags[@]}"} -l "$logs/$name.log" "$@") 2> "$logs/$name.run"
    rc=$?
    verdict=$(verdict_of "$rc" "$usage_blind")
    echo "$verdict $name $(secs "$began" "$(now)")s"
    case $verdict in
        OK) return ;;
        BLIND) blind=1 ;;
        *) failed=1 ;;
    esac
    # run.sh ends its log with the line it also writes to stderr; the stderr file matters only when there is no log.
    if [[ -s $logs/$name.log ]]; then
        tail -n 15 "$logs/$name.log" | sed 's/^/    /'
    else
        sed 's/^/    /' "$logs/$name.run"
    fi
}

# usage-is-blind: plants.sh exits 2 for a BLIND plant; run.sh exits 2 on a refused -t for every stage, but a
# Python stage's own 2 (argparse) cannot be told apart from it, so those count it as FAIL.
if true; then  # tiers nest: quick stages run in every tier
    stage unit 60 0 -- python3 -m unittest discover -s "$harness" -p 'test_*.py'
    stage sim 60 0 -- python3 "$harness/sim.py" --tree "$snap" --seeds 200 --timeout 50 --tape-dir "$out/sim"
fi
if [[ $tier == harness || $tier == full ]]; then
    # compile() rather than py_compile: checks syntax without writing a .pyc anywhere.
    stage compile 60 0 -- python3 -c 'import sys
for f in sys.argv[1:]: compile(open(f).read(), f, "exec")' "$harness"/*.py
    stage plants 240 1 -- "$root/scripts/plants.sh" "$snap" "$here/plants"
fi
if [[ $tier == full ]]; then
    stage sweep 300 0 -H -- python3 "$harness/sim.py" --tree "$snap" --seeds 2000 --start 200 --timeout 280 \
        --tape-dir "$out/sweep"
fi

if (( blind || failed )); then
    echo "gate: run dir kept: $work" >&2
    gate_exit "$blind" "$failed"
fi
# drop_tmp (lib/verdict.sh) removes the dir only when it resolves inside PG_TMP.
drop_tmp "$work" || echo "gate: run dir kept: $work" >&2
gate_exit 0 0
