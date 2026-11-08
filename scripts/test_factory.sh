#!/usr/bin/env bash
# scripts/factory.sh against a stub claude: each stop path, the job queue, heavy-job concurrency, job timeouts, resume
# numbering, the session-limit sleep decision, the read-only jail, the no-bwrap refusal, and jobs sharing run.sh heavy
# slots: a busy slot sends the job back to pending with a backoff, a heavy run inside a job shares the job's slot.
# Spends no quota. Heavy slots live in a temp RUN_DIR, never the machine's .run/.
#
#   scripts/test_factory.sh
#
# Exit 1 on the first failed case. Takes about two minutes, most of it the stub sleeping.
set -uo pipefail
# No -e: each case inspects exit codes and greps that are expected to fail.

here=$(cd "$(dirname "$0")" && pwd)
root=$(mktemp -d)
export RUN_DIR=$root/rundir
# Run from a heavy gate stage, the caller's slot must not leak into the cases that count slots.
unset RUN_HEAVY_SLOT
fail() { echo "FAIL: $*"; exit 1; }

# The stub reads its behaviour from $STUB_MODE and the session dir from the prompt.
cat > "$root/claude" <<'EOF'
#!/usr/bin/env bash
session=$(grep -oE 'Session: [^ ]+' <<< "${*: -1}" | cut -d' ' -f2)
state=$session/session-state.md
n=$(cat "$session/n" 2>/dev/null || echo 0); n=$(( n + 1 )); echo $n > "$session/n"
case $STUB_MODE in
    done) echo "step $n" >> "$state"; (( n >= 2 )) && echo "Status: done" >> "$state" ;;
    stuck) : ;;
    pause) echo "${*: -1}" >> "$session/prompts"
           [[ $(grep -c '^## Done' "$state") == 0 ]] && printf 'Status: building\n\n## Done\n' >> "$state"
           if grep -q "Pause iteration" <<< "${*: -1}"; then echo "- pause-$n" >> "$state"
           else mkdir -p "$session/units"; printf '## Contract\n## Decisions\n## Commits\n' > "$session/units/u$n.md"
                echo "- u$n lead abc" >> "$state"; fi
           (( n >= 8 )) && sed -i 's/^Status: building/Status: done/' "$state" ;;
    job) if (( n == 1 )); then echo "first" >> "$state"; echo "sleep 3; echo ran > $session/jobs/ran" > "$session/jobs/pending/a.sh"
         elif grep -q ran "$session/jobs/ran" 2>/dev/null; then echo "Status: done" >> "$state"; fi ;;
    record) printf 'Status: building\n\n## Done\n- u1 lead abc\n' > "$state"
            mkdir -p "$session/units"; printf '## Contract\n## Commits\n' > "$session/units/u1.md" ;;
    twojobs) if (( n == 1 )); then echo "first" >> "$state"
                 echo "sleep 2" > "$session/jobs/pending/a.sh"; echo "echo b" > "$session/jobs/pending/b.sh"
             elif (( n == 2 )); then echo "second" >> "$state"; sleep 6
             elif [[ -e $session/jobs/done/b.exit ]]; then echo "Status: done" >> "$state"; fi ;;
    heavy) if (( n == 1 )); then echo "first" >> "$state"
               for j in a b c; do echo "sleep 3" > "$session/jobs/pending/$j.sh"; done
           elif [[ -e $session/jobs/done/a.exit && -e $session/jobs/done/b.exit && -e $session/jobs/done/c.exit ]]; then
               echo "Status: done" >> "$state"; fi ;;
    timeout) if (( n == 1 )); then echo "first" >> "$state"; printf '#!/usr/bin/env bash\n# timeout: 2\nsleep 30\n' > "$session/jobs/pending/slow.sh"
             elif [[ -e $session/jobs/done/slow.exit ]]; then echo "Status: done" >> "$state"; fi ;;
    weekly) echo '{"type":"assistant","text":"You'"'"'ve hit your weekly limit · resets Mon 12:00am"}' ;;
    session) echo '{"type":"assistant","text":"You'"'"'ve hit your 5-hour limit · resets 11:59pm"}' ;;
    stopjob) echo "sleep 60" > "$session/jobs/pending/a.sh"; echo "step $n" >> "$state"; sleep 3; touch "$session/STOP" ;;
    busy) if (( n == 1 )); then echo "first" >> "$state"; echo "echo ran" > "$session/jobs/pending/a.sh"
          elif [[ -e $session/jobs/done/a.exit ]]; then echo "Status: done" >> "$state"; fi ;;
    nested) if (( n == 1 )); then echo "first" >> "$state"
                echo "$RUN_SH -H -t 5 -- echo inner-ok" > "$session/jobs/pending/a.sh"
            elif [[ -e $session/jobs/done/a.exit ]]; then echo "Status: done" >> "$state"; fi ;;
    jail) echo hacked > "$JAIL_TARGET/f" 2>/dev/null; echo hacked > "$JAIL_EXTRA/f" 2>/dev/null; echo "Status: done" >> "$state" ;;
