#!/usr/bin/env bash
# Allocate the next id for a register entry and write its skeleton with the frontmatter AGENTS.md defines.
#
#   scripts/new-id.sh decision <slug> [session-dir]   -> decisions/NNN-<slug>.md        (# D-NNN)
#   scripts/new-id.sh risk <slug> [session-dir]       -> risks/RNNN-<slug>.md           (# RNNN)
#   scripts/new-id.sh finding <slug> <session-dir>    -> <session-dir>/findings/NNN-<slug>.md
#
# Prints the path written. The skeletons live in scripts/skeleton.py, which the register checks share. Without a
# session dir, decisions and risks name the highest-numbered session.
# The scan and the create happen under one lock (lib/alloc.sh), and the create itself refuses to overwrite.
# DECISIONS_DIR and RISKS_DIR override the folders (tests).
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck source=lib/alloc.sh
source "$root/scripts/lib/alloc.sh"
usage() { sed -n 4,6p "$0" >&2; exit 2; }
(( $# >= 2 )) || usage
kind=$1 slug=$2 session_dir=${3:-}
[[ $slug =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "new-id: slug must be lower-case words joined by -" >&2; exit 2; }

case $kind in
    decision) dir=${DECISIONS_DIR:-$root/decisions}; prefix= ;;
    risk) dir=${RISKS_DIR:-$root/risks}; prefix=R ;;
    finding) [[ -n $session_dir ]] || usage; dir=$session_dir/findings; prefix= ;;
    *) usage ;;
esac
mkdir -p "$dir"

if [[ -n $session_dir ]]; then
    session=$(basename "$(cd "$session_dir" && pwd)" | grep -oE '^session-v[0-9]+') \
        || { echo "new-id: $session_dir is not a sessions/session-vN-... folder" >&2; exit 2; }
else
    session=session-v$(highest_number "$root/sessions" 'session-v#-*')
fi

take_lock "$dir" || exit 1
n=$(( $(highest_number "$dir" "${prefix}#-*.md") + 1 ))
num=$(printf %03d "$n")
title=${slug//-/ }
today=$(date +%F)

case $kind in
    decision) path=$dir/$num-$slug.md ;;
    risk) path=$dir/R$num-$slug.md ;;
    finding) path=$dir/$num-$slug.md ;;
esac
body=$(python3 "$root/scripts/skeleton.py" render "$kind" "$num" "$title" "$session" "$today")

set -o noclobber
printf '%s\n' "$body" > "$path"
echo "$path"
