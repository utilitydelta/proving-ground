#!/usr/bin/env bash
# scripts/new-plant.sh and scripts/plants.sh over a throwaway tree: a plant made from a diff and one made by editing a
# copy both go OK; a plant the check misses is FAIL (exit 1), one that does not apply, one with no check and one that
# times out are BLIND (exit 2); work dirs go on all-OK and stay otherwise. plants.sh warns about a plant no coverage
# row names. scripts/coverage-plants.sh grades rows: OK, FAIL for a row that reads the live tree instead of TREE, BLIND
# for a row red on the clean copy, a stale plant, or no plant rows. RUN_DIR, PG_TMP and HEAVY_DIR are temp.
#
#   scripts/test_plants.sh
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
t=$(mktemp -d "${TMPDIR:-/tmp}/test-plants.XXXXXX")
export RUN_DIR=$t/run PG_TMP=$t/run/tmp HEAVY_DIR=$t/heavy
mkdir -p "$PG_TMP"
fail() { echo "FAIL: $*"; exit 1; }
cases=0
pass() { cases=$(( cases + 1 )); }

tree=$t/tree
mkdir -p "$tree/src"
echo good > "$tree/src/x.txt"
echo other > "$tree/notes.txt"
check='grep -q good "$TREE/src/x.txt"'
plants=$t/plants

# From a diff with tree-root paths: header written, paths kept, the plant caught.
cat > "$t/break.diff" <<'EOF'
diff --git a/src/x.txt b/src/x.txt
--- a/src/x.txt
+++ b/src/x.txt
@@ -1 +1 @@
-good
+bad
EOF
out=$("$here/new-plant.sh" "$tree" "$plants/break-x" "Turns good into bad." "$check" --from-diff "$t/break.diff") \
    || fail "new-plant --from-diff: $out"
[[ $out == "$plants/break-x.patch" ]] || fail "new-plant printed $out"
head -n 2 "$plants/break-x.patch" | diff - <(printf '# Turns good into bad.\n# check: %s\n' "$check") > /dev/null \
    || fail "header: $(head -n 3 "$plants/break-x.patch")"
grep -q '^--- a/src/x.txt$' "$plants/break-x.patch" && grep -q '^+++ b/src/x.txt$' "$plants/break-x.patch" \
    || fail "paths are not tree-root: $(cat "$plants/break-x.patch")"
pass

# Edit a copy, then --finish: a new file and an edit, tree-root paths, temp dir gone.
copy=$("$here/new-plant.sh" "$tree" "$plants/empty-x" "Empties x." "$check" --timeout 20 2> /dev/null) || fail "copy: $copy"
[[ -f $copy/src/x.txt ]] || fail "no copy at $copy"
: > "$copy/src/x.txt"
echo new > "$copy/src/added.txt"
"$here/new-plant.sh" --finish "$copy" > /dev/null || fail "--finish"
grep -q '^# timeout: 20$' "$plants/empty-x.patch" || fail "no timeout header"
grep -q '^+++ b/src/added.txt$' "$plants/empty-x.patch" || fail "new file path: $(cat "$plants/empty-x.patch")"
[[ ! -e $(dirname "$copy") ]] || fail "--finish left $(dirname "$copy")"
pass

# Refusals: an existing patch, an empty diff, an empty check.
"$here/new-plant.sh" "$tree" "$plants/break-x" "again" "$check" --from-diff "$t/break.diff" 2> /dev/null && fail "overwrite"
copy=$("$here/new-plant.sh" "$tree" "$plants/nothing" "Nothing." "$check" 2> /dev/null)
"$here/new-plant.sh" --finish "$copy" 2> /dev/null && fail "empty diff accepted"
"$here/new-plant.sh" "$tree" "$plants/no-check" "x" " " 2> /dev/null && fail "empty check accepted"
pass

out=$("$here/plants.sh" "$tree" "$plants" 2> "$t/stderr"); rc=$?
(( rc == 0 )) || fail "plants exit $rc: $out"
[[ $(grep -c '^OK ' <<< "$out") == 2 ]] || fail "expected 2 OK: $out"
grep -qE '^OK break-x [0-9]+\.[0-9]{2}s$' <<< "$out" || fail "time format: $out"
compgen -G "$PG_TMP/plants.*" > /dev/null && fail "all-OK run left $(ls "$PG_TMP")"
pass

# A plant the check misses: FAIL, exit 1, work dir kept and named.
mkdir "$t/missed"
sed -e 's#src/x.txt#notes.txt#g' -e 's/^-good/-other/' "$t/break.diff" > "$t/notes.diff"
"$here/new-plant.sh" "$tree" "$t/missed/notes" "Breaks a file nobody checks." "$check" --from-diff "$t/notes.diff" \
    > /dev/null || fail "new-plant notes"
out=$("$here/plants.sh" "$tree" "$t/missed" 2> "$t/stderr"); rc=$?
(( rc == 1 )) && grep -q '^FAIL notes' <<< "$out" || fail "missed plant: exit $rc: $out"
grep -q "plants: kept $PG_TMP/plants." "$t/stderr" || fail "FAIL run did not keep its dir: $(cat "$t/stderr")"
pass

