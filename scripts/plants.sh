#!/usr/bin/env bash
# Proves a harness can fail: every planted bug must turn its check red, in any language.
#
#   scripts/plants.sh <tree> <plants-dir>
#
# A plant is <plants-dir>/<name>.patch: a unified diff whose paths are relative to the tree root (a/src/x.c,
# b/src/x.c, applied with -p1), with header comment lines before the diff:
#
#   # One line on the bug this plants.
#   # check: <shell command; red (nonzero) means the bug was caught>
#   # timeout: <seconds, optional; scripts/run.sh -t>
#
# For each plant: copy <tree> (without .git) into a fresh dir, `git apply` the patch there, and run the check from
# this repo's root with TREE=<patched copy> and PLANT_OUT=<an empty dir for tapes and output>, under scripts/run.sh.
# Each distinct check also runs once on an unpatched copy and must be green there: a check that is red on the clean
# tree (a harness crash, a bad argument) would otherwise count every plant as caught.
#
# One line per plant:
#   OK <plant> <secs>s   the check went red on the patched copy
#   FAIL <plant>         the check stayed green: the harness is blind to this bug
#   BLIND <plant>        no check line, the patch does not apply, the check is red on the clean tree, or the check
#                        could not judge (lib/verdict.sh: run.sh 75, 124, 137; shell 126, 127)
# Exit as every gate does (lib/verdict.sh gate_exit): 0 every plant OK, 2 any BLIND (no plants at all, or a usage
# error, counts), else 1. Work dirs live under one mktemp -d in PG_TMP, removed when every plant is OK and kept, with
# the path on stderr, otherwise, so a tape or log can be read after a red run.
set -uo pipefail

(( $# == 2 )) || { sed -n 4p "$0" >&2; exit 2; }
root=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck source=lib/verdict.sh
source "$root/scripts/lib/verdict.sh"
tree=$(cd "$1" && pwd) || { echo "plants: no tree at $1" >&2; exit 2; }
plants_dir=$(cd "$2" && pwd) || { echo "plants: no plants dir at $2" >&2; exit 2; }
mkdir -p "${PG_TMP:=$root/.run/tmp}"
export PG_TMP
work=$(mktemp -d "$PG_TMP/plants.XXXXXX")
echo "plants: tree $tree, work dir $work" >&2

copy_tree() {
    mkdir -p "$1" && tar -C "$tree" --exclude=.git -cf - . | tar -C "$1" -xf -
}

header() {
    # Prints the value of "# <key>: value" from the comment lines before the diff starts.
    awk -v key="$2" '
        /^(diff |--- |Index: )/ { exit }
        index($0, "# " key ": ") == 1 { print substr($0, length(key) + 5); exit }
    ' "$1"
}

# run_check <dir> <tree copy> <check> <timeout>: sets rc to the check's exit status. No subshell for the caller, so
# the baseline cache below survives.
run_check() {
    local dir=$1 copy=$2 check=$3 limit=$4
    mkdir -p "$dir/out"
    (
        cd "$root" || exit 2
        TREE=$copy PLANT_OUT=$dir/out "$root/scripts/run.sh" ${limit:+-t "$limit"} -l "$dir/check.log" \
            -- bash -c "$check" 2> "$dir/run.line"
    )
    rc=$?
}

baseline_checks=() baseline_codes=()
baseline() {
    # Sets rc to <check>'s exit status on an unpatched copy, run once per distinct check and timeout.
    local check=$1 limit=$2 i
    for i in "${!baseline_checks[@]}"; do
        [[ ${baseline_checks[$i]} == "$check|$limit" ]] && { rc=${baseline_codes[$i]}; return; }
    done
    local dir=$work/baseline-${#baseline_checks[@]}
    copy_tree "$dir/tree"
    run_check "$dir" "$dir/tree" "$check" "$limit"
    baseline_checks+=("$check|$limit") baseline_codes+=("$rc")
}

fails=0 blinds=0 count=0
for patch in "$plants_dir"/*.patch; do
    [[ -e $patch ]] || break
    count=$(( count + 1 ))
    name=$(basename "$patch" .patch)
    dir=$work/$name
    check=$(header "$patch" check)
    limit=$(header "$patch" timeout)
    if [[ -z $check ]]; then
        echo "BLIND $name (no '# check:' line)"; blinds=$(( blinds + 1 )); continue
    fi
    copy_tree "$dir/tree"
    if ! (cd "$dir/tree" && GIT_CEILING_DIRECTORIES=$dir git apply -p1 "$patch") 2> "$dir/apply.log"; then
        echo "BLIND $name (patch does not apply: $(head -n 1 "$dir/apply.log"))"; blinds=$(( blinds + 1 )); continue
    fi
    baseline "$check" "$limit"
    if (( rc != 0 )); then
        echo "BLIND $name (check exits $rc on the clean tree; see $work/baseline-*)"; blinds=$(( blinds + 1 ))
        continue
    fi
    began=$(now)
    run_check "$dir" "$dir/tree" "$check" "$limit"
    code=$rc
    took=$(secs "$began" "$(now)")
    # Inverted: the check going red is the plant's OK, but a check that could not judge is BLIND either way.
    case $(verdict_of "$code") in
        OK) echo "FAIL $name ${took}s (check green on the planted bug; log $dir/check.log)"; fails=$(( fails + 1 )) ;;
        BLIND) echo "BLIND $name ${took}s (check could not finish, exit $code: $(cat "$dir/run.line"))"
               blinds=$(( blinds + 1 )) ;;
        *) echo "OK $name ${took}s" ;;
    esac
done

(( count )) || { echo "BLIND (no plants in $plants_dir)"; blinds=1; }
if (( fails + blinds )); then echo "plants: kept $work" >&2; else drop_tmp "$work"; fi
gate_exit "$blinds" "$fails"
