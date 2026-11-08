#!/usr/bin/env bash
# The PreToolUse hooks against crafted hook JSON: no-rm-rf.sh and guard-human-repo.sh, allowed and refused cases, and
# the fail-closed inputs. Nothing is deleted or written; the hooks only judge. HUMAN_REPO points at a temp dir.
#
#   scripts/test_hooks.sh
#
# Decided false positive: `rm -rf build` (a literal, relative build dir) is refused. The hook cannot tell a gitignored
# build output from source; the build tool's own clean, or RUN_OUT for fresh output, does the job.
set -uo pipefail

hooks=$(cd "$(dirname "$0")/hooks" && pwd)
root=$(cd "$hooks/../.." && pwd -P)
hr=$(mktemp -d "${TMPDIR:-/tmp}/hooks-human.XXXXXX")
hr=$(cd "$hr" && pwd -P)
export HUMAN_REPO=$hr
failures=0 cases=0

json() { python3 -c 'import json, sys; print(json.dumps({"tool_name": sys.argv[1], "cwd": sys.argv[2],
    "tool_input": {"command": sys.argv[3]} if sys.argv[1] == "Bash" else {"file_path": sys.argv[3]}}))' "$@"; }

# judge <want> <label> <hook> [env assignments...]: stdin is the hook input. Never on the right of a pipe: the counters
# would stay in the subshell and a red run would print OK.
judge() {
    local want=$1 label=$2 hook=$3 code got
    shift 3
    cases=$(( cases + 1 ))
    env "$@" "$hooks/$hook.sh" 2> /dev/null
    code=$?
    got=allow; (( code == 2 )) && got=refuse
    (( code == 0 || code == 2 )) || got="exit $code"
    if [[ $got != "$want" ]]; then
        echo "FAIL $hook: expected $want, got $got: $label"
        failures=$(( failures + 1 ))
    fi
}

# expect <allow|refuse> <hook> <tool> <cwd> <command or file_path>
expect() { judge "$1" "[$3 in $4] $5" "$2" < <(json "$3" "$4" "$5"); }

# Fail closed: input the guard cannot judge is refused, never waved through.
for hook in no-rm-rf guard-human-repo; do
    judge refuse "empty stdin" "$hook" < /dev/null
    judge refuse "unparseable stdin" "$hook" < <(printf 'not json')
    judge refuse "no tool_input" "$hook" < <(printf '{"tool_name": "Bash", "cwd": "/"}')
done
judge refuse "HUMAN_REPO empty" guard-human-repo HUMAN_REPO= < <(json Bash "$root" ls)
judge allow "no-rm-rf needs no HUMAN_REPO" no-rm-rf HUMAN_REPO= < <(json Bash "$root" ls)

s=$root/sessions/session-v1-task-x/scratch
# no-rm-rf: allowed
expect allow no-rm-rf Bash "$root" "rm -rf sessions/session-v1-task-x/scratch/run1"
expect allow no-rm-rf Bash "$root" "rm -rf $s/run1 $s/run2 2>/dev/null"
expect allow no-rm-rf Bash "$root" "rm -rf .run/tmp/gate-bots.abc123 .run/out/x"
expect allow no-rm-rf Bash "$root" "cd sessions/session-v1-task-x && rm -rf scratch/old"
expect allow no-rm-rf Bash "$root" "rm -f \$x/file.txt; echo 'rm -rf /'"
expect allow no-rm-rf Bash "$root" "find $s -name '*.tmp' -delete"
expect allow no-rm-rf Bash "$root" "git clean -nd"
expect allow no-rm-rf Bash "$root" "git clean -fd .run/tmp"
# no-rm-rf: refused
expect refuse no-rm-rf Bash "$root" "rm -rf build"
expect refuse no-rm-rf Bash "$root" 'rm -rf "$tmp"'
expect refuse no-rm-rf Bash "$root" 'rm -rf $(pwd)/x'
expect refuse no-rm-rf Bash "$root" "rm -rf sessions/*/scratch"
expect refuse no-rm-rf Bash "$root" "rm --recursive $s/../../.."
expect refuse no-rm-rf Bash "$root" "timeout -k 5 10 sudo rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "FOO=1 env A=1 nice -n 5 rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "bash -c \"sh -ec 'cd /tmp && rm -rf y'\""
expect refuse no-rm-rf Bash "$root" "eval rm -rf /opt/x"
expect refuse no-rm-rf Bash "$root" "ls | xargs rm -rf"
expect refuse no-rm-rf Bash "$root" "find /opt -type d -exec rm -rf {} +"
expect refuse no-rm-rf Bash "$root" $'echo ok\n( rm -rf /opt/x )'
expect refuse no-rm-rf Bash "$root" "git clean -fdx"
expect refuse no-rm-rf Bash "$root" "git --no-pager -c core.x=y -C /opt/repo clean -f"

