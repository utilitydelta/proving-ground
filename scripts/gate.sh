#!/usr/bin/env bash
# The one pass/fail command over a product tree.
#
#   scripts/gate.sh <tree> [quick|harness|full]          (default tier quick)
#
# Contract (adopters keep it when they add stages):
# - One line per stage: `OK|FAIL|BLIND <stage> <secs>s`, two decimals. The verdict comes from lib/verdict.sh: BLIND
#   when the stage could not judge (heavy slot busy, timeout, cannot run, killed; exit 2 too for a stage declared
#   with -b). Stages run no-fail-fast. Exit 0 when every stage is OK, 2 when any is BLIND, else 1.
# - Stages: `lint` first (scripts/lint.py on this repo's working tree: registers, findings, INDEX, frozen sessions;
#   seconds), then the product stages in the ADOPT block below. Bot tooling self-tests are not here: they are
#   scripts/check-tooling.sh, their own gate.
# - Tiers nest: quick < harness < full. A stage declared with tier-min runs in that tier and every higher one.
#   quick: what an agent runs after every change, within the quick budget in INDEX.md. harness: every harness
#   compiles and every coverage row goes red on its plant (scripts/coverage-plants.sh). full: sweeps and proofs; every
#   stage runs heavy (-H). A stage's declared -t stays its cap in every tier.
# - Snapshots, never a live tree. Stages run from a `git archive HEAD` copy of this repo, through that copy's own
#   scripts/run.sh and lib/verdict.sh, so uncommitted harness or tooling edits cannot change a verdict. TREE is exported as a snapshot of <tree>: the human tree (HUMAN_REPO) with its
#   uncommitted edits (the gate prints its HEAD and a dirty hash), any other git tree at HEAD, a plain dir as is.
#   GATE_TIER is exported too. The work dir is removed when every stage is OK and kept, with its path printed, when
#   any is not. Logs go to RUN_DIR/logs/gate-<time>-<pid>/; scripts/clean-tmp.sh ages them out.
set -uo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
# shellcheck source=lib/verdict.sh
source "$ROOT/scripts/lib/verdict.sh"
(( $# >= 1 )) || { sed -n 4p "$0" >&2; exit 2; }
GATE_TIER=${2:-quick}
case $GATE_TIER in quick|harness|full) ;; *) echo "gate: tier must be quick, harness or full" >&2; exit 2 ;; esac
tree=$(cd "$1" 2> /dev/null && pwd -P) || { echo "BLIND snapshot 0.00s"; echo "    gate: no tree at $1"; exit 2; }
# Shared with every nested run.sh so temp dirs stay this clone's and heavy slots this machine's.
export RUN_DIR PG_TMP HEAVY_DIR GATE_TIER
logs=$RUN_DIR/logs/gate-$(date +%Y%m%d-%H%M%S)-$$
mkdir -p "$logs"
work=$(mktemp -d "$PG_TMP/gate.XXXXXX")
blind=0 failed=0 stages=0

rank() { case $1 in quick) echo 1 ;; harness) echo 2 ;; full) echo 3 ;; *) echo 0 ;; esac; }

# stage <name> <tier-min> [-H] [-t secs] [-b] -- <cmd...>
#   -H heavy (scripts/run.sh -H), -t timeout (default RUN_TIMEOUT; the cap at every tier), -b exit 2 means BLIND (a
#   build or usage failure, or a nested gate or grader that exits 2 for BLIND). Runs <cmd> from the bot snapshot
#   through the snapshot's scripts/run.sh.
stage() {
    local name=$1 min=$2 limit=$RUN_TIMEOUT heavy=0 usage_blind=0 began rc verdict
    shift 2
    (( $(rank "$min") )) || { echo "gate: stage $name: tier-min must be quick, harness or full" >&2; exit 2; }
    while [[ ${1:-} != -- ]]; do
        case ${1:-} in
            -H) heavy=1; shift ;;
            -t) limit=$2; shift 2 ;;
            -b) usage_blind=1; shift ;;
            *) echo "gate: stage $name: unknown flag ${1:-(none)}; usage: stage <name> <tier-min> [-H] [-t s] [-b] -- cmd" >&2
               exit 2 ;;
        esac
    done
    shift
    (( $(rank "$GATE_TIER") >= $(rank "$min") )) || return 0
    stages=$(( stages + 1 ))
    [[ $GATE_TIER == full ]] && heavy=1
    local flags=(-t "$limit")
    (( heavy )) && flags+=(-H)
    began=$(now)
    (cd "$work/bots" && "$work/bots/scripts/run.sh" "${flags[@]}" -l "$logs/$name.log" -- "$@") 2> "$logs/$name.run"
    rc=$?
    verdict=$(verdict_of "$rc" "$usage_blind")
    echo "$verdict $name $(secs "$began" "$(now)")s"
    case $verdict in
        OK) return 0 ;;
        BLIND) blind=$(( blind + 1 )) ;;
        *) failed=$(( failed + 1 )) ;;
    esac
    # run.sh ends its log with the verdict line it also writes to stderr; the stderr file matters only without a log.
    if [[ -s $logs/$name.log ]]; then
        tail -n 20 "$logs/$name.log" | sed 's/^/    /'
    else
        sed 's/^/    /' "$logs/$name.run"
    fi
}

