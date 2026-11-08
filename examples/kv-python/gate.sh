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
# outside git), into a fresh mktemp -d; every stage runs on the snapshot under scripts/run.sh with its own log.
# One line per stage: OK|FAIL|BLIND <stage> <secs>s. Stages run no-fail-fast. Exit 0 only if every stage is OK.
# The run dir is kept and printed on stderr: tapes and logs live there. scripts/clean-tmp.sh clears it.
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$here/../.." && pwd)
(( $# >= 1 )) || { sed -n 4p "$0" >&2; exit 2; }
tree=$(cd "$1" && pwd) || { echo "gate: no tree at $1" >&2; exit 2; }
tier=${2:-quick}
case $tier in quick|harness|full) ;; *) echo "gate: tier must be quick, harness or full, got $tier" >&2; exit 2 ;; esac

harness=$here/harness
mkdir -p "${PG_TMP:=$root/.run/tmp}"
work=$(mktemp -d "$PG_TMP/kv-gate.XXXXXX")
snap=$work/tree logs=$work/logs out=$work/out
mkdir -p "$snap" "$logs" "$out"

snapshot() {
    if git -C "$tree" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        # Tracked plus untracked-not-ignored, minus tracked files deleted in the worktree.
        (cd "$tree" && git ls-files -co --exclude-standard -z \
            | while IFS= read -r -d '' f; do [[ -e $f ]] && printf '%s\0' "$f"; done \
            | tar --null -T - -cf -) | tar -C "$snap" -xf -
    else
        tar -C "$tree" --exclude=.git -cf - . | tar -C "$snap" -xf -
    fi
}
snapshot || { echo "BLIND snapshot 0.00s"; echo "    could not copy $tree into $snap"; exit 1; }
echo "gate: tree $tree, tier $tier, run dir $work" >&2

now() { if [[ -n ${EPOCHREALTIME:-} ]]; then echo "${EPOCHREALTIME/,/.}"; else date +%s; fi; }

bad=0
# stage <name> <timeout> [run.sh flags...] -- <cmd...>
stage() {
    local name=$1 limit=$2 began rc verdict
    shift 2
    local flags=()
    while [[ $1 != -- ]]; do flags+=("$1"); shift; done
    began=$(now)
    (cd "$root" && KV_TREE=$snap PYTHONPYCACHEPREFIX=$work/pyc \
        "$root/scripts/run.sh" -t "$limit" ${flags[@]+"${flags[@]}"} -l "$logs/$name.log" "$@") 2> "$logs/$name.run"
    rc=$?
    case $rc in
        0) verdict=OK ;;
        2|75|126|127|137) verdict=BLIND ;;
        3) if [[ $name == plants ]]; then verdict=BLIND; else verdict=FAIL; fi ;;
        *) verdict=FAIL ;;
    esac
    awk -v v="$verdict" -v n="$name" -v a="$began" -v b="$(now)" 'BEGIN { printf "%s %s %.2fs\n", v, n, b - a }'
    if [[ $verdict != OK ]]; then
        bad=1
        tail -n 15 "$logs/$name.log" 2> /dev/null | sed 's/^/    /'
        sed 's/^/    /' "$logs/$name.run"
    fi
}

if [[ $tier == quick || $tier == full ]]; then
    stage unit 60 -- python3 -m unittest discover -s "$harness" -p 'test_*.py'
    stage sim 60 -- python3 "$harness/sim.py" --tree "$snap" --seeds 200 --timeout 50 --tape-dir "$out/sim"
fi
if [[ $tier == harness || $tier == full ]]; then
    stage compile 60 -- python3 -m py_compile "$harness"/*.py
    stage plants 240 -- "$root/scripts/plants.sh" "$snap" "$here/plants"
fi
if [[ $tier == full ]]; then
    stage sweep 300 -H -- python3 "$harness/sim.py" --tree "$snap" --seeds 2000 --start 200 --timeout 280 \
        --tape-dir "$out/sweep"
fi

exit "$bad"