esac
echo '{"type":"result","total_cost_usd":0.01,"num_turns":1}'
EOF
chmod +x "$root/claude"

# HUMAN_REPO and one FACTORY_READ_ONLY dir, both of which the jail must hold read-only.
ro=$root/human; mkdir -p "$ro"; echo orig > "$ro/f"
extra=$root/extra; mkdir -p "$extra"; echo orig > "$extra/f"
run() {
    local mode=$1; shift
    local s=$root/$mode; mkdir -p "$s"; : > "$s/session-state.md"
    STUB_MODE=$mode CLAUDE_BIN=$root/claude HUMAN_REPO=$ro FACTORY_READ_ONLY=$extra JAIL_TARGET=$ro JAIL_EXTRA=$extra \
        RUN_SH=$here/run.sh FACTORY_BUSY_BACKOFF=2 \
        timeout 120 "$here/factory.sh" "$s" "$@" > "$s/runner.out" 2>&1
    echo $? > "$s/exit"
}

run done --until "+1 hour"
grep -q "stop: Status: done" "$root/done/progress.md" || fail "done: $(cat "$root/done/runner.out")"
[[ $(cat "$root/done/n") == 2 ]] || fail "done: expected 2 iterations, got $(cat "$root/done/n")"

run stuck --until "+1 hour"
grep -q "3 iterations left session-state.md unchanged" "$root/stuck/progress.md" || fail "stuck: $(cat "$root/stuck/runner.out")"

run job --until "+1 hour"
grep -q "job a exit 0" "$root/job/progress.md" || fail "job: $(cat "$root/job/runner.out")"
grep -q "stop: Status: done" "$root/job/progress.md" || fail "job: never saw the job result"
# Iteration 2 runs while the job sleeps, finds nothing to do, and the runner waits for the job instead of iterating.
order=$(grep -oE "iteration 2$|job a exit|waiting on job: a" "$root/job/progress.md" | tr '\n' ',')
[[ $order == "iteration 2,waiting on job: a,job a exit," ]] || fail "job: expected iteration 2 during the job, then a wait: $order"

run pause --until "+1 hour"
grep -q "stop: Status: done" "$root/pause/progress.md" || fail "pause: $(cat "$root/pause/runner.out")"
[[ $(grep -n "Pause iteration" "$root/pause/prompts" | cut -d: -f1 | tr '\n' ' ') == "4 8 " ]] \
    || fail "pause: expected pauses at iterations 4 and 8, got: $(grep -n "Pause iteration" "$root/pause/prompts" | cut -d: -f1)"

run record --until "+1 hour"
grep -q "stop: units done with no complete record in units/: u1" "$root/record/progress.md" \
    || fail "record: $(cat "$root/record/runner.out")"