# Tracked plus untracked-not-ignored, minus tracked files deleted in the worktree.
snapshot_live() {
    (cd "$1" && git ls-files -co --exclude-standard -z \
        | while IFS= read -r -d '' f; do [[ -e $f || -L $f ]] && printf '%s\0' "$f"; done \
        | tar --null -T - -cf -) | tar -C "$2" -xf -
}

# Committed state of <src> (its subtree when <src> sits below the top of its checkout); a plain copy outside git.
snapshot_head() {
    local prefix
    if prefix=$(git -C "$1" rev-parse --show-prefix 2> /dev/null); then
        git -C "$1" archive "HEAD:$prefix" | tar -C "$2" -xf -
    else
        tar -C "$1" --exclude=.git -cf - . | tar -C "$2" -xf -
    fi
}

sha256() { if command -v sha256sum > /dev/null; then sha256sum; else shasum -a 256; fi | cut -c1-16; }

# "clean", or a hash of the uncommitted diff and the untracked files under <tree>.
dirty_hash() {
    (
        cd "$1" || exit 1
        [[ -z $(git status --porcelain -- .) ]] && { echo clean; exit 0; }
        { git diff HEAD --binary -- .
          git ls-files -o --exclude-standard -z -- . | while IFS= read -r -d '' f; do
              printf '%s\0' "$f"; cat "$f" 2> /dev/null; done; } | sha256
    )
}

human=$(cd "$HUMAN_REPO" 2> /dev/null && pwd -P || true)
mkdir -p "$work/bots" "$work/tree"
if [[ $tree == "$human" ]]; then
    echo "gate: human tree $tree HEAD $(git -C "$tree" rev-parse --short HEAD 2> /dev/null || echo none)" \
        "dirty $(dirty_hash "$tree" 2> /dev/null || echo unknown), tier $GATE_TIER"
    snapshot=snapshot_live
else
    echo "gate: tree $tree, tier $GATE_TIER"
    snapshot=snapshot_head
fi
began=$(now)
if ! { git -C "$ROOT" archive HEAD | tar -C "$work/bots" -xf -; } 2> "$logs/snapshot.log" \
    || ! $snapshot "$tree" "$work/tree" 2>> "$logs/snapshot.log"; then
    echo "BLIND snapshot $(secs "$began" "$(now)")s"
    sed 's/^/    /' "$logs/snapshot.log"
    echo "gate: kept $work" >&2
    exit 2
fi
# From here on the verdict mapping is the committed one, like run.sh.
# shellcheck source=lib/verdict.sh
source "$work/bots/scripts/lib/verdict.sh"
export TREE=$work/tree
# Git in a copy must never find this repo above it.
export GIT_CEILING_DIRECTORIES=$PG_TMP

began=$(now)
(cd "$ROOT" && python3 scripts/lint.py) > "$logs/lint.log" 2>&1
rc=$?
verdict=$(verdict_of "$rc")
echo "$verdict lint $(secs "$began" "$(now)")s"
if [[ $verdict != OK ]]; then
    failed=$(( failed + 1 ))
    tail -n 20 "$logs/lint.log" | sed 's/^/    /'
fi

# ADOPT: product stages below. One line per stage: stage <name> <tier-min> [-H] [-t secs] [-b] -- <cmd>. Commands run
# from this repo's committed snapshot with TREE (the product snapshot) and GATE_TIER exported, and read the product
# only through "$TREE". These are the worked example's stages, the pattern to copy: unit and sim at quick, compile
# and coverage-plants at harness, a heavy sweep at full. Replace them; scripts/lint.py --adoption fails while any
# line here names examples/kv-python.
stage unit quick -t 60 -- python3 -m unittest discover -s examples/kv-python/harness -p 'test_*.py'
stage sim quick -t 60 -- python3 examples/kv-python/harness/sim.py --tree "$TREE" --seeds 200 --timeout 50
stage compile harness -t 60 -- python3 -c 'import sys
for f in sys.argv[1:]: compile(open(f).read(), f, "exec")' examples/kv-python/harness/*.py
stage coverage-plants harness -t 240 -b -- bash scripts/coverage-plants.sh "$TREE"
stage sweep full -H -t 300 -- python3 examples/kv-python/harness/sim.py --tree "$TREE" --seeds 2000 --start 200 \
    --timeout 280
# ADOPT: product stages above.

if (( stages == 0 )); then
    echo "BLIND product 0.00s"
    echo "    gate: no product stage runs at tier $GATE_TIER: add them in the ADOPT block of scripts/gate.sh"
    blind=$(( blind + 1 ))
fi

echo "gate: logs $logs" >&2
if (( blind + failed )); then
    echo "gate: kept $work" >&2
else
    drop_tmp "$work"
fi
gate_exit "$blind" "$failed"
