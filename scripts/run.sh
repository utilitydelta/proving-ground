#!/usr/bin/env bash
# Run one harness command bounded in time and memory, with its own log and build-output dir, and say how long it took
# in one line for log.md.
#
#   scripts/run.sh [-t SECONDS] [-H] [-l LOGFILE] -- <cmd> [args...]
#
#   -t  hard timeout, default RUN_TIMEOUT (project.env). Past RUN_TIMEOUT the run is heavy: refused without -H.
#   -H  heavy run (sweep, fuzz, proof, mutants, full suite, factory job): takes one of HEAVY_JOBS slots, exit 75 when
#       all are busy. A heavy run started inside a heavy run (a factory job calling the full gate) shares its
#       parent's slot through RUN_HEAVY_SLOT instead of waiting on itself.
#   -l  write stdout and stderr to LOGFILE only; it must not exist yet, so two runs never share a log. Without -l the
#       output goes to the terminal and to RUN_DIR/logs/run-<time>-<pid>.log.
#
# Exports RUN_OUT, a fresh empty dir under RUN_DIR/out/ (default .run/out/), for the command's build output and tapes.
# Memory is capped at MEMORY_MAX (lib/env.sh set_mem_cap). The exit status is always the command's own, 124 on timeout
# and 137 on a kill: an OOM-killed run that reads as a pass is how a dead mutants job once counted as green. Exit 2 on a
# usage error or a refused -t. Heavy slots are lock dirs under RUN_DIR/heavy/ holding the owner's pid; a slot whose
# pid is gone is reclaimed. The verdict line goes to stderr and to the end of the log.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
usage() { sed -n 5p "$0" >&2; exit 2; }
limit=$RUN_TIMEOUT heavy=0 log=
while getopts "t:Hl:" opt; do
    case $opt in
        t) limit=$OPTARG ;;
        H) heavy=1 ;;
        l) log=$OPTARG ;;
        *) usage ;;
    esac
done
shift $(( OPTIND - 1 ))
[[ ${1:-} == -- ]] && shift
(( $# )) || usage
[[ $limit =~ ^[0-9]+$ ]] || { echo "run: -t takes whole seconds" >&2; exit 2; }
if (( limit > RUN_TIMEOUT && ! heavy )); then
    echo "run: refused, -t $limit is past RUN_TIMEOUT $RUN_TIMEOUT: a run that long is heavy, add -H" >&2
    exit 2
fi
timeout_bin=$(command -v timeout || command -v gtimeout) \
    || { echo "run: needs timeout (GNU coreutils; gtimeout on macOS)" >&2; exit 2; }

alive() { [[ -n $1 ]] && kill -0 "$1" 2> /dev/null; }
slot=
release() { [[ -n $slot ]] && rm -f "$slot/pid" && rmdir "$slot" 2> /dev/null; return 0; }
trap release EXIT
if (( heavy )) && [[ ${RUN_HEAVY_SLOT:-} == "$RUN_DIR"/heavy/slot-* ]] \
    && alive "$(cat "$RUN_HEAVY_SLOT/pid" 2> /dev/null)"; then
    : # Nested inside a heavy run that already holds a slot of this RUN_DIR.
elif (( heavy )); then
    mkdir -p "$RUN_DIR/heavy"
    for (( i = 1; i <= HEAVY_JOBS; i++ )); do
        candidate=$RUN_DIR/heavy/slot-$i
        if [[ -d $candidate ]]; then
            alive "$(cat "$candidate/pid" 2> /dev/null)" && continue
            # Stale: its owner died without releasing it.
            rm -f "$candidate/pid"; rmdir "$candidate" 2> /dev/null || continue
        fi
        mkdir "$candidate" 2> /dev/null || continue
        echo $$ > "$candidate/pid"
        slot=$candidate
        break
    done
    if [[ -z $slot ]]; then
        echo "run: refused, $HEAVY_JOBS heavy run(s) already active (HEAVY_JOBS); retry later:" >&2
        for pidfile in "$RUN_DIR"/heavy/slot-*/pid; do
            [[ -e $pidfile ]] && ps -o pid=,etime=,args= -p "$(cat "$pidfile")" >&2 || true
        done
        exit 75
    fi
    export RUN_HEAVY_SLOT=$slot
fi

stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p "$RUN_DIR/out" "$RUN_DIR/logs"
RUN_OUT=$(mktemp -d "$RUN_DIR/out/$stamp-XXXXXX")
export RUN_OUT
tee_too=0
if [[ -z $log ]]; then
    log=$RUN_DIR/logs/run-$stamp-$$.log
    tee_too=1
fi
mkdir -p "$(dirname "$log")"
( set -o noclobber; : > "$log" ) 2> /dev/null || { echo "run: log $log exists; give each run its own" >&2; exit 2; }

set_mem_cap
start=$(date +%s)
set +e
if (( tee_too )); then
    ${MEM_CAP[@]+"${MEM_CAP[@]}"} "$timeout_bin" -k 10 "$limit" "$@" 2>&1 | tee -a "$log"
    code=${PIPESTATUS[0]}
else
    ${MEM_CAP[@]+"${MEM_CAP[@]}"} "$timeout_bin" -k 10 "$limit" "$@" >> "$log" 2>&1
    code=$?
fi
set -e
took=$(( $(date +%s) - start ))
case $code in
    124) verdict="TIMEOUT at $limit s" ;;
    137) (( took >= limit )) && verdict="TIMEOUT at $limit s, killed" || verdict="KILLED (SIGKILL; MEMORY_MAX ${MEMORY_MAX:-unset}?)" ;;
    0) verdict=ok ;;
    *) verdict="exit $code" ;;
esac
tag=
(( heavy )) && tag=", heavy"
line="run: $verdict after $took s$tag, log $log: $*"
echo "$line" >> "$log"
echo "$line" >&2
exit "$code"
