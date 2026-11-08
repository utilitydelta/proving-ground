#!/usr/bin/env bash
# Allocate the next id for a register entry and write its skeleton with the frontmatter AGENTS.md defines.
#
#   scripts/new-id.sh decision <slug> [session-dir]   -> decisions/NNN-<slug>.md        (# D-NNN)
#   scripts/new-id.sh risk <slug> [session-dir]       -> risks/RNNN-<slug>.md           (# RNNN)
#   scripts/new-id.sh finding <slug> <session-dir>    -> <session-dir>/findings/NNN-<slug>.md
#
# Prints the path written. Without a session dir, decisions and risks name the highest-numbered session.
# Picking the next number with `ls | tail` gave three duplicate ids in the source repo when agents ran in parallel:
# the scan and the create here happen under one lock (mkdir is atomic), and the create itself refuses to overwrite.
# DECISIONS_DIR and RISKS_DIR override the folders (tests).
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
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
    session=$(find "$root/sessions" -maxdepth 1 -type d -name 'session-v*' -printf '%f\n' 2>/dev/null \
        | sed -nE 's/^(session-v[0-9]+).*/\1/p' | sort -t v -k2 -n | tail -1) || true
    session=${session:-session-v0}
fi

lock=$dir/.new-id.lock
for _ in $(seq 1 100); do
    mkdir "$lock" 2> /dev/null && break
    sleep 0.1
done
[[ -d $lock ]] || { echo "new-id: $lock held for 10 s; remove it if no new-id.sh is running" >&2; exit 1; }
trap 'rmdir "$lock"' EXIT

highest=$(find "$dir" -maxdepth 1 -type f -name "${prefix}[0-9]*-*.md" -printf '%f\n' \
    | sed -E "s/^${prefix}0*([0-9]+)-.*/\1/" | sort -n | tail -1)
n=$(( ${highest:-0} + 1 ))
num=$(printf %03d "$n")
title=${slug//-/ }
today=$(date +%F)

case $kind in
    decision)
        path=$dir/$num-$slug.md
        body="---
status: open
decided_by: none
touches: <path::Symbol in the human repo, lead or a harness>
revisit_when: <the event that reopens it>
session: $session
---
# D-$num: $title

<Why, in a sentence or two. Alternatives and why not. Evidence: command or file.>

## History
- $today $session: opened" ;;
    risk)
        path=$dir/R$num-$slug.md
        body="---
likelihood: <1-5>
consequence: <1-5>
score: <likelihood x consequence>
control: none
status: open
decision: none
session: $session
evidence: <command, test or tape that shows the scenario>
---
# R$num: $title

<What happens, step by step. Why this likelihood and consequence. The control and its cost in state, or why none.>

## History
- $today $session: raised" ;;
    finding)
        path=$dir/$num-$slug.md
        body="---
class: <one-way-door | time-sink | regression | two-way-door>
status: open
touches: <path::Symbol in the human repo>
evidence: <one command that reproduces it from this repo>
---
<Claim in one sentence. Evidence output. What the human might do about it.>" ;;
esac

set -o noclobber
printf '%s\n' "$body" > "$path"
echo "$path"
