#!/usr/bin/env bash
# The bot-tooling checks: this repo's own scripts, tests and lint. The gate's bot-tooling stage runs it on a
# `git archive HEAD` copy; run it by hand from the repo root to check a working tree.
#
#   scripts/check-tooling.sh [quick|harness|full]
#
# quick: test_ledgers.py, test_hooks.sh, lint.py. harness and full add test_factory.sh (about a minute), `bash -n` of
# every shell script and py_compile of every Python script under scripts/. Every check runs; one line each,
# OK|FAIL <check>, with the failing output's tail. Exit 0 only if all pass. A new script or test joins this list in
# the commit that adds it.
set -uo pipefail

cd "$(dirname "$0")/.."
tier=${1:-quick}
case $tier in quick|harness|full) ;; *) sed -n 4p "$0" >&2; exit 2 ;; esac
out=$(mktemp -d "${PG_TMP:-${TMPDIR:-/tmp}}/tooling.XXXXXX")
export PYTHONPYCACHEPREFIX=$out/pyc
bad=0

check() {
    local name=$1; shift
    if "$@" > "$out/$name.log" 2>&1; then
        echo "OK $name"
    else
        echo "FAIL $name (exit $?)"
        tail -n 20 "$out/$name.log" | sed 's/^/    /'
        bad=1
    fi
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

check test_ledgers python3 scripts/test_ledgers.py
check test_hooks bash scripts/test_hooks.sh
check lint python3 scripts/lint.py
if [[ $tier != quick ]]; then
    check test_factory bash scripts/test_factory.sh
    check shell_syntax shell_syntax
    check python_syntax python_syntax
fi
exit $bad