# Job a ends while iteration 2 still runs; b must start then, not after iteration 2 exits.
run twojobs --until "+1 hour"
grep -q "stop: Status: done" "$root/twojobs/progress.md" || fail "twojobs: $(cat "$root/twojobs/runner.out")"
order=$(grep -oE "iteration [0-9]+( exit)?|job a exit|job b start" "$root/twojobs/progress.md" | tr '\n' ',')
[[ $order == *"iteration 2,job a exit,job b start,"*"iteration 2 exit"* ]] \
    || fail "twojobs: expected b to follow a without an iteration between: $order"

# HEAVY_JOBS=1: never two jobs running at once. HEAVY_JOBS=2: two run together, the third waits for a slot.
max_running() {
    awk '/runner: job [a-z]+ start/{r++; if (r > m) m = r} /runner: job [a-z]+ exit/{r--} END{print m + 0}' "$1"
}
HEAVY_JOBS=1 run heavy --until "+1 hour"
grep -q "stop: Status: done" "$root/heavy/progress.md" || fail "heavy 1: $(cat "$root/heavy/runner.out")"
[[ $(max_running "$root/heavy/progress.md") == 1 ]] || fail "heavy 1: $(max_running "$root/heavy/progress.md") jobs at once"
mv "$root/heavy" "$root/heavy1"
HEAVY_JOBS=2 run heavy --until "+1 hour"
grep -q "stop: Status: done" "$root/heavy/progress.md" || fail "heavy 2: $(cat "$root/heavy/runner.out")"
[[ $(max_running "$root/heavy/progress.md") == 2 ]] || fail "heavy 2: $(max_running "$root/heavy/progress.md") jobs at once"

# A job's own `# timeout:` header kills it, and the kill is written into its .out.
run timeout --until "+1 hour"
grep -q "stop: Status: done" "$root/timeout/progress.md" || fail "timeout: $(cat "$root/timeout/runner.out")"
[[ $(cat "$root/timeout/jobs/done/slow.exit") == 124 ]] || fail "timeout: exit $(cat "$root/timeout/jobs/done/slow.exit")"
grep -q "killed by its 2 s timeout" "$root/timeout/jobs/done/slow.out" || fail "timeout: .out does not say so"
grep -q "job slow exit 124 after [0-9] s" "$root/timeout/progress.md" || fail "timeout: ran past its timeout"

run weekly --until "+1 hour"
grep -q "stop: weekly limit" "$root/weekly/progress.md" || fail "weekly: $(cat "$root/weekly/runner.out")"

# 11:59pm is past a deadline two minutes out (unless the test runs at 23:57), so the runner stops rather than sleeps.
run session --until "+2 minutes"
grep -q "stop: session limit resets past the deadline" "$root/session/progress.md" || fail "session: $(cat "$root/session/runner.out")"

# STOP while a job runs: the runner takes the job down with it and leaves it in pending for the next run.
run stopjob --until "+1 hour"
grep -q "stop: STOP file" "$root/stopjob/progress.md" || fail "stopjob: $(cat "$root/stopjob/runner.out")"
[[ -e $root/stopjob/jobs/pending/a.sh && ! -e $root/stopjob/jobs/done/a.exit ]] || fail "stopjob: job not back in pending"
! pgrep -f "$root/stopjob/jobs/running/" > /dev/null || fail "stopjob: job outlived the runner"

# Every heavy slot held by another process: the job goes back to pending, retries after the backoff without waking an
# iteration per retry, and runs once the slot frees.
mkdir -p "$root/rundir/heavy/slot-1"; sleep 7 & holder=$!; echo $holder > "$root/rundir/heavy/slot-1/pid"
HEAVY_JOBS=1 run busy --until "+1 hour"
wait $holder 2> /dev/null
grep -q "stop: Status: done" "$root/busy/progress.md" || fail "busy: $(cat "$root/busy/runner.out")"
grep -q "job a back in pending: every heavy slot is busy" "$root/busy/progress.md" || fail "busy: never refused a slot"
[[ $(cat "$root/busy/jobs/done/a.exit") == 0 ]] && grep -q '^ran$' "$root/busy/jobs/done/a.out" || fail "busy: job never ran"
retries=$(grep -c "back in pending" "$root/busy/progress.md")
(( retries <= 5 )) || fail "busy: $retries retries in about 7 s with a 2 s backoff"
(( $(cat "$root/busy/n") <= 3 )) || fail "busy: $(cat "$root/busy/n") iterations; backoff retries woke iterations"

