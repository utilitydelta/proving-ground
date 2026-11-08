#!/usr/bin/env bash
# Remove old temp dirs the scripts made: gate and plant snapshots kept after a red run under PG_TMP (.run/tmp/), run
# output under RUN_DIR/out/ (.run/out/) and run and gate logs under RUN_DIR/logs/ (.run/logs/). Build caches
# (.run/build/) stay: they are what makes the next build fast.
#
#   scripts/clean-tmp.sh [--older-than-hours N]      (default 24; 0 removes everything, running gates included)
#
# Each entry is removed by its literal resolved path, and only when that path sits directly inside one of the three
# roots; a symlink is unlinked, never followed. Prints each removal and a total. The no-rm-rf hook allows agents
# .run/tmp and .run/out by literal path, so this script is the cleanup and nothing else needs a variable-built rm -r.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
hours=24
case ${1:-} in
    '') ;;
    --older-than-hours) [[ ${2:-} =~ ^[0-9]+$ ]] || { sed -n 6p "$0" >&2; exit 2; }; hours=$2 ;;
    *) sed -n 6p "$0" >&2; exit 2 ;;
esac
mkdir -p "$RUN_DIR/out" "$RUN_DIR/logs"
exec python3 - "$hours" "$PG_TMP" "$RUN_DIR/out" "$RUN_DIR/logs" <<'PY'
import os, shutil, sys, time

hours, roots = float(sys.argv[1]), [os.path.realpath(r) for r in sys.argv[2:]]
cutoff = time.time() - hours * 3600
removed = 0
for root in roots:
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.dirname(os.path.abspath(path)) != root or name in ("", ".", ".."):
            print(f"clean-tmp: refused {path}: not directly inside {root}", file=sys.stderr)
            continue
        if os.lstat(path).st_mtime > cutoff:
            continue
        if os.path.islink(path) or not os.path.isdir(path):
            os.unlink(path)
        else:
            shutil.rmtree(path)
        removed += 1
        print(f"clean-tmp: removed {path}")
print(f"clean-tmp: {removed} removed, older than {sys.argv[1]} h, under {', '.join(roots)}")
PY
