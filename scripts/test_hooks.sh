#!/usr/bin/env bash
# The PreToolUse hooks against crafted hook JSON: no-rm-rf.sh and guard-human-repo.sh, allowed and refused cases.
# Nothing is deleted or written; the hooks only judge. HUMAN_REPO points at a temp dir.
#
#   scripts/test_hooks.sh
#
# Decided false positive: `rm -rf build` (a literal, relative build dir) is refused. The hook cannot tell a gitignored
# build output from source; the build tool's own clean, or RUN_OUT for fresh output, does the job.
set -uo pipefail
# The guard counts the build-output variables of its own environment; run.sh sets them, so a run under it would pass
# cases that must refuse.
unset CARGO_TARGET_DIR PYTHONPYCACHEPREFIX PYTHONDONTWRITEBYTECODE

hooks=$(cd "$(dirname "$0")/hooks" && pwd)
root=$(cd "$hooks/../.." && pwd -P)
hr=$(mktemp -d "${TMPDIR:-/tmp}/hooks-human.XXXXXX")
hr=$(cd "$hr" && pwd -P)
export HUMAN_REPO=$hr
failures=0 cases=0

json() { python3 -c 'import json, sys; print(json.dumps({"tool_name": sys.argv[1], "cwd": sys.argv[2],
    "tool_input": {"command": sys.argv[3]} if sys.argv[1] == "Bash" else {"file_path": sys.argv[3]}}))' "$@"; }

# expect <allow|refuse> <hook> <tool> <cwd> <command or file_path>
expect() {
    local want=$1 hook=$2 tool=$3 cwd=$4 input=$5 code got
    cases=$(( cases + 1 ))
    json "$tool" "$cwd" "$input" | "$hooks/$hook.sh" 2> /dev/null
    code=$?
    got=allow; (( code == 2 )) && got=refuse
    (( code == 0 || code == 2 )) || got="exit $code"
    if [[ $got != "$want" ]]; then
        echo "FAIL $hook: expected $want, got $got: [$tool in $cwd] $input"
        failures=$(( failures + 1 ))
    fi
}

