#!/usr/bin/env bash
# The one pass/fail command over a tree. A stub until the adopting project writes its own.
#
#   scripts/gate.sh <tree> [quick|harness|full]          (GATE_CMD in project.env; default tier quick)
#
# Contract for the real gate:
# - Exit 0 green, nonzero red. Nothing else counts as a verdict.
# - Tiers. quick: the targeted checks an agent runs after every change; it must fit the quick budget INDEX.md records
#   for this machine, and a run past it is a finding about the gate. harness: every harness compiles and every
#   planted-fault patch still applies and turns its check red (a patch that no longer applies is a harness gone
#   blind). full: every tier, sweeps and proofs included.
# - Stages run no-fail-fast: one red stage does not hide the next one's verdict.
# - Each stage prints one line: OK, FAIL or BLIND, then its wall-clock in seconds. BLIND means the stage did not build
#   or could not run. BLIND is never reported as OK, and any BLIND makes the gate exit nonzero: a check that cannot
#   run proves nothing.
# - Every stage runs under its own timeout (scripts/run.sh -t), its own build-output dir and its own log path, so two
#   gates or two stages never share either.
# - The gate runs from a `git archive` copy of <tree> in a fresh mktemp -d, never the live worktree: an agent editing
#   the tree mid-run cannot change the verdict, and uncommitted files cannot make it green.
#
# This stub delegates to examples/kv-python/gate.sh when that exists, so the template is green out of the box. The
# example gates its own toy product (examples/kv-python/product), so <tree> is ignored until the real gate exists.
# Otherwise it says the gate needs writing and exits 2.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
(( $# >= 1 )) || { sed -n 4p "$0" >&2; exit 2; }
case ${2:-quick} in quick|harness|full) ;; *) echo "gate: tier must be quick, harness or full" >&2; exit 2 ;; esac

example=$root/examples/kv-python/gate.sh
if [[ -x $example || -f $example ]]; then
    echo "gate: stub, delegating to the kv-python example over its own product tree; $1 is not gated" >&2
    exec bash "$example" "$root/examples/kv-python/product" "${2:-quick}"
fi
echo "gate: scripts/gate.sh is a stub. Write the project's gate to the contract in its header." >&2
exit 2
