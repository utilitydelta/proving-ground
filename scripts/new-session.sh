#!/usr/bin/env bash
# Create the next session folder with its skeleton.
#
#   scripts/new-session.sh <mode> <slug>
#
# Modes (AGENTS.md): watch task factory tend debrief closeoff invariant. N is the highest existing session-vN plus one,
# picked and claimed under the same lock new-id.sh takes (lib/alloc.sh), so two sessions started together never share
# an N. Writes goal.md (## Ask, ## Acceptance, ## Delta, ## Weight, ## Builds on), log.md, human.md, report.md,
# scraps.md, findings/, briefs/, reviews/ and scratch/ (gitignored). Factory mode adds what scripts/factory.sh and the factory
# skill read: session-state.md, progress.md, units/ and jobs/{pending,running,done}/. Prints the folder.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
# shellcheck source=lib/alloc.sh
source "$(dirname "$0")/lib/alloc.sh"
modes=(watch task factory tend debrief closeoff invariant)
(( $# == 2 )) || { sed -n 4p "$0" >&2; exit 2; }
mode=$1 slug=$2
[[ " ${modes[*]} " == *" $mode "* ]] || { echo "new-session: mode must be one of: ${modes[*]}" >&2; exit 2; }
[[ $slug =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "new-session: slug must be lower-case words joined by -" >&2; exit 2; }
if [[ ! -d $HUMAN_REPO ]]; then
    echo "new-session: WARNING: HUMAN_REPO $HUMAN_REPO does not exist. Nothing in this session can build or test the" >&2
    echo "new-session: WARNING: product until project.env points at it." >&2
fi

sessions=$ROOT/sessions
mkdir -p "$sessions"
take_lock "$sessions" || exit 1
n=$(( $(highest_number "$sessions" 'session-v#-*') + 1 ))
dir=$sessions/session-v$n-$mode-$slug
mkdir "$dir"
mkdir "$dir/findings" "$dir/briefs" "$dir/reviews" "$dir/scratch"
cat > "$dir/goal.md" <<EOF
# Goal: $slug

## Ask

## Acceptance

## Delta

## Weight

## Builds on
EOF
echo "# Log: session-v$n" > "$dir/log.md"
echo "# Human: session-v$n" > "$dir/human.md"
echo "# Report: session-v$n" > "$dir/report.md"
echo "# Scraps: session-v$n" > "$dir/scraps.md"

if [[ $mode == factory ]]; then
    head_of() { [[ -n $1 ]] && git -C "$1" rev-parse --short HEAD 2> /dev/null || echo none; }
    cat > "$dir/session-state.md" <<EOF
Status: building
human head: $(head_of "$HUMAN_REPO")
lead head: $(head_of "${LEAD_REPO:-}")

## Queue

## Waiting

## Done
EOF
    echo "# Progress: session-v$n" > "$dir/progress.md"
    mkdir -p "$dir/units" "$dir/jobs/pending" "$dir/jobs/running" "$dir/jobs/done"
fi
echo "$dir"
