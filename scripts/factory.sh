#!/usr/bin/env bash
# Unattended runner for a Factory session: a fresh `claude -p` orchestrator per iteration, state on disk.
#
#   scripts/factory.sh <session-dir> --until "<date -d expression>" [--model M] [--max-iterations N] [--gap MINUTES]
#
# Each iteration loads the `factory` skill against <session-dir>, does one bounded step and exits. Queued jobs
# (<session-dir>/jobs/pending/*.sh) run in the background with no Claude process waiting on them, at most HEAVY_JOBS
# at once, so a long test or simulation never holds a context past the prompt-cache TTL. Each job runs under a hard
# timeout: `# timeout: <seconds>` in its first 10 lines, else 3600. A timeout is written into the job's .out.
# When an iteration changes nothing while a job runs, the runner waits for a job instead of iterating.
#
# Every Claude process and job runs in a bwrap jail with HUMAN_REPO and FACTORY_READ_ONLY (project.env) read-only.
# No bwrap: the runner refuses to start unless FACTORY_NO_JAIL=1.
#
# Stops on: <session-dir>/STOP, the deadline, `Status: done|blocked` in session-state.md, a weekly limit, 3 iterations
# in a row that leave session-state.md unchanged, or --max-iterations. Sleeps through a session limit when its reset
# falls before the deadline. After every 3 units built the next iteration is a pause: the prompt says so and the skill
# builds nothing new until a `- pause-...` line lands in `## Done`. A built unit in `## Done` whose units/<id>.md lacks
# `## Contract`, `## Decisions` or `## Commits` stops the runner. Raw transcripts are gzipped in iterations/.
#
# Environment: CLAUDE_BIN (claude binary), BWRAP_BIN (bwrap binary), FACTORY_NO_JAIL=1 (run unjailed),
# plus any project.env key. Every iteration and every job runs under MEMORY_MAX (see lib/env.sh set_mem_cap); a job's
# real exit status, an OOM kill included, lands in jobs/done/<name>.exit.
set -uo pipefail
# No -e: the loop inspects exit codes of claude and jobs and must survive every one of them.

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh" || exit 2

session=
until_expr=
model=${FACTORY_MODEL:-opus}
max_iterations=1000
gap=0
pause_every=3
default_job_timeout=3600
while (( $# )); do
    case $1 in
        --until) until_expr=$2; shift 2 ;;
        --model) model=$2; shift 2 ;;
        --max-iterations) max_iterations=$2; shift 2 ;;
        --gap) gap=$2; shift 2 ;;
        -*) echo "unknown flag $1" >&2; exit 2 ;;
        *) session=$1; shift ;;
    esac
done
[[ -n $session && -n $until_expr ]] || { sed -n 4p "$0" >&2; exit 2; }
session=$(cd "$session" && pwd) || exit 2
deadline=$(date -d "$until_expr" +%s) || exit 2
(( deadline > $(date +%s) )) || { echo "deadline $until_expr is in the past" >&2; exit 2; }
claude_bin=${CLAUDE_BIN:-claude}
(( HEAVY_JOBS >= 1 )) || { echo "HEAVY_JOBS must be at least 1" >&2; exit 2; }
# Started from inside a Claude Code session, the parent's session variables would leak into every iteration.
for var in "${!CLAUDE_CODE_@}"; do unset "$var"; done