# guard-human-repo: allowed
expect allow guard-human-repo Write "$root" "$root/sessions/x/log.md"
expect allow guard-human-repo Bash "$root" "cat $hr/src/a.py > sessions/x/scratch/a.py && cp $hr/a sessions/x/scratch/"
expect allow guard-human-repo Bash "$hr" "git diff HEAD~1 | tee $root/sessions/x/scratch/d.patch"
expect allow guard-human-repo Bash "$root" "git commit -m 'note on $hr' && sed -i s/a/b/ scripts/x.sh"
expect allow guard-human-repo Bash "$root" "git --no-pager -c color.ui=never -C $hr log -5"
expect allow guard-human-repo Bash "$hr" "git branch --list && git stash list && git config --get user.name"
expect allow guard-human-repo Bash "$root" "tar -C $hr -cf sessions/x/scratch/t.tar . && unzip x.zip -d /tmp/u"
expect allow guard-human-repo Bash "$root" "cd $hr && python3 -m pytest"
expect allow guard-human-repo Bash "$hr" "go test ./... && npm test && cargo test"
expect allow guard-human-repo Bash "$root" "D=sessions/x/scratch; echo x > \$D/a"
# guard-human-repo: refused
expect refuse guard-human-repo Write "$root" "$hr/src/a.py"
expect refuse guard-human-repo Edit "$hr" "src/a.py"
expect refuse guard-human-repo NotebookEdit "$root" "$hr/nb.ipynb"
expect refuse guard-human-repo Bash "$root" "echo x >> \$HUMAN_REPO/a.py"
expect refuse guard-human-repo Bash "$root" "cd $hr && echo x > a.py"
expect refuse guard-human-repo Bash "$root" "echo x | tee -a $hr/a.py"
expect refuse guard-human-repo Bash "$root" "D=$hr/src; echo x > \$D/a.py"
expect refuse guard-human-repo Bash "$root" "export D=$hr; cp x \${D}/a.py"
expect refuse guard-human-repo Bash "$hr" "sed -i.bak s/a/b/ a.py"
expect refuse guard-human-repo Bash "$root" "perl -pi -e 's/a/b/' $hr/a.py"
expect refuse guard-human-repo Bash "$root" "awk -i inplace '{print}' $hr/a.py"
expect refuse guard-human-repo Bash "$root" "mv $hr/a.py /tmp/ && rsync -a x/ $hr/src/"
expect refuse guard-human-repo Bash "$root" "tar -xf x.tar -C $hr"
expect refuse guard-human-repo Bash "$root" "unzip -o x.zip -d $hr/src"
expect refuse guard-human-repo Bash "$root" "patch -p1 -d $hr < sessions/x/scratch/fix.diff"
expect refuse guard-human-repo Bash "$root" "bash -c 'cd $hr && git commit -m x'"
expect refuse guard-human-repo Bash "$root" "git --no-pager -c user.name=x -C $hr commit -m x"
expect refuse guard-human-repo Bash "$root" "git --git-dir=$hr/.git --work-tree=$hr reset --hard"
expect refuse guard-human-repo Bash "$hr" "git stash"
expect refuse guard-human-repo Bash "$hr" "git config user.name bot"

rmdir "$hr"
if (( failures )); then
    echo "hooks: $failures of $cases cases failed"
    exit 1
fi
echo "hooks: $cases cases OK"
