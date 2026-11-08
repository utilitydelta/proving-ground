#!/usr/bin/env bash
# Write a plant patch in the format scripts/plants.sh reads, without hand-editing diff paths.
#
#   scripts/new-plant.sh <tree> <plants-dir>/<name> "<one line on the bug>" "<check>" [--timeout S] [--from-diff F]
#   scripts/new-plant.sh --finish <copy>
#
# First form: copies <tree> (without .git) twice under a fresh mktemp -d in PG_TMP, a pristine base and an edit copy,
# and prints the edit copy's path. Plant the bug there with ordinary edits, then run the second form on that path: it
# diffs base against edit with tree-root paths (a/x, b/x), writes <plants-dir>/<name>.patch with its `#` header
# (description, `# check:`, optional `# timeout:`), removes the temp dir and prints the patch path. With --from-diff,
# F (a unified diff with tree-root paths, -p1) is applied to the edit copy and the patch is written at once.
# Refuses to overwrite a patch, an empty diff, or a check that is empty. Prove it next: scripts/plants.sh <tree>
# <plants-dir> must print OK for it.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
# shellcheck source=lib/verdict.sh
source "$ROOT/scripts/lib/verdict.sh"
usage() { sed -n 4,5p "$0" >&2; exit 2; }
export PG_TMP

finish() {
    local edit work base
    edit=$(cd "$1" && pwd -P) || usage
    work=$(dirname "$edit")
    [[ -f $work/plant.env && -d $work/base && $edit == "$work/edit" ]] \
        || { echo "new-plant: $1 is not an edit copy made by new-plant.sh" >&2; exit 2; }
    # shellcheck disable=SC1091
    source "$work/plant.env"
    base=$work/base
    [[ ! -e $patch ]] || { echo "new-plant: $patch exists; pick another name" >&2; exit 2; }
    local diff
    diff=$(cd "$work" && git diff --no-index --binary -- base edit || true)
    [[ -n $diff ]] || { echo "new-plant: no change between the base and $edit; plant the bug first" >&2; exit 2; }
    mkdir -p "$(dirname "$patch")"
    {
        echo "# $desc"
        echo "# check: $check"
        [[ -n $limit ]] && echo "# timeout: $limit"
        # git names a new or deleted file under whichever side has it: strip both prefixes from both sides.
        sed -E -e '/^diff --git /s# ([ab])/(base|edit)/# \1/#g' \
               -e 's#^(---|\+\+\+) ([ab])/(base|edit)/#\1 \2/#' \
               -e 's#^(rename|copy) (from|to) (base|edit)/#\1 \2 #' <<< "$diff"
    } > "$patch"
    drop_tmp "$work"
    echo "$patch"
}

if [[ ${1:-} == --finish ]]; then
    (( $# == 2 )) || usage
    finish "$2"
    exit 0
fi

(( $# >= 4 )) || usage
tree=$(cd "$1" && pwd -P) || { echo "new-plant: no tree at $1" >&2; exit 2; }
target=$2 desc=$3 check=$4
shift 4
limit= from=
while (( $# )); do
    case $1 in
        --timeout) [[ ${2:-} =~ ^[0-9]+$ ]] || usage; limit=$2; shift 2 ;;
        --from-diff) from=$(cd "$(dirname "${2:?}")" && pwd -P)/$(basename "$2"); shift 2 ;;
        *) usage ;;
    esac
done
[[ $target == */* && $(basename "$target") =~ ^[a-z0-9][a-z0-9_-]*$ ]] \
    || { echo "new-plant: name is <plants-dir>/<name>, name in lower-case words joined by - or _" >&2; exit 2; }
[[ -n ${check// } && -n ${desc// } ]] || { echo "new-plant: the description and the check must not be empty" >&2; exit 2; }
plants_dir=$(mkdir -p "$(dirname "$target")" && cd "$(dirname "$target")" && pwd -P)
patch=$plants_dir/$(basename "$target").patch
[[ ! -e $patch ]] || { echo "new-plant: $patch exists; pick another name" >&2; exit 2; }

work=$(mktemp -d "$PG_TMP/plant.XXXXXX")
mkdir "$work/base" "$work/edit"
tar -C "$tree" --exclude=.git -cf - . | tar -C "$work/base" -xf -
tar -C "$tree" --exclude=.git -cf - . | tar -C "$work/edit" -xf -
printf 'patch=%q\ndesc=%q\ncheck=%q\nlimit=%q\n' "$patch" "$desc" "$check" "$limit" > "$work/plant.env"
if [[ -n $from ]]; then
    (cd "$work/edit" && GIT_CEILING_DIRECTORIES=$work git apply -p1 "$from") \
        || { echo "new-plant: $from does not apply to $tree; kept $work" >&2; exit 1; }
    finish "$work/edit"
    exit 0
fi
echo "new-plant: plant the bug in the copy below, then: scripts/new-plant.sh --finish $work/edit" >&2
echo "$work/edit"
