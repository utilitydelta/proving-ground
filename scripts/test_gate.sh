#!/usr/bin/env bash
# scripts/gate.sh in a throwaway clone whose ADOPT block holds fixture stages: a declared -t stays the cap at the full
# tier, a FAIL prints its run.sh verdict line once, and stages run the committed snapshot's scripts/run.sh, so an
# uncommitted tooling edit cannot change a verdict. RUN_DIR, PG_TMP and HEAVY_DIR are temp.
#
#   scripts/test_gate.sh
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
src=$(cd "$here/.." && pwd)
t=$(mktemp -d "${TMPDIR:-/tmp}/test-gate.XXXXXX")
export RUN_DIR=$t/run PG_TMP=$t/run/tmp HEAVY_DIR=$t/heavy
unset RUN_HEAVY_SLOT TREE GATE_TIER
fail() { echo "FAIL: $*"; exit 1; }
cases=0
pass() { cases=$(( cases + 1 )); }

clone=$t/clone
mkdir -p "$clone"
(cd "$src" && git ls-files -co --exclude-standard -z \
    | while IFS= read -r -d '' f; do [[ -e $f ]] && printf '%s\0' "$f"; done | tar --null -T - -cf -) \
    | tar -C "$clone" -xf -
python3 - "$clone/scripts/gate.sh" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path).read()
stages = ("stage slow quick -t 2 -- sleep 6\n"
          "stage bad quick -- false\n"
          "stage good quick -- true\n")
new, n = re.subn(r"(# ADOPT: product stages below\..*?\n)(?:(?!# ADOPT).*\n)*?(# ADOPT: product stages above\.)",
                 lambda m: m.group(1) + stages + m.group(2), text, flags=re.S)
assert n == 1, "no ADOPT block"
open(path, "w").write(new)
PY
grep -q '^stage slow quick -t 2 -- sleep 6$' "$clone/scripts/gate.sh" || fail "fixture block not written"
git -C "$clone" init -q && git -C "$clone" add -A \
    && git -C "$clone" -c user.name=t -c user.email=t@t commit -qm fixture || fail "fixture commit"
mkdir -p "$t/tree"; echo x > "$t/tree/f"

began=$SECONDS
out=$("$clone/scripts/gate.sh" "$t/tree" full 2> "$t/stderr"); rc=$?
took=$(( SECONDS - began ))
(( rc == 2 )) || fail "full: exit $rc, want 2 (slow is BLIND): $out"
grep -qE '^BLIND slow [0-9.]+s$' <<< "$out" || fail "slow not BLIND: $out"
(( took < 6 )) || fail "full tier raised slow's -t 2: the gate took $took s"
pass

grep -qE '^FAIL bad ' <<< "$out" && grep -qE '^OK good ' <<< "$out" || fail "bad/good: $out"
[[ $(grep -c 'run: exit 1 ' <<< "$out") == 1 ]] || fail "run: line for bad printed $(grep -c 'run: exit 1 ' <<< "$out") times: $out"
pass

# An uncommitted edit to run.sh that turns every run green must not reach the verdicts.
sed -i '2i exit 0' "$clone/scripts/run.sh"
out=$("$clone/scripts/gate.sh" "$t/tree" quick 2> /dev/null); rc=$?
grep -qE '^FAIL bad ' <<< "$out" || fail "live run.sh edit changed the verdict: $out"
pass

[[ $t == "${TMPDIR:-/tmp}"/test-gate.* ]] && rm -r -- "$t"
echo "gate: $cases cases OK"