[[ -d $HUMAN_REPO ]] || { echo "HUMAN_REPO $HUMAN_REPO is not a directory; set it in project.env" >&2; exit 2; }
read_only=("$HUMAN_REPO")
read -ra extra <<< "${FACTORY_READ_ONLY:-}"
for dir in "${extra[@]}"; do
    [[ $dir == /* ]] || dir=$ROOT/$dir
    read_only+=("$dir")
done

jail=()
if [[ ${FACTORY_NO_JAIL:-} == 1 ]]; then
    echo "factory: FACTORY_NO_JAIL=1, running unjailed: nothing stops a write to $HUMAN_REPO" >&2
else
    bwrap_bin=${BWRAP_BIN:-bwrap}
    command -v "$bwrap_bin" > /dev/null || {
        echo "factory: bwrap not found. The jail is what keeps $HUMAN_REPO read-only; install bubblewrap," >&2
        echo "or set FACTORY_NO_JAIL=1 to run without it." >&2
        exit 2
    }
    jail=("$bwrap_bin" --bind / / --dev /dev --proc /proc)
    for dir in "${read_only[@]}"; do
        [[ -d $dir ]] && jail+=(--ro-bind "$(cd "$dir" && pwd)" "$(cd "$dir" && pwd)")
    done
    for dir in "${read_only[@]}"; do
        [[ -d $dir ]] || continue
        "${jail[@]}" findmnt -no OPTIONS --target "$dir" | grep -qE '(^|,)ro(,|$)' \
            || { echo "jail does not mount $dir read-only; refusing to run" >&2; exit 2; }
    done
fi
set_mem_cap || exit 2
scope=("${MEM_CAP[@]}")

mkdir -p "$session/jobs/pending" "$session/jobs/running" "$session/jobs/done" "$session/iterations"
# A job left in running/ by a killed runner starts again.
for job in "$session"/jobs/running/*.sh; do [[ -e $job ]] && mv "$job" "$session/jobs/pending/"; done
progress=$session/progress.md
state=$session/session-state.md
note() { echo "- $(date '+%Y-%m-%d %H:%M %Z') runner: $*" | tee -a "$progress"; }

# A session-limit reset time from the CLI's message ("resets 3:45pm", "resets Mon 12:00am"), as epoch seconds.
reset_epoch() {
    local when at
    when=$(grep -oE "resets [^\"·\\]*" "$1" | head -1 | sed -E 's/^resets //; s/ *$//')
    [[ -n $when ]] || return 1
    at=$(date -d "$when" +%s 2>/dev/null) || return 1
    (( at <= $(date +%s) )) && at=$(( at + 86400 ))
    echo "$at"
}

running_count() { local f=("$session"/jobs/running/*.sh); [[ -e ${f[0]} ]] && echo "${#f[@]}" || echo 0; }
job_running() { compgen -G "$session/jobs/running/*.sh" > /dev/null; }
job_pending() { compgen -G "$session/jobs/pending/*.sh" > /dev/null; }

job_timeout() {
    local t
    t=$(head -n 10 "$1" | grep -m1 -oE '^# timeout: *[0-9]+' | grep -oE '[0-9]+$')
    echo "${t:-$default_job_timeout}"
}

# One job, start to finish: moved to running/, run under its timeout, output and exit code in done/.
run_job() {
    local name=$1 limit code start=$SECONDS
    limit=$(job_timeout "$session/jobs/running/$name.sh")
    note "job $name start, timeout ${limit} s"
    "${scope[@]}" "${jail[@]}" timeout -k 30 "$limit" bash "$session/jobs/running/$name.sh" \
        > "$session/jobs/done/$name.out" 2>&1
    code=$?
    # 137 is also an OOM kill under MEMORY_MAX; only the clock tells the two apart.
    if (( code == 124 || (code == 137 && SECONDS - start >= limit) )); then
        echo "runner: job killed by its ${limit} s timeout (exit $code)" >> "$session/jobs/done/$name.out"
    elif (( code == 137 )); then
        echo "runner: job killed by SIGKILL before its timeout, likely the MEMORY_MAX cap (exit 137)" >> "$session/jobs/done/$name.out"
    fi
    echo "$code" > "$session/jobs/done/$name.exit"
    mv "$session/jobs/running/$name.sh" "$session/jobs/done/$name.sh"
    note "job $name exit $code after $(( SECONDS - start )) s"
}

# One background worker drains jobs/pending, HEAVY_JOBS at a time, so a finished job's successor starts without
# waiting for the current iteration to end. A no-op while the worker lives.
start_job() {
    [[ -n ${worker:-} ]] && kill -0 "$worker" 2> /dev/null && return 0
    job_pending || return 0
    (
        # Children of a killed worker must die before they can move their job to done/.
        trap 'kill $(jobs -p) 2> /dev/null; exit 143' TERM
        while job_pending || [[ -n $(jobs -pr) ]]; do
            if job_pending && (( $(running_count) < HEAVY_JOBS )); then
                next=("$session"/jobs/pending/*.sh)
                name=$(basename "${next[0]}" .sh)
                mv "${next[0]}" "$session/jobs/running/"
                run_job "$name" &
            else
                sleep 1
            fi
        done
    ) &
    worker=$!
}

# A runner that exits takes its worker and the running jobs with it and puts them back in pending: a worker left
# behind would keep draining the queue beside the next runner's.
stop_worker() {
    [[ -n ${worker:-} ]] && kill -0 "$worker" 2> /dev/null || return 0
    kill "$worker" 2> /dev/null
    wait "$worker" 2> /dev/null
    pkill -f "$session/jobs/running/" 2> /dev/null
    for job in "$session"/jobs/running/*.sh; do [[ -e $job ]] && mv "$job" "$session/jobs/pending/"; done
    note "job worker stopped, running jobs back in pending"
}
trap stop_worker EXIT

# Blocks until one running job ends, the deadline passes or STOP appears. One job, not the whole queue: the next
# iteration may have work the finished job unblocked.
wait_for_job() {
    local before
    before=$(compgen -G "$session/jobs/running/*.sh" | sort)
    note "waiting on job: $(echo "$before" | xargs -r -n1 basename | sed 's/\.sh$//' | paste -sd' ')"
    while [[ ! -e $session/STOP ]] && (( $(date +%s) < deadline )); do
        start_job
        local now
        now=$(compgen -G "$session/jobs/running/*.sh" | sort)
        [[ -z $before && -n $now ]] && before=$now
        [[ -n $before ]] && comm -23 <(echo "$before") <(echo "$now") | grep -q . && break
        job_running || job_pending || break
        sleep 5
    done
    start_job
}

# Units built and pauses taken, from the `## Done` section: "- pause-..." lines are pauses, every other item a build.
done_counts() {
    awk '/^## /{in_done = ($0 == "## Done")} in_done && /^- pause-/{p++} in_done && /^- / && !/^- pause-/{b++}
         END{print b + 0, p + 0}' "$state" 2>/dev/null || echo "0 0"
}

# Built units in `## Done` whose units/<id>.md lacks a Contract, Decisions or Commits section. Prints the ids and
# succeeds when any is missing: the human reads the build through these records, so a unit without one is not done.
missing_records() {
    local id heading ids=()
    while read -r id; do
        for heading in "## Contract" "## Decisions" "## Commits"; do
            grep -qx "$heading" "$session/units/$id.md" 2>/dev/null || { ids+=("$id"); break; }
        done
    done < <(awk '/^## /{in_done = ($0 == "## Done")} in_done && /^- / && !/^- pause-/{print $2}' "$state" 2>/dev/null)
    (( ${#ids[@]} )) && echo "${ids[*]}"
}

unchanged=0
note "start, deadline $(date -d "@$deadline" '+%a %H:%M'), model $model, heavy jobs $HEAVY_JOBS"
# A resumed session numbers on from its last transcript, so gzip never meets an existing name.
first=1
for f in "$session"/iterations/[0-9][0-9][0-9][0-9].jsonl*; do
    [[ -e $f ]] || continue
    n=$(basename "$f"); n=$((10#${n%%.*}))
    (( n >= first )) && first=$(( n + 1 ))
done
for (( i = first; i < first + max_iterations; i++ )); do
    compgen -G "$session/iterations/*.jsonl" > /dev/null && gzip -q "$session"/iterations/*.jsonl
    start_job
    [[ -e $session/STOP ]] && { note "stop: STOP file"; exit 0; }
    (( $(date +%s) < deadline )) || { note "stop: deadline"; exit 0; }
    if grep -qE '^Status: (done|blocked)' "$state" 2>/dev/null; then
        note "stop: $(grep -m1 -E '^Status:' "$state")"; exit 0
    fi

    before=$(sha256sum "$state" 2>/dev/null | cut -c1-16)
    out=$session/iterations/$(printf %04d "$i").jsonl
    prompt="Load the factory skill and run one iteration. Session: $session Deadline: $(date -d "@$deadline" '+%Y-%m-%d %H:%M %Z')"
    read -r builds pauses < <(done_counts)
    if (( builds >= pause_every * (pauses + 1) )); then
        prompt="$prompt Pause iteration: $builds units built since the start, $pauses pauses; build nothing new."
        note "iteration $i (pause)"
    else
        note "iteration $i"
    fi
    (cd "$ROOT" && "${scope[@]}" "${jail[@]}" "$claude_bin" -p --model "$model" --permission-mode auto \
        --permission-prompts none --output-format stream-json --verbose --forward-subagent-text "$prompt") > "$out" 2>&1
    code=$?
    summary=$(python3 - "$out" <<'PY'
import json, sys
cost = turns = None
for line in open(sys.argv[1], errors="replace"):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    if isinstance(d, dict) and d.get("type") == "result":
        cost, turns = d.get("total_cost_usd"), d.get("num_turns")
print(f"turns {turns}, est. ${cost}")
PY
)
    note "iteration $i exit $code, $summary"

    if grep -q "hit your weekly limit" "$out"; then
        note "stop: weekly limit"; exit 0
    fi
    if grep -qE "hit your (session|5-hour) limit" "$out"; then
        at=$(reset_epoch "$out") || at=$(( $(date +%s) + 1800 ))
        (( at + 300 < deadline )) || { note "stop: session limit resets past the deadline"; exit 0; }
        note "session limit, sleeping to $(date -d "@$(( at + 300 ))" '+%a %H:%M')"
        sleep $(( at + 300 - $(date +%s) ))
        continue
    fi
    if missing=$(missing_records); then
        note "stop: units done with no complete record in units/: $missing"; exit 1
    fi
    after=$(sha256sum "$state" 2>/dev/null | cut -c1-16)
    if [[ $before == "$after" ]] && { job_running || job_pending; }; then
        wait_for_job
    elif [[ $before == "$after" ]]; then
        unchanged=$(( unchanged + 1 ))
        (( unchanged < 3 )) || { note "stop: 3 iterations left session-state.md unchanged"; exit 1; }
        (( code == 0 )) || sleep 120
    else
        unchanged=0
    fi
    # --gap spreads iterations out so a run leaves room in the 5-hour usage window; never sleeps past the deadline.
    if (( gap > 0 )); then
        nap=$(( gap * 60 )); left=$(( deadline - $(date +%s) ))
        (( nap > left )) && nap=$left
        (( nap > 0 )) && { note "gap, sleeping $(( nap / 60 )) min"; sleep "$nap"; }
    fi
done
note "stop: --max-iterations $max_iterations"
job_running && note "job still running in the background: $(compgen -G "$session/jobs/running/*.sh" | head -1)"
