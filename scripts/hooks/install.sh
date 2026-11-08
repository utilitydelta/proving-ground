#!/usr/bin/env bash
# Points this clone's git hooks at scripts/hooks (repo-local config; a global hooksPath stays as it is elsewhere).
#
#   scripts/hooks/install.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config --local core.hooksPath scripts/hooks
chmod +x scripts/hooks/pre-commit scripts/hooks/no-rm-rf.sh
echo "hooks: core.hooksPath = scripts/hooks"
