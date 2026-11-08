#!/usr/bin/env bash
# Run one harness command bounded in time and memory, and say how long it took in one line for log.md.
#
#   scripts/run.sh [-t SECONDS] [-H] [-l LOGFILE] -- <cmd> [args...]
#
#   -t  hard timeout, default RUN_TIMEOUT from project.env
#   -H  heavy run (sweep, fuzz, proof, mutants, full suite): refused when HEAVY_JOBS heavy runs are already active
#   -l  write the command's stdout and stderr to LOGFILE, which must not exist yet, so two runs never share a log
#
# Memory is capped at MEMORY_MAX (see lib/env.sh set_mem_cap). The exit status is always the command's own, 124 on
# timeout and 137 on a kill: an OOM-killed run that reads as a pass is how a dead mutants job once counted as green.
# Heavy slots are lock dirs under .run/heavy/ holding the owner's pid; a slot whose pid is gone is reclaimed.
# Exit 75 when refused for want of a heavy slot.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
limit=$RUN_TIMEOUT heavy=0 log=
while getopts "t:Hl:" opt; do
    case $opt in
        t) limit=$OPTARG ;;
        H) heavy=1 ;;
        l) log=$OPTARG ;;
        *) sed -n 4p "$0" >&2; exit 2 ;;
    esac
done
shift $(( OPTIND - 1 ))
[[ ${1:-} == -- ]] && shift
(( $# )) || { sed -n 4p "$0" >&2; exit 2; }
[[ $limit =~ ^[0-9]+$ ]] || { echo "run: -t takes whole seconds" >&2; exit 2; }

slot=
release() { [[ -n $slot ]] && rm -f "$slot/pid" && rmdir "$slot" 2> /dev/null; return 0; }
trap release EXIT
if (( heavy )); then
    mkdir -p "$ROOT/.run/heavy"
    for (( i = 1; i <= HEAVY_JOBS; i++ )); do
        candidate=$ROOT/.run/heavy/slot-$i
        if [[ -d $candidate ]]; then
            owner=$(cat "$candidate/pid" 2> /dev/null || true)
            [[ -n $owner ]] && kill -0 "$owner" 2> /dev/null && continue
            # Stale: its owner died without releasing it.
            rm -f "$candidate/pid"; rmdir "$candidate" 2> /dev/null || continue
        fi
        mkdir "$candidate" 2> /dev/null || continue
        echo $$ > "$candidate/pid"
        slot=$candidate
        break
    done
    if [[ -z $slot ]]; then
        echo "run: refused, $HEAVY_JOBS heavy run(s) already active (HEAVY_JOBS):" >&2
        for pidfile in "$ROOT"/.run/heavy/slot-*/pid; do
            [[ -e $pidfile ]] && ps -o pid=,etime=,args= -p "$(cat "$pidfile")" >&2 || true
        done
        exit 75
    fi
fi

set_mem_cap
start=$(date +%s)
set +e
if [[ -n $log ]]; then
    mkdir -p "$(dirname "$log")"
    ( set -o noclobber; : > "$log" ) 2> /dev/null || { echo "run: log $log exists; give each run its own" >&2; exit 2; }
    "${MEM_CAP[@]}" timeout -k 10 "$limit" "$@" >> "$log" 2>&1
else
    "${MEM_CAP[@]}" timeout -k 10 "$limit" "$@"
fi
code=$?
set -e
took=$(( $(date +%s) - start ))
case $code in
    124) verdict="TIMEOUT at $limit s" ;;
    137) (( took >= limit )) && verdict="TIMEOUT at $limit s, killed" || verdict="KILLED (SIGKILL; MEMORY_MAX ${MEMORY_MAX:-unset}?)" ;;
    0) verdict=ok ;;
    *) verdict="exit $code" ;;
esac
echo "run: $verdict after $took s$( (( heavy )) && echo ", heavy")${log:+, log $log}: $*" >&2
exit "$code"
