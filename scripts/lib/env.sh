# shellcheck shell=bash
# Sourced, never run. Loads project.env into the caller's shell and resolves its paths.
#
#   source "$(dirname "$0")/lib/env.sh"     # sets ROOT, every KEY in project.env, RUN_DIR, PG_TMP and HEAVY_DIR
#
# A variable already set in the environment wins over project.env, so a test or a one-off run can point
# HUMAN_REPO or FACTORY_READ_ONLY elsewhere without editing the file. HUMAN_REPO and LEAD_REPO come back
# absolute (relative ones resolve against ROOT), whether or not the directory exists.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

load_project_env() {
    local file=${PROJECT_ENV:-$ROOT/project.env}
    [[ -f $file ]] || { echo "env: $file not found" >&2; return 1; }
    local key keys saved=()
    keys=$(grep -oE '^[A-Z_][A-Z0-9_]*=' "$file" | tr -d '=')
    for key in $keys; do
        [[ -n ${!key+x} ]] && saved+=("$key=${!key}")
    done
    # shellcheck disable=SC1090
    source "$file"
    local pair
    for pair in "${saved[@]}"; do
        printf -v "${pair%%=*}" '%s' "${pair#*=}"
    done
    for key in HUMAN_REPO LEAD_REPO; do
        [[ -n ${!key:-} && ${!key} != /* ]] && printf -v "$key" '%s' "$ROOT/${!key}"
    done
    RUN_TIMEOUT=${RUN_TIMEOUT:-300}
    HEAVY_JOBS=${HEAVY_JOBS:-1}
    HEAVY_TIMEOUT_MAX=${HEAVY_TIMEOUT_MAX:-3600}
    # Heavy slots are per machine, not per clone: two clones of this template (or two adopting projects) on one box
    # share the CPU, so they share the slots. Tests point it at a temp dir.
    HEAVY_DIR=${HEAVY_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/proving-ground/heavy}
    # Per-machine runtime state: heavy slots, run logs, build output. Tests point it at a temp dir.
    RUN_DIR=${RUN_DIR:-$ROOT/.run}
    # Root for every temp dir the scripts make (gate and plant snapshots): `mktemp -d "$PG_TMP/x.XXXXXX"`. Under
    # .run/ so scripts/clean-tmp.sh can clear it by literal path; $TMPDIR copies piled up with no way to delete them.
    PG_TMP=${PG_TMP:-$RUN_DIR/tmp}
    mkdir -p "$PG_TMP"
    if [[ -n ${HUMAN_REPO:-} && ! -d $HUMAN_REPO ]]; then
        echo "env: warning: HUMAN_REPO $HUMAN_REPO does not exist; set it in project.env" >&2
    fi
    return 0
}

# MEM_CAP: a command prefix that runs its argument under MEMORY_MAX in a systemd user scope: the whole process tree
# is capped and an OOM kill stays inside it. Where systemd-run cannot start a user scope (macOS, containers, a service
# without a user bus) the run goes uncapped with a warning. Never `ulimit -v` or `prlimit --data`: both count address
# space reserved but never touched, which kills ASAN (terabytes of shadow), Go and the JVM at startup and reads as a
# red test.
set_mem_cap() {
    MEM_CAP=()
    [[ -n ${MEMORY_MAX:-} ]] || return 0
    if command -v systemd-run > /dev/null && systemd-run --user --scope -q true 2> /dev/null; then
        MEM_CAP=(systemd-run --user --scope -q -p "MemoryMax=$MEMORY_MAX" -p MemorySwapMax=0)
    else
        echo "env: warning: no systemd user scope here, so MEMORY_MAX=$MEMORY_MAX is not enforced; watch memory by hand" >&2
    fi
}

load_project_env
