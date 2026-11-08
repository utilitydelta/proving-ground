#!/usr/bin/env bash
# The bot-tooling gate: this repo's own scripts, tests and lint, separate from the product gate (scripts/gate.sh).
# Runs on the working tree from the repo root. `finish` runs it when the session changed tooling
# (scripts/changed-tooling.sh <base> exits 0).
#
#   scripts/check-tooling.sh [quick|harness]
#
# quick: `bash -n` of every shell script, py_compile of every Python script, test_ledgers.py, test_hooks.sh,
# test_plants.sh (plants.sh and coverage-plants.sh), test_gate.sh. harness adds test_factory.sh (Linux only: bwrap and GNU date; elsewhere a SKIP line). One line per
# check, `OK|FAIL|BLIND <check> <secs>s` (lib/verdict.sh), with the failing output's tail. Exit 0 all OK, 2 any BLIND,
# else 1. A new script or test joins this list in the commit that adds it. Measured times live in INDEX.md (2026-11-09,
# template dev box: quick 22 s, harness 95 s, test_factory alone 73 s).
set -uo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=lib/verdict.sh
source scripts/lib/verdict.sh
tier=${1:-quick}
case $tier in quick|harness) ;; *) sed -n 6p "$0" >&2; exit 2 ;; esac
mkdir -p "${PG_TMP:=$PWD/.run/tmp}"
export PG_TMP
out=$(mktemp -d "$PG_TMP/tooling.XXXXXX")
export PYTHONPYCACHEPREFIX=$out/pyc PYTHONDONTWRITEBYTECODE=1
blind=0 failed=0

check() {
    local name=$1 began rc verdict
    shift
    began=$(now)
    "$@" > "$out/$name.log" 2>&1
    rc=$?
    verdict=$(verdict_of "$rc")
    echo "$verdict $name $(secs "$began" "$(now)")s"
    case $verdict in
        OK) return 0 ;;
        BLIND) blind=$(( blind + 1 )) ;;
        *) failed=$(( failed + 1 )) ;;
    esac
    tail -n 20 "$out/$name.log" | sed 's/^/    /'
}

shell_syntax() {
    local f rc=0
    for f in scripts/*.sh scripts/lib/*.sh scripts/hooks/*.sh scripts/hooks/pre-commit; do
        [[ -e $f ]] || continue
        bash -n "$f" || { echo "bash -n: $f"; rc=1; }
    done
    return $rc
}

python_syntax() {
    local f rc=0
    for f in scripts/*.py scripts/hooks/*.py; do
        [[ -e $f ]] || continue
        python3 -m py_compile "$f" || { echo "py_compile: $f"; rc=1; }
    done
    return $rc
}

check shell_syntax shell_syntax
check python_syntax python_syntax
check test_ledgers python3 scripts/test_ledgers.py
check test_hooks bash scripts/test_hooks.sh
check test_plants bash scripts/test_plants.sh
check test_gate bash scripts/test_gate.sh
if [[ $tier == harness ]]; then
    if [[ $(uname -s) == Linux ]]; then
        check test_factory bash scripts/test_factory.sh
    else
        echo "SKIP test_factory 0.00s (scripts/factory.sh is Linux only: bwrap, GNU date)"
    fi
fi
if (( blind + failed )); then echo "check-tooling: kept $out" >&2; else drop_tmp "$out"; fi
gate_exit "$blind" "$failed"