s=$root/sessions/session-v1-task-x/scratch
# no-rm-rf: allowed
expect allow no-rm-rf Bash "$root" "rm -rf sessions/session-v1-task-x/scratch/run1"
expect allow no-rm-rf Bash "$root" "rm -rf $s/run1 $s/run2"
expect allow no-rm-rf Bash "$root" "rm -rf $s"
expect allow no-rm-rf Bash "$root" "rm -rf .run/tmp/gate-bots.abc123"
expect allow no-rm-rf Bash "$root" "cd sessions/session-v1-task-x && rm -rf scratch/old"
expect allow no-rm-rf Bash "$root" "rm -f \$x/file.txt"
expect allow no-rm-rf Bash "$root" "ls -la; git status && echo 'rm -rf /'"
expect allow no-rm-rf Bash "$root" "rm -rf $s/run1 2>/dev/null"
expect allow no-rm-rf Bash "$root" "find $s -name '*.tmp' -delete"
expect allow no-rm-rf Bash "$root" "git clean -nd"
expect allow no-rm-rf Bash "$root" "git clean --dry-run -fdx"
expect allow no-rm-rf Bash "$root" "git clean -fdx $s/run1"
expect allow no-rm-rf Bash "$root" "git clean -fd .run/tmp"
expect allow no-rm-rf Bash "$root" "rsync -a --delete src/ $s/mirror/"
expect allow no-rm-rf Bash "$root" "python3 -c 'import shutil; shutil.rmtree(\"$s/run1\")'"
expect allow no-rm-rf Bash "$root" "rsync -a src/ /opt/mirror/"
# no-rm-rf: refused
expect refuse no-rm-rf Bash "$root" "rm -rf build"
expect refuse no-rm-rf Bash "$root" 'rm -rf "$tmp"'
expect refuse no-rm-rf Bash "$root" 'rm -rf $(pwd)/x'
expect refuse no-rm-rf Bash "$root" 'rm -r -- `echo x`'
expect refuse no-rm-rf Bash "$root" "rm -rf sessions/*/scratch"
expect refuse no-rm-rf Bash "$root" "rm -rf ~/x"
expect refuse no-rm-rf Bash "$root" "rm --recursive /tmp/x"
expect refuse no-rm-rf Bash "$root" "rm -rf $s/../../.."
expect refuse no-rm-rf Bash "$root" "rm -rf /elsewhere/sessions/s/scratch/x"
expect refuse no-rm-rf Bash "$root" "echo hi && sudo rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "timeout 10 rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "timeout -k 5 10 rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "nice -n 5 rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "env A=1 rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "FOO=1 rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "bash -c 'rm -rf /opt/x'"
expect refuse no-rm-rf Bash "$root" "sh -ec \"cd /tmp && rm -rf y\""
expect refuse no-rm-rf Bash "$root" "eval rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "bash -c \"bash -c 'rm -rf /opt/x'\""
expect refuse no-rm-rf Bash "$root" "ls | xargs rm -rf"
expect refuse no-rm-rf Bash "$root" "find . -name x | xargs -0 rm"
expect refuse no-rm-rf Bash "$root" 'find "$dir" -delete'
expect refuse no-rm-rf Bash "$root" "find /opt -type d -exec rm -rf {} +"
expect refuse no-rm-rf Bash "$root" "git clean -fdx"
expect refuse no-rm-rf Bash "$root" "git -C /opt/repo clean -fX"
expect refuse no-rm-rf Bash "$root" "cd \$d && rm -rf scratch/x"
expect refuse no-rm-rf Bash "$root" $'echo ok\nrm -rf /opt/x'
expect refuse no-rm-rf Bash "$root" "( rm -rf /opt/x )"
expect refuse no-rm-rf Bash "$root" "git clean -fd"
expect refuse no-rm-rf Bash "$root" "git clean -f sessions/"
expect refuse no-rm-rf Bash "$root" "git --no-pager -C /opt/repo clean -f"
expect refuse no-rm-rf Bash "$root" "git -c core.x=y clean -fd"
expect refuse no-rm-rf Bash "$root" "rsync -a --delete src/ /opt/mirror/"
expect refuse no-rm-rf Bash "$root" "rsync -a --delete-after src/ docs/"
expect refuse no-rm-rf Bash "$root" "python3 -c 'import shutil; shutil.rmtree(\"/opt/x\")'"
expect refuse no-rm-rf Bash "$root" "python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' /opt/x"