# A heavy run inside a job shares the job's slot instead of exiting 75 against it.
HEAVY_JOBS=1 run nested --until "+1 hour"
grep -q "stop: Status: done" "$root/nested/progress.md" || fail "nested: $(cat "$root/nested/runner.out")"
[[ $(cat "$root/nested/jobs/done/a.exit") == 0 ]] && grep -q inner-ok "$root/nested/jobs/done/a.out" \
    || fail "nested: $(cat "$root/nested/jobs/done/a.out")"

run jail --until "+1 hour"
grep -q "stop: Status: done" "$root/jail/progress.md" || fail "jail: the stub never ran: $(cat "$root/jail/runner.out")"
[[ $(cat "$ro/f") == orig ]] || fail "jail: the stub wrote through the HUMAN_REPO bind"
[[ $(cat "$extra/f") == orig ]] || fail "jail: the stub wrote through the FACTORY_READ_ONLY bind"

# No bwrap: refuse with a message naming the escape hatch. FACTORY_NO_JAIL=1 runs anyway.
s=$root/nobwrap; mkdir -p "$s"; : > "$s/session-state.md"
STUB_MODE=done CLAUDE_BIN=$root/claude HUMAN_REPO=$ro BWRAP_BIN=$root/no-such-bwrap timeout 60 "$here/factory.sh" "$s" \
    --until "+1 hour" > "$s/runner.out" 2>&1
[[ $? == 2 ]] && grep -q "FACTORY_NO_JAIL=1" "$s/runner.out" && [[ ! -e $s/n ]] || fail "nobwrap: $(cat "$s/runner.out")"
STUB_MODE=done CLAUDE_BIN=$root/claude HUMAN_REPO=$ro BWRAP_BIN=$root/no-such-bwrap FACTORY_NO_JAIL=1 timeout 60 \
    "$here/factory.sh" "$s" --until "+1 hour" > "$s/runner.out" 2>&1
grep -q "stop: Status: done" "$s/progress.md" || fail "nojail: $(cat "$s/runner.out")"

# A missing HUMAN_REPO is a refusal, not an unguarded run.
s=$root/nohuman; mkdir -p "$s"; : > "$s/session-state.md"
STUB_MODE=done CLAUDE_BIN=$root/claude HUMAN_REPO=$root/absent timeout 60 "$here/factory.sh" "$s" --until "+1 hour" \
    > "$s/runner.out" 2>&1
[[ $? == 2 && ! -e $s/n ]] || fail "nohuman: $(cat "$s/runner.out")"

# A resumed session numbers on from its last transcript; the old gzip is untouched.
s=$root/resume; mkdir -p "$s/iterations"; : > "$s/session-state.md"; echo old | gzip > "$s/iterations/0003.jsonl.gz"
STUB_MODE=done CLAUDE_BIN=$root/claude HUMAN_REPO=$ro timeout 120 "$here/factory.sh" "$s" --until "+1 hour" \
    > "$s/runner.out" 2>&1
grep -q "iteration 4$" "$s/progress.md" || fail "resume: expected iteration 4 first: $(cat "$s/progress.md")"
[[ $(zcat "$s/iterations/0003.jsonl.gz") == old && -e $s/iterations/0005.jsonl.gz ]] \
    || fail "resume: transcripts $(ls "$s/iterations" | tr '\n' ' ')"

run done --until "-1 minute"
[[ $(cat "$root/done/exit") == 2 ]] || fail "past deadline: expected refusal"

[[ $root == "${TMPDIR:-/tmp}"/tmp.* ]] && rm -r -- "$root"
echo "factory: 19 cases OK"
