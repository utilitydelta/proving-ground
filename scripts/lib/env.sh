# shellcheck shell=bash
# Sourced, never run. Loads project.env into the caller's shell and resolves its paths.
#
#   source "$(dirname "$0")/lib/env.sh"     # sets ROOT, then every KEY in project.env
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
    RUN_TIMEOUT=${RUN_TIMEOUT:-600}
    HEAVY_JOBS=${HEAVY_JOBS:-1}
    return 0
}


# Bytes from a size like 8G, 512M, 20G or a plain number of bytes.
size_bytes() {
    local n=${1%[KkMmGgTt]} unit=${1: -1}
    [[ $n =~ ^[0-9]+$ ]] || { echo "env: bad size $1" >&2; return 1; }
    case $unit in
        K|k) echo $(( n << 10 )) ;; M|m) echo $(( n << 20 )) ;; G|g) echo $(( n << 30 )) ;; T|t) echo $(( n << 40 )) ;;
        *) echo "$n" ;;
    esac
}

# MEM_CAP: a command prefix that runs its argument under MEMORY_MAX. Prefer a systemd user scope (the whole process
# tree is capped and an OOM kill stays inside it); fall back to ulimit -v per process, with a warning, where
# systemd-run cannot start a user scope (macOS, containers, a systemd service without a user bus).
set_mem_cap() {
    MEM_CAP=()
    [[ -n ${MEMORY_MAX:-} ]] || return 0
    if command -v systemd-run > /dev/null && systemd-run --user --scope -q true 2> /dev/null; then
        MEM_CAP=(systemd-run --user --scope -q -p "MemoryMax=$MEMORY_MAX" -p MemorySwapMax=0)
    else
        local bytes
        bytes=$(size_bytes "$MEMORY_MAX") || return 1
        echo "env: systemd-run --user unavailable, capping with ulimit -v (per process, not per tree)" >&2
        # shellcheck disable=SC2016
        MEM_CAP=(bash -c 'ulimit -v "$0" && exec "$@"' "$(( bytes >> 10 ))")
    fi
}

load_project_env