# guard-human-repo: allowed
expect allow guard-human-repo Write "$root" "$root/sessions/x/log.md"
expect allow guard-human-repo Edit "$root" "scripts/run.sh"
expect allow guard-human-repo Bash "$root" "cat $hr/src/a.py > sessions/x/scratch/a.py"
expect allow guard-human-repo Bash "$root" "cp $hr/src/a.py sessions/x/scratch/"
expect allow guard-human-repo Bash "$root" "git -C $hr status && git -C $hr log --oneline -5"
expect allow guard-human-repo Bash "$hr" "git diff HEAD~1 > $root/sessions/x/scratch/d.patch"
expect allow guard-human-repo Bash "$hr" "grep -rn foo . | tee $root/sessions/x/scratch/hits"
expect allow guard-human-repo Bash "$root" "git commit -m 'note on $hr'"
expect allow guard-human-repo Bash "$root" "sed -i s/a/b/ scripts/x.sh"
expect allow guard-human-repo Bash "$hr" "git branch --list && git stash list"
expect allow guard-human-repo Bash "$root" "git --no-pager -C $hr log -5"
expect allow guard-human-repo Bash "$root" "git -P -C $hr diff"
expect allow guard-human-repo Bash "$root" "git --no-optional-locks -C $hr status"
expect allow guard-human-repo Bash "$root" "git -c color.ui=never -C $hr show HEAD"
expect allow guard-human-repo Bash "$root" "git --git-dir=$hr/.git --work-tree=$hr log"
expect allow guard-human-repo Bash "$hr" "git reflog"
expect allow guard-human-repo Bash "$hr" "git reflog show HEAD"
expect allow guard-human-repo Bash "$hr" "git tag -l 'v*'"
expect allow guard-human-repo Bash "$hr" "git tag --list"
expect allow guard-human-repo Bash "$hr" "git config --get user.name"
expect allow guard-human-repo Bash "$hr" "git config user.name"
expect allow guard-human-repo Bash "$hr" "git config --list"
expect allow guard-human-repo Bash "$hr" "git submodule status"
expect allow guard-human-repo Bash "$root" "git commit -m 'make test in $hr'"
expect allow guard-human-repo Bash "$root" "npm install --prefix sessions/x/scratch/copy"
expect allow guard-human-repo Bash "$root" "cargo add serde"
expect allow guard-human-repo Bash "$root" "CARGO_TARGET_DIR=/tmp/t cargo test --manifest-path $hr/Cargo.toml"
expect allow guard-human-repo Bash "$root" "cargo test --manifest-path $hr/Cargo.toml --target-dir .run/build/cargo"
expect allow guard-human-repo Bash "$root" "scripts/run.sh -t 60 -- cargo test --manifest-path $hr/Cargo.toml"
expect allow guard-human-repo Bash "$root" "export CARGO_TARGET_DIR=/tmp/t; cargo build --manifest-path $hr/Cargo.toml"
expect allow guard-human-repo Bash "$hr" "cargo fmt --check"
expect allow guard-human-repo Bash "$hr" "black --check ."
expect allow guard-human-repo Bash "$hr" "prettier --check src"
expect allow guard-human-repo Bash "$hr" "gofmt -l ."
expect allow guard-human-repo Bash "$hr" "go test ./..."
expect allow guard-human-repo Bash "$hr" "go vet ./..."
expect allow guard-human-repo Bash "$hr" "go build -o $root/.run/build/bin ./cmd/x"
expect allow guard-human-repo Bash "$hr" "tsc --noEmit -p ."
expect allow guard-human-repo Bash "$hr" "dotnet format --verify-no-changes"
expect allow guard-human-repo Bash "$root" "scripts/run.sh -t 60 -- python3 harness/sim.py --tree $hr"
expect allow guard-human-repo Bash "$root" "PYTHONDONTWRITEBYTECODE=1 python3 harness/sim.py --tree $hr"
expect allow guard-human-repo Bash "$root" "python3 -B harness/sim.py --tree=$hr"
expect allow guard-human-repo Bash "$root" "python3 harness/sim.py --tree sessions/x/scratch/copy"
expect allow guard-human-repo Bash "$hr" "PYTHONPYCACHEPREFIX=/tmp/pyc python3 -m pytest -p no:cacheprovider"
expect allow guard-human-repo Bash "$root" "pip install -e sessions/x/scratch/copy"
expect allow guard-human-repo Bash "$root" "make -C sessions/x/scratch/copy"
# guard-human-repo: refused
expect refuse guard-human-repo Write "$root" "$hr/src/a.py"
expect refuse guard-human-repo Edit "$hr" "src/a.py"
expect refuse guard-human-repo NotebookEdit "$root" "$hr/nb.ipynb"
expect refuse guard-human-repo Bash "$root" "echo x > $hr/a.py"
expect refuse guard-human-repo Bash "$root" "echo x >> \$HUMAN_REPO/a.py"
expect refuse guard-human-repo Bash "$hr" "echo x > a.py"
expect refuse guard-human-repo Bash "$root" "cd $hr && echo x > a.py"
expect refuse guard-human-repo Bash "$root" "echo x | tee $hr/a.py"
expect refuse guard-human-repo Bash "$root" "sed -i 's/a/b/' $hr/a.py"
expect refuse guard-human-repo Bash "$hr" "sed -i.bak s/a/b/ a.py"
expect refuse guard-human-repo Bash "$root" "mv $hr/a.py /tmp/"
expect refuse guard-human-repo Bash "$root" "cp sessions/x/scratch/a.py $hr/src/"
expect refuse guard-human-repo Bash "$root" "rm $hr/a.py"
expect refuse guard-human-repo Bash "$root" "git -C $hr commit -am x"
expect refuse guard-human-repo Bash "$hr" "git checkout -- ."
expect refuse guard-human-repo Bash "$hr" "git reset --hard"
expect refuse guard-human-repo Bash "$hr" "git stash"
expect refuse guard-human-repo Bash "$hr" "git clean -fd"
expect refuse guard-human-repo Bash "$root" "bash -c 'cd $hr && git commit -m x'"
expect refuse guard-human-repo Bash "$root" "touch $hr/new"
expect refuse guard-human-repo Bash "$root" "git --no-pager -C $hr commit -m x"
expect refuse guard-human-repo Bash "$root" "git -P -C $hr checkout main"
expect refuse guard-human-repo Bash "$root" "git --git-dir=$hr/.git --work-tree=$hr reset --hard"
expect refuse guard-human-repo Bash "$root" "git --work-tree $hr checkout -- ."
expect refuse guard-human-repo Bash "$root" "git -c user.name=x -C $hr commit -m x"
expect refuse guard-human-repo Bash "$hr" "git tag v1"
expect refuse guard-human-repo Bash "$hr" "git tag -d v1"
expect refuse guard-human-repo Bash "$hr" "git config user.name bot"
expect refuse guard-human-repo Bash "$hr" "git config --unset user.name"
expect refuse guard-human-repo Bash "$hr" "git reflog expire --all"
expect refuse guard-human-repo Bash "$hr" "git submodule update --init"
expect refuse guard-human-repo Bash "$hr" "git archive -o out.tar HEAD"
expect refuse guard-human-repo Bash "$hr" "npm install"
expect refuse guard-human-repo Bash "$hr" "npm ci"
expect refuse guard-human-repo Bash "$root" "npm install --prefix $hr"
expect refuse guard-human-repo Bash "$root" "pnpm -C $hr add lodash"
expect refuse guard-human-repo Bash "$root" "yarn --cwd $hr"
expect refuse guard-human-repo Bash "$hr" "yarn"
expect refuse guard-human-repo Bash "$root" "pip install -e $hr"
expect refuse guard-human-repo Bash "$hr" "pip install -e ."
expect refuse guard-human-repo Bash "$hr" "python3 -m pip install ."
expect refuse guard-human-repo Bash "$root" "cargo add serde --manifest-path $hr/Cargo.toml"
expect refuse guard-human-repo Bash "$hr" "cargo update"
expect refuse guard-human-repo Bash "$hr" "cargo fmt"
expect refuse guard-human-repo Bash "$hr" "go fmt ./..."
expect refuse guard-human-repo Bash "$hr" "gofmt -w ."
expect refuse guard-human-repo Bash "$root" "black $hr/src"
expect refuse guard-human-repo Bash "$hr" "prettier --write src"
expect refuse guard-human-repo Bash "$hr" "prettier -w src"
expect refuse guard-human-repo Bash "$hr" "eslint --fix src"
expect refuse guard-human-repo Bash "$hr" "ruff check --fix ."
expect refuse guard-human-repo Bash "$hr" "ruff format ."
expect refuse guard-human-repo Bash "$root" "clang-format -i $hr/a.c"
expect refuse guard-human-repo Bash "$hr" "dotnet format"
expect refuse guard-human-repo Bash "$hr" "tsc"
expect refuse guard-human-repo Bash "$root" "tsc -p $hr"
expect refuse guard-human-repo Bash "$hr" "make test 2>/dev/null"
expect refuse guard-human-repo Bash "$root" "make -C $hr"
expect refuse guard-human-repo Bash "$hr" "dotnet build"
expect refuse guard-human-repo Bash "$root" "dotnet test $hr/x.sln"
expect refuse guard-human-repo Bash "$hr" "dotnet run"
expect refuse guard-human-repo Bash "$hr" "go build ./cmd/x"
expect refuse guard-human-repo Bash "$hr" "go mod tidy"
expect refuse guard-human-repo Bash "$hr" "cargo build"
expect refuse guard-human-repo Bash "$root" "cargo test --manifest-path $hr/Cargo.toml"
expect refuse guard-human-repo Bash "$root" "cargo test --manifest-path=$hr/Cargo.toml --target-dir $hr/target"
expect refuse guard-human-repo Bash "$root" "CARGO_TARGET_DIR=$hr/target cargo run --manifest-path $hr/Cargo.toml"
expect refuse guard-human-repo Bash "$root" "python3 harness/sim.py --tree $hr"
expect refuse guard-human-repo Bash "$hr" "python3 -m unittest"
expect refuse guard-human-repo Bash "$hr" "pytest"
expect refuse guard-human-repo Bash "$root" "scripts/run.sh -- pytest $hr/tests"

rmdir "$hr"
if (( failures )); then
    echo "hooks: $failures of $cases cases failed"
    exit 1
fi
echo "hooks: $cases cases OK"
