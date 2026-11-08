# shellcheck shell=bash
# Sourced, never run. The one exit-status-to-verdict mapping for every gate (scripts/gate.sh, scripts/plants.sh, an
# adopter's or the example's gate) and the stage clock.
#
#   verdict_of <rc> [usage-is-blind]   prints OK, FAIL or BLIND
#   now                                 seconds since the epoch, two decimals where the shell allows (EPOCHREALTIME)
#   secs <start> <end>                  end - start, two decimals
#   gate_exit <blind-count> <fail-count>   exits 0 all OK, 2 any BLIND, else 1
#   drop_tmp <dir>                      removes a temp dir only when it resolves inside PG_TMP
#
# OK: 0. BLIND: the check could not judge: 75 heavy slot busy (scripts/run.sh), 124 timeout, 126 or 127 cannot run,
# 137 killed (timeout -k or the MEMORY_MAX cap), and 2 only when the caller says its stage uses 2 for a usage or build
# failure (pass usage-is-blind=1). FAIL: any other nonzero, the check itself saying no. A timeout is BLIND, not FAIL:
# it says nothing about the code, only that the budget was wrong or the slot was taken.

verdict_of() {
    local rc=$1 usage_blind=${2:-0}
    case $rc in
        0) echo OK ;;
        75|124|126|127|137) echo BLIND ;;
        2) if (( usage_blind )); then echo BLIND; else echo FAIL; fi ;;
        *) echo FAIL ;;
    esac
}

now() {
    if [[ -n ${EPOCHREALTIME:-} ]]; then
        echo "${EPOCHREALTIME/,/.}"
    else
        date +%s.00
    fi
}

secs() { awk -v a="$1" -v b="$2" 'BEGIN { printf "%.2f", b - a }'; }

gate_exit() {
    (( $1 )) && exit 2
    (( $2 )) && exit 1
    exit 0
}

# drop_tmp <dir>: remove a temp dir this script made with `mktemp -d "$PG_TMP/..."`. Refuses, with a line on stderr,
# anything whose resolved path is not strictly inside PG_TMP: a gate must never delete what it did not create.
drop_tmp() {
    local dir base
    dir=$(cd "$1" 2> /dev/null && pwd -P) || return 0
    base=$(cd "${PG_TMP:?}" && pwd -P) || return 1
    if [[ $dir != "$base"/?* ]]; then
        echo "drop_tmp: refused $1 ($dir): not inside PG_TMP $base" >&2
        return 1
    fi
    rm -rf -- "$dir"
}
