#!/usr/bin/env bash
# Proves each coverage row can fail: its own command must be green on a clean copy of the tree and red with its plant.
#
#   scripts/coverage-plants.sh <tree> [coverage.tsv]          (default harness/coverage.tsv)
#
# For every data row of the table with a plant (columns glob, command, tier, budget_s, plant; # lines are comments):
# copy <tree> (without .git) clean once, copy it again per row and `git apply -p1` the row's plant there, then run the
# row's command from this repo's root through scripts/run.sh, `bash -c <command>` with TREE set to the copy. Rows at
# tier harness or full run heavy (-H -t HEAVY_TIMEOUT_MAX), the rest under RUN_TIMEOUT. Each distinct command runs once
# on the clean copy. The check is the row's command itself: a plant's `# check:` line plays no part here.
#
# One line per graded row, <row> being <table name>:<line> <plant name>:
#   OK <row> <secs>s   green on the clean copy, red on the planted one
#   FAIL <row>         green on the planted copy too: the row's command is blind to its plant (often it reads a fixed
#                      path instead of TREE)
#   BLIND <row>        the plant does not apply, the command is red on the clean copy, or a run could not judge
#                      (lib/verdict.sh)
# A row without a plant gets no line; a table with no plant rows is `BLIND coverage-plants`. Exit as every gate does
# (lib/verdict.sh gate_exit). Work dirs live under one mktemp -d in PG_TMP, removed when every row is OK and kept, with
# the path on stderr, otherwise.
set -uo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
# shellcheck source=lib/verdict.sh
source "$ROOT/scripts/lib/verdict.sh"
(( $# >= 1 && $# <= 2 )) || { sed -n 4p "$0" >&2; exit 2; }
tree=$(cd "$1" 2> /dev/null && pwd) || { echo "BLIND coverage-plants (no tree at $1)"; exit 2; }
table=$(realpath -e -- "${2:-$ROOT/harness/coverage.tsv}" 2> /dev/null) \
    || { echo "BLIND coverage-plants (no table at ${2:-$ROOT/harness/coverage.tsv})"; exit 2; }
work=$(mktemp -d "$PG_TMP/coverage-plants.XXXXXX")
echo "coverage-plants: tree $tree, table $table, work dir $work" >&2

copy_tree() { mkdir -p "$1" && tar -C "$tree" --exclude=.git -cf - . | tar -C "$1" -xf -; }

# run_row <dir> <copy> <tier> <command>: sets rc to the command's exit status under run.sh.
run_row() {
    local dir=$1 copy=$2 tier=$3 command=$4 flags=(-t "$RUN_TIMEOUT")
    [[ $tier == harness || $tier == full ]] && flags=(-H -t "$HEAVY_TIMEOUT_MAX")
    mkdir -p "$dir"
    (cd "$ROOT" && TREE=$copy "$ROOT/scripts/run.sh" "${flags[@]}" -l "$dir/run.log" -- bash -c "$command") \
        < /dev/null 2> "$dir/run.line"
    rc=$?
}

clean_commands=() clean_codes=()
clean_rc() {
    local i
    for i in "${!clean_commands[@]}"; do
        [[ ${clean_commands[$i]} == "$2|$1" ]] && { rc=${clean_codes[$i]}; return; }
    done
    [[ -d $work/clean ]] || copy_tree "$work/clean"
    run_row "$work/clean-${#clean_commands[@]}" "$work/clean" "$1" "$2"
    clean_commands+=("$2|$1") clean_codes+=("$rc")
}

fails=0 blinds=0 count=0
rows=$(awk -F'\t' 'NR > 1 && !/^#/ && NF >= 5 && $5 != "" { print NR "\t" $3 "\t" $5 "\t" $2 }' "$table")
while IFS=$'\t' read -r line tier plant command; do
    [[ -n $line ]] || continue
    count=$(( count + 1 ))
    name=$(basename "$plant" .patch)
    label="$(basename "$table"):$line $name"
    dir=$work/row-$line
    patch=$(cd "$ROOT" && realpath -e -- "$plant" 2> /dev/null) \
        || { echo "BLIND $label (no plant at $plant)"; blinds=$(( blinds + 1 )); continue; }
    copy_tree "$dir/tree"
    if ! (cd "$dir/tree" && GIT_CEILING_DIRECTORIES=$dir git apply -p1 "$patch") 2> "$dir/apply.log"; then
        echo "BLIND $label (plant does not apply: $(head -n 1 "$dir/apply.log"))"; blinds=$(( blinds + 1 )); continue
    fi
    clean_rc "$tier" "$command"
    if (( rc != 0 )); then
        echo "BLIND $label (command red on the clean copy, exit $rc; see $work/clean-*)"; blinds=$(( blinds + 1 ))
        continue
    fi
    began=$(now)
    run_row "$dir" "$dir/tree" "$tier" "$command"
    took=$(secs "$began" "$(now)")
    case $(verdict_of "$rc") in
        OK) echo "FAIL $label ${took}s (green with the plant applied; log $dir/run.log)"; fails=$(( fails + 1 )) ;;
        BLIND) echo "BLIND $label ${took}s (could not judge, exit $rc: $(cat "$dir/run.line"))"
               blinds=$(( blinds + 1 )) ;;
        *) echo "OK $label ${took}s" ;;
    esac
done <<< "$rows"

(( count )) || { echo "BLIND coverage-plants (no row with a plant in $table)"; blinds=1; }
if (( fails + blinds )); then echo "coverage-plants: kept $work" >&2; else drop_tmp "$work"; fi
gate_exit "$blinds" "$fails"