# BLIND, exit 2: does not apply, no check line, times out. A FAIL beside them still exits 2.
mkdir "$t/blind"
{ echo "# Stale."; echo "# check: $check"; sed 's/^-good/-gone/' "$t/break.diff"; } > "$t/blind/stale.patch"
sed '/^# check:/d' "$plants/break-x.patch" > "$t/blind/nocheck.patch"
{ echo "# Slow."; echo "# check: sleep 5"; echo "# timeout: 1"; cat "$t/break.diff"; } > "$t/blind/slow.patch"
out=$("$here/plants.sh" "$tree" "$t/blind" 2> /dev/null); rc=$?
(( rc == 2 )) || fail "blind: exit $rc: $out"
for name in stale nocheck slow; do grep -q "^BLIND $name" <<< "$out" || fail "blind $name: $out"; done
cp "$t/missed/notes.patch" "$t/blind/"
"$here/plants.sh" "$tree" "$t/blind" > /dev/null 2>&1; rc=$?
(( rc == 2 )) || fail "BLIND beside FAIL: exit $rc, want 2"
pass

# No plants at all: BLIND.
mkdir "$t/none"
"$here/plants.sh" "$tree" "$t/none" > /dev/null 2>&1; rc=$?
(( rc == 2 )) || fail "no plants: exit $rc"
pass

# plants.sh warns about a plant no coverage row names: its # check: grades it, not a product row.
printf 'glob\tcommand\ttier\tbudget_s\tplant\nsrc/*\tgrep -q good "$TREE/src/x.txt"\ttargeted\t1\t%s\n' \
    "$plants/break-x.patch" > "$t/cov-one.tsv"
COVERAGE=$t/cov-one.tsv "$here/plants.sh" "$tree" "$plants" > /dev/null 2> "$t/stderr" || fail "warn run"
grep -q "warning: empty-x is not the plant of any coverage row" "$t/stderr" || fail "no warning: $(cat "$t/stderr")"
grep -q "warning: break-x" "$t/stderr" && fail "warned about a referenced plant: $(cat "$t/stderr")"
pass

# coverage-plants.sh: each row with a plant runs on a clean copy (green) and a planted one (red).
cov() { printf 'glob\tcommand\ttier\tbudget_s\tplant\n'; printf '%s\n' "$@"; }
row() { printf 'src/*\t%s\ttargeted\t1\t%s' "$1" "$2"; }
cov "$(row 'grep -q good "$TREE/src/x.txt"' "$plants/break-x.patch")" "$(row 'echo no plant' '')" > "$t/cov-ok.tsv"
out=$("$here/coverage-plants.sh" "$tree" "$t/cov-ok.tsv" 2> "$t/stderr"); rc=$?
(( rc == 0 )) || fail "coverage ok: exit $rc: $out $(cat "$t/stderr")"
grep -qE '^OK cov-ok.tsv:2 break-x [0-9]+\.[0-9]{2}s$' <<< "$out" || fail "coverage ok line: $out"
[[ $(wc -l <<< "$out") == 1 ]] || fail "a row without a plant got a verdict: $out"
compgen -G "$PG_TMP/coverage-plants.*" > /dev/null && fail "all-OK coverage run left $(ls "$PG_TMP")"
pass

# A row that reads the live tree instead of TREE stays green on the planted copy: FAIL.
cov "$(row "grep -q good $tree/src/x.txt" "$plants/break-x.patch")" > "$t/cov-live.tsv"
out=$("$here/coverage-plants.sh" "$tree" "$t/cov-live.tsv" 2> /dev/null); rc=$?
(( rc == 1 )) && grep -q '^FAIL cov-live.tsv:2 break-x' <<< "$out" || fail "live-tree row: exit $rc: $out"
pass

# BLIND: red on the clean copy, a plant that does not apply, a timeout; none graded at all.
cov "$(row 'grep -q bad "$TREE/src/x.txt"' "$plants/break-x.patch")" \
    "$(row 'grep -q good "$TREE/src/x.txt"' "$t/blind/stale.patch")" > "$t/cov-blind.tsv"
out=$("$here/coverage-plants.sh" "$tree" "$t/cov-blind.tsv" 2> /dev/null); rc=$?
(( rc == 2 )) || fail "coverage blind: exit $rc: $out"
grep -q '^BLIND cov-blind.tsv:2 break-x .*red on the clean copy' <<< "$out" || fail "clean red: $out"
grep -q '^BLIND cov-blind.tsv:3 stale .*does not apply' <<< "$out" || fail "stale: $out"
cov "$(row 'echo none' '')" > "$t/cov-none.tsv"
out=$("$here/coverage-plants.sh" "$tree" "$t/cov-none.tsv" 2> /dev/null); rc=$?
(( rc == 2 )) && grep -q '^BLIND coverage-plants' <<< "$out" || fail "no plant rows: exit $rc: $out"
pass

[[ $t == "${TMPDIR:-/tmp}"/test-plants.* ]] && rm -r -- "$t"
echo "plants: $cases cases OK"
