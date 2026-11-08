# shellcheck shell=bash
# Sourced, never run. Number allocation for sessions and register entries, portable to macOS (no find -printf).
#
#   take_lock <dir>               mkdir-based lock at <dir>/.alloc.lock, released on EXIT; fails after 10 s
#   highest_number <dir> <glob>   highest N among <dir>/<glob> names, where <glob> holds one literal '#' standing for N
#
# Picking the next number with `ls | tail` gave three duplicate ids in the source repo when agents ran in parallel: the
# scan and the create happen under one lock (mkdir is atomic), and callers create with mkdir or noclobber so a lock
# held by a dead process cannot turn into a silent overwrite.

take_lock() {
    local lock=$1/.alloc.lock _
    for _ in $(seq 1 100); do
        if mkdir "$lock" 2> /dev/null; then
            # shellcheck disable=SC2064
            trap "rmdir '$lock' 2> /dev/null" EXIT
            return 0
        fi
        sleep 0.1
    done
    echo "alloc: $lock held for 10 s; remove it if no new-id.sh or new-session.sh is running" >&2
    return 1
}

# highest_number sessions 'session-v#-*' -> 12 for session-v12-task-x. Prints 0 when nothing matches.
highest_number() {
    local dir=$1 before=${2%%#*} after=${2#*#} best=0 path name n
    for path in "$dir"/$before[0-9]*$after; do
        [[ -e $path ]] || continue
        name=${path##*/}
        n=${name#"$before"}
        n=${n%%[!0-9]*}
        [[ -n $n ]] || continue
        (( 10#$n > best )) && best=$(( 10#$n ))
    done
    echo "$best"
}
