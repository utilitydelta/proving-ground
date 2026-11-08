#!/usr/bin/env bash
# The one pass/fail command over a tree. A stub for the product stages until the adopting project writes them.
#
#   scripts/gate.sh <tree> [quick|harness|full]          (default tier quick)
#
# Contract (the stub keeps it; the real gate must too):
# - Each stage prints one line: `OK|FAIL|BLIND <stage> <secs>s`. BLIND means the stage could not build, run or apply
#   (run.sh 75, 126, 127, a snapshot that failed). BLIND is never OK. Exit 0 only if every stage is OK; 2 when any
#   stage is BLIND, else 1. Stages run no-fail-fast: one red stage does not hide the next one's verdict.
# - Tiers. quick: the targeted checks an agent runs after every change, within the quick budget INDEX.md records.
#   harness: every harness compiles and every plant (scripts/plants.sh) applies and turns its check red. full: every
#   tier, sweeps and proofs included; its stages run with run.sh -H.
# - Every stage runs through scripts/run.sh with its own timeout, its own log under RUN_DIR/logs/gate-<time>-<pid>/
#   and its own RUN_OUT.
# - Snapshots, never the live worktree. Bot trees (this repo, lead) are copied with `git archive HEAD` into
#   `mktemp -d "$PG_TMP/..."`: an agent editing mid-run cannot change the verdict, and uncommitted files cannot make
#   it green. The human tree (HUMAN_REPO) is copied with its uncommitted edits (`git ls-files -co --exclude-standard`
#   through tar), because the human gates what they are typing; the gate prints its HEAD and a dirty hash so a verdict
#   names exactly what it judged.
#
# Stages here:
# - bot-tooling: scripts/check-tooling.sh <tier> over a `git archive HEAD` copy of this repo.
# - product: if <tree> is examples/kv-python/product, delegated to examples/kv-python/gate.sh (from the same archive
#   copy) with the same tier. Otherwise BLIND with the message to write them. `scripts/lint.py --adoption` fails while
#   this file still delegates to the example.
set -uo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
(( $# >= 1 )) || { sed -n 4p "$0" >&2; exit 2; }
tier=${2:-quick}
case $tier in quick|harness|full) ;; *) echo "gate: tier must be quick, harness or full" >&2; exit 2 ;; esac
tree=$(cd "$1" 2> /dev/null && pwd -P) || { echo "BLIND product 0s"; echo "    gate: no tree at $1"; exit 2; }
# Shared with every nested run.sh, the copies' included, so heavy slots and temp dirs stay this machine's.
export RUN_DIR PG_TMP
heavy=()
[[ $tier == full ]] && heavy=(-H)
logs=$RUN_DIR/logs/gate-$(date +%Y%m%d-%H%M%S)-$$
mkdir -p "$logs"
blind=0 failed=0

verdict() {
    local name=$1 code=$2 took=$3
    case $code in
        0) echo "OK $name ${took}s" ;;
        75|126|127) echo "BLIND $name ${took}s"; blind=1 ;;
        *) echo "FAIL $name ${took}s"; failed=1 ;;
    esac
    (( code == 0 )) || tail -n 20 "$logs/$name.log" 2> /dev/null | sed 's/^/    /'
}

# Bot tree: committed state only.
snapshot_bot() {
    local src=$1 dest=$2
    git -C "$src" archive HEAD | tar -C "$dest" -xf -
}

# Human tree: tracked plus untracked-not-ignored, minus tracked files deleted in the worktree.
snapshot_human() {
    local src=$1 dest=$2
    (cd "$src" && git ls-files -co --exclude-standard -z \
        | while IFS= read -r -d '' f; do [[ -e $f || -L $f ]] && printf '%s\0' "$f"; done \
        | tar --null -T - -cf -) | tar -C "$dest" -xf -
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
if [[ $tree == "$human" ]]; then
    echo "gate: human tree $tree HEAD $(git -C "$tree" rev-parse --short HEAD 2> /dev/null || echo none)" \
        "dirty $(dirty_hash "$tree" 2> /dev/null || echo unknown), tier $tier"
else
    echo "gate: bot tree $tree, tier $tier"
fi

# Git in a copy must never find this repo above it.
export GIT_CEILING_DIRECTORIES=$PG_TMP
start=$SECONDS
bots=$(mktemp -d "$PG_TMP/gate-bots.XXXXXX")
if snapshot_bot "$ROOT" "$bots" 2> "$logs/bot-tooling.log"; then
    limit=120
    [[ $tier != quick ]] && limit=300
    (cd "$bots" && "$ROOT/scripts/run.sh" -t "$limit" ${heavy[@]+"${heavy[@]}"} -l "$logs/bot-tooling.log.run" \
        -- bash scripts/check-tooling.sh "$tier") 2> /dev/null
    code=$?
    cat "$logs/bot-tooling.log.run" >> "$logs/bot-tooling.log"
else
    code=126
fi
verdict bot-tooling "$code" $(( SECONDS - start ))

example=$(cd "$ROOT/examples/kv-python/product" 2> /dev/null && pwd -P || true)
if [[ -n $example && $tree == "$example" ]]; then
    bash "$bots/examples/kv-python/gate.sh" "$tree" "$tier"
    case $? in 0) ;; 1) failed=1 ;; *) blind=1 ;; esac
else
    snap=$(mktemp -d "$PG_TMP/gate-tree.XXXXXX")
    if [[ $tree == "$human" ]]; then snapshot_human "$tree" "$snap"; else snapshot_bot "$tree" "$snap"; fi \
        || echo "    gate: snapshot of $tree into $snap failed"
    echo "BLIND product 0s \"gate.sh has no stages for $tree: write them (contract above)\""
    blind=1
fi

echo "gate: logs $logs" >&2
(( blind )) && exit 2
(( failed )) && exit 1
exit 0
