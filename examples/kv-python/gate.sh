#!/usr/bin/env bash
# One pass/fail over a product tree: gate.sh [tree] [quick|full]
# Every stage runs under `timeout` and prints its wall-clock. Exit nonzero on any red.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tree="$(cd "${1:-$here/product}" && pwd)" || { echo "gate: no tree at ${1:-}"; exit 2; }
tier="${2:-quick}"
case "$tier" in quick|full) ;; *) echo "gate: tier must be quick or full, got $tier"; exit 2 ;; esac

harness="$here/harness"
tapes="$(mktemp -d "${TMPDIR:-/tmp}/kv-gate-tapes.XXXXXX")"
export KV_TREE="$tree"
unset KV_PLANT
red=0

now() { python3 -c "import time; print(time.time())"; }

stage() {
  local name="$1" budget="$2"
  shift 2
  local began ended rc
  began="$(now)"
  (cd "$harness" && timeout "$budget" "$@") >"$tapes/$name.out" 2>&1
  rc=$?
  ended="$(now)"
  local verdict="green"
  [ "$rc" -eq 0 ] || { verdict="RED (exit $rc)"; red=1; }
  [ "$rc" -eq 124 ] && verdict="RED (timeout ${budget}s)"
  printf 'gate: %-12s %-22s %6.2fs\n' "$name" "$verdict" "$(awk "BEGIN { print $ended - $began }")"
  [ "$rc" -eq 0 ] || tail -n 20 "$tapes/$name.out" | sed 's/^/      /'
}

echo "gate: tree $tree, tier $tier"
stage unit 60 python3 -m unittest discover -s . -p 'test_*.py'
stage sim-quick 60 python3 sim.py --seeds 200 --start 0 --timeout 50 --tape-dir "$tapes"
stage plant-check 120 python3 plant_check.py --seeds 200
if [ "$tier" = full ]; then
  stage sim-sweep 300 python3 sim.py --seeds 2000 --start 200 --timeout 280 --tape-dir "$tapes"
fi

if [ "$red" -ne 0 ]; then
  echo "gate: RED; stage output and any tapes in $tapes"
  exit 1
fi
rm -f -- "${tapes:?}"/*.out
rmdir -- "$tapes"
echo "gate: GREEN"
