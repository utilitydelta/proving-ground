#!/usr/bin/env python3
"""Claude Code PreToolUse guards behind scripts/hooks/no-rm-rf.sh and guard-human-repo.sh. Best effort: they catch
slips, not adversaries. The factory jail (scripts/factory.sh, bwrap read-only mounts) is the hard boundary.

  shell_guard.py no-rm-rf     Bash
  shell_guard.py human-repo   Edit, Write, MultiEdit, NotebookEdit, Bash

stdin is the hook JSON ({"tool_name", "tool_input", "cwd"}). Exit 0 allows; exit 2 refuses with the reason on stderr.
Fails closed (exit 2): stdin empty or not a JSON object, tool_input missing, and for human-repo a HUMAN_REPO that is
unset or empty (the environment wins, else project.env; relative to this repo's root).

no-rm-rf refuses rm -r/-R/--recursive, find -delete or -exec/-execdir/-ok rm, rsync --delete* (its destination) and
git clean without -n/--dry-run (its paths, else where it runs), unless every target is a literal path resolving
inside <root>/sessions/<session>/scratch, <root>/.run/tmp or <root>/.run/out. A target holding $, `, a glob or ~ is
refused, and so is any xargs rm.

human-repo refuses when the path resolves under HUMAN_REPO:
  - Edit/Write/MultiEdit/NotebookEdit file_path or notebook_path (realpath)
  - redirects > and >>, tee operands, dd of=
  - sed -i, perl -i, awk/gawk -i inplace on any operand
  - rm, rmdir, mv, touch, mkdir, chmod, chown, truncate, ln, unlink on any operand
  - cp/install destination (last operand or -t), rsync destination; tar -C (else the cwd) when extracting; unzip -d
    (else the cwd) unless listing or testing; patch -d (else the cwd) unless --dry-run
  - git anything but reads, with global options peeled (-C, -c, --git-dir, --work-tree, --no-pager, -P, ...)
Allowed: reading the human repo and running tests or tools in it (python, pytest, go test, npm test, cargo test).
Build output is scripts/run.sh's job (out-of-tree caches) and the gate's (snapshots), not this hook's.

Parsing: shlex, split at ; && || | & ( ) and newlines; wrappers peeled (sudo, env, nice, timeout, nohup, command,
VAR=x, scripts/run.sh); `bash -c`, `sh -c` and `eval` strings checked recursively; `cd <literal>` followed. For
human-repo, $HUMAN_REPO, $HOME, ~ and variables set earlier in the command by `VAR=x` or `export VAR=x` are
expanded; other variables are not. A heredoc body is read as commands.
"""
import json
import os
import re
import shlex
import sys

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KEYWORDS = {"{", "}", "!", "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "time", "exec"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
UNSAFE = re.compile(r"[$`*?\[{~]")
ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.S)
WRAPPERS = {"sudo": ("-u", "-g"), "command": (), "nohup": (), "nice": ("-n",), "env": ("-u", "-C", "-S"),
            "timeout": ("-k", "-s"), "run.sh": ("-t", "-l")}
WRITERS = {"tee", "rm", "rmdir", "mv", "touch", "mkdir", "chmod", "chown", "truncate", "ln", "unlink"}


def commands(command):
    """Simple commands as (argv, output redirect targets). Input redirect and fd-dup targets are dropped."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        toks = list(lexer)
    except ValueError:
        toks = command.replace("\n", " ; ").split()
    out, argv, writes, i = [], [], [], 0
    while i < len(toks):
        tok = toks[i]
        if tok and set(tok) <= set("();<>|&"):
            if "<" in tok or ">" in tok:
                if argv and argv[-1].isdigit():
                    argv.pop()
                if ">" in tok and not tok.endswith("&") and i + 1 < len(toks):
                    writes.append(toks[i + 1])
                i += 2
                continue
            if argv or writes:
                out.append((argv, writes))
            argv, writes = [], []
        else:
            argv.append(tok)
        i += 1
    if argv or writes:
        out.append((argv, writes))
    return out


def drop_options(argv, valued=()):
    i = 0
    while i < len(argv) and argv[i].startswith("-") and argv[i] != "--":
        i += 2 if argv[i] in valued else 1
    return argv[i + 1:] if i < len(argv) and argv[i] == "--" else argv[i:]


def unwrap(argv, env):
    """Peel keywords, VAR=x prefixes and wrappers. Returns (argv, env plus the prefixes)."""
    env = dict(env)
    while argv:
        name, m = os.path.basename(argv[0]), ASSIGN.match(argv[0])
        if argv[0] in KEYWORDS:
            argv = argv[1:]
        elif m:
            env[m.group(1)] = m.group(2)
            argv = argv[1:]
        elif name in WRAPPERS:
            argv = drop_options(argv[1:], WRAPPERS[name])
            argv = argv[1:] if name == "timeout" else argv
        else:
            break
    return argv, env


def walk(command, cwd, check, expand, env=None):
    """First refusal from check(argv, writes, cwd) over every simple command, or None. cwd None means unknown."""
    env = dict(env or {})
    for raw, writes in commands(command):
        argv, cmd_env = unwrap(raw, env)
        if not argv or argv[0] == "export":
            env = cmd_env
            for k, v in (ASSIGN.match(a).groups() for a in argv[1:] if ASSIGN.match(a)):
                env[k] = v
            if not writes:
                continue
        argv = [expand(a, cmd_env) for a in argv]
        writes = [expand(w, cmd_env) for w in writes]
        if argv and argv[0] in ("cd", "pushd"):
            target = argv[1] if len(argv) > 1 else None
            cwd = None if target is None or UNSAFE.search(target) else resolve(target, cwd)
            continue
        name = os.path.basename(argv[0]) if argv else ""
        inner = " ".join(argv[1:]) if name == "eval" else None
        if name in SHELLS:
            inner = next((argv[i + 1] for i, a in enumerate(argv[1:-1], 1) if re.match(r"^-[a-z]*c[a-z]*$", a)), None)
        why = walk(inner, cwd, check, expand, cmd_env) if inner is not None else check(argv, writes, cwd)
        if why:
            return why
    return None


def resolve(path, cwd):
    if os.path.isabs(path):
        return os.path.realpath(path)
    return os.path.realpath(os.path.join(cwd, path)) if cwd else None


def inside(path, root):
    return path is not None and (path == root or path.startswith(root.rstrip(os.sep) + os.sep))


def operands(argv):
    return [a for a in argv[1:] if not a.startswith("-")]


def option_value(argv, *names):
    for i, a in enumerate(argv):
        if a in names and i + 1 < len(argv):
            return argv[i + 1]
        if "=" in a and a.split("=", 1)[0] in names:
            return a.split("=", 1)[1]
    return None


GIT_GLOBAL_FLAGS = {"--no-pager", "-P", "--paginate", "-p", "--no-optional-locks", "--bare", "--no-replace-objects",
                    "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs",
                    "--no-advice", "--no-lazy-fetch"}
GIT_GLOBAL_VALUED = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env",
                     "--super-prefix"}
GIT_READ = {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "blame", "grep", "cat-file",
            "describe", "shortlog", "rev-list", "for-each-ref", "name-rev", "merge-base", "help", "version",
            "whatchanged", "show-ref", "count-objects", "check-ignore", "var", "show-branch", "range-diff",
            "cherry", "ls-remote", "verify-commit", "verify-tag", "fsck"}
GIT_READ_ARGS = {"branch": {"--list", "-l", "-a", "-r", "-v", "-vv", "--show-current", "--all", "--remotes",
                            "--contains", "--merged", "--no-merged"},
                 "stash": {"list", "show"}, "worktree": {"list"}, "remote": {"-v", "show", "get-url"},
                 "tag": {"-l", "--list", "-v", "--verify", "--contains", "--points-at"},
                 "submodule": {"status", "summary"}, "reflog": {"show"}}
GIT_CONFIG_GET = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l", "get", "list"}
GIT_CONFIG_WRITE = {"--unset", "--unset-all", "--add", "--replace-all", "--rename-section", "--remove-section",
                    "-e", "--edit", "set", "unset", "rename-section", "remove-section", "edit"}


def git_parse(argv, cwd):
    """(subcommand args, places): every global option peeled; places are the directories it acts on (None unknown)."""
    rest, where, places = argv[1:], cwd, []
    while rest and rest[0].startswith("-"):
        opt, value, step = rest[0], None, 1
        if "=" in opt and opt.split("=", 1)[0] in GIT_GLOBAL_VALUED:
            opt, value = opt.split("=", 1)
        elif opt in GIT_GLOBAL_VALUED:
            value, step = (rest[1] if len(rest) > 1 else None), 2
        elif opt not in GIT_GLOBAL_FLAGS:
            break
        if opt == "-C" and value is not None:
            where = resolve(value, where) if not UNSAFE.search(value) else None
        elif opt in ("--work-tree", "--git-dir") and value is not None:
            places.append(resolve(value, where) if not UNSAFE.search(value) else None)
        rest = rest[step:]
    return rest, [where, *places]


def git_problem(argv, cwd, hr):
    rest, places = git_parse(argv, cwd)
    if not rest or not any(inside(p, hr) for p in places):
        return None
    sub, args = rest[0], set(rest[1:])
    if sub == "archive":
        out = option_value(rest, "-o", "--output")
        return "git archive -o into the human repo" if out and inside(resolve(out, cwd), hr) else None
    if sub in GIT_READ:
        return None
    if sub == "config" and not GIT_CONFIG_WRITE & args and (GIT_CONFIG_GET & args or len(operands(rest)) == 1):
        return None
    allowed = GIT_READ_ARGS.get(sub)
    if allowed is not None and ((not args and sub in ("branch", "remote", "tag", "reflog")) or allowed & args):
        return None
    return f"git {sub} in the human repo"


def human_check(hr):
    def under(path, cwd):
        return not path.startswith("/dev/") and inside(resolve(path, cwd), hr)

    def check(argv, writes, cwd):
        if any(under(w, cwd) for w in writes):
            return "redirect into the human repo"
        if not argv:
            return None
        name, ops = os.path.basename(argv[0]), operands(argv)
        hit = any(under(p, cwd) for p in ops)
        in_place = {"sed": r"^(-[a-zA-Z]*i|--in-place)", "perl": r"^-[a-zA-Z]*i"}.get(name)
        if in_place and hit and any(re.match(in_place, a) for a in argv[1:]):
            return f"{name} -i on a file in the human repo"
        if name in ("awk", "gawk") and hit and {"inplace", "-iinplace", "--include=inplace"} & set(argv):
            return f"{name} -i inplace on a file in the human repo"
        if name in WRITERS and hit:
            return f"{name} on a path in the human repo"
        target = option_value(argv, "-t", "--target-directory") if name in ("cp", "install") else None
        dest = target or (ops[-1] if len(ops) > 1 else None)
        if name in ("cp", "install", "rsync") and dest and under(dest, cwd):
            return f"{name} into the human repo"
        extract = "-x" in argv or any(a in ("--extract", "--get") or re.match(r"^-?[a-zA-Z]*x", a) for a in argv[1:2])
        if name == "tar" and extract and under(option_value(argv, "-C", "--directory") or ".", cwd):
            return "tar extract into the human repo"
        if name == "unzip" and not {"-l", "-t", "-v", "-Z"} & set(argv) and under(option_value(argv, "-d") or ".", cwd):
            return "unzip into the human repo"
        if name == "patch" and "--dry-run" not in argv and \
                (under(option_value(argv, "-d", "--directory") or ".", cwd) or hit):
            return "patch in the human repo"
        if name == "dd" and any(a.startswith("of=") and under(a[3:], cwd) for a in argv[1:]):
            return "dd of= into the human repo"
        return git_problem(argv, cwd, hr) if name == "git" else None
    return check


def deletable(target, cwd):
    """None when target is a literal path inside session scratch or .run/tmp, .run/out; else the reason."""
    if UNSAFE.search(target):
        return f"a path built from a variable, glob, ~ or substitution: {target}"
    path = resolve(target, cwd)
    if path is None:
        return f"relative path {target} after a cd this hook cannot follow"
    rel = os.path.relpath(path, ROOT).split(os.sep)
    if (len(rel) >= 3 and rel[0] == "sessions" and rel[1] not in ("..", ".") and rel[2] == "scratch") or \
            (len(rel) >= 2 and rel[0] == ".run" and rel[1] in ("tmp", "out")):
        return None
    return f"{target} ({path}), outside session scratch and .run/tmp, .run/out"


def rm_check(argv, _writes, cwd):
    if not argv:
        return None
    name, ops, targets = os.path.basename(argv[0]), operands(argv), []
    if name == "rm" and any(a == "--recursive" or re.match(r"^-[a-zA-Z]*[rR]", a) for a in argv[1:]):
        targets = ops
    elif name == "xargs" and any(os.path.basename(a) == "rm" for a in argv[1:]):
        return "xargs rm takes its targets from stdin, which this hook cannot see"
    elif name == "find" and ("-delete" in argv or any(a in ("-exec", "-execdir", "-ok") and i + 1 < len(argv)
                                                       and os.path.basename(argv[i + 1]) == "rm"
                                                       for i, a in enumerate(argv))):
        targets = [a for a in argv[1:] if not a.startswith(("-", "(", "!"))][:1] or ["."]
    elif name == "rsync" and any(a == "--del" or a.startswith("--delete") for a in argv) and ops:
        targets = ops[-1:]
    elif name == "git":
        rest, places = git_parse(argv, cwd)
        if rest and rest[0] == "clean" and not any(a == "--dry-run" or re.match(r"^-[a-zA-Z]*n", a) for a in rest[1:]):
            if places[0] is None:
                return "git clean after a cd or -C this hook cannot follow"
            targets = [os.path.join(places[0], t) for t in operands(rest)] or [places[0]]
    return next((f"recursive delete of {why}" for t in targets if (why := deletable(t, cwd))), None)


def human_repo():
    value = os.environ.get("HUMAN_REPO")
    if value is None:
        try:
            with open(os.path.join(ROOT, "project.env")) as f:
                value = next((m.group(1).strip().strip("'\"") for line in f
                              if (m := re.match(r"^HUMAN_REPO=(.*)$", line.strip()))), None)
        except OSError:
            value = None
    if not value:
        return None
    value = value.replace("$HOME", os.environ.get("HOME", ""))
    return os.path.realpath(value if os.path.isabs(value) else os.path.join(ROOT, value))


def judge(mode, data):
    tool_input, cwd = data.get("tool_input"), data.get("cwd") or os.getcwd()
    if not isinstance(tool_input, dict):
        return f"{mode}: refused: the hook input has no tool_input; failing closed"
    if mode == "no-rm-rf":
        why = walk(tool_input.get("command") or "", cwd, rm_check, lambda t, _env: t)
        return why and (f"no-rm-rf: refused: {why}. Delete only literal paths inside {ROOT}/sessions/<session>/scratch/"
                        " or .run/tmp/, .run/out/ (scripts/clean-tmp.sh clears .run); mktemp -d a fresh dir instead.")
    hr = human_repo()
    if not hr:
        return "guard-human-repo: refused: HUMAN_REPO is unset or empty (environment or project.env); failing closed"
    tool = data.get("tool_name") or ""
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        why = f"{tool} on {target}" if target and inside(resolve(target, cwd), hr) else None
    else:
        def expand(token, env):
            for k, v in {**env, "HUMAN_REPO": hr, "HOME": os.environ.get("HOME", "")}.items():
                token = re.sub(r"\$\{?" + re.escape(k) + r"\}?(?!\w)", lambda _m, v=v: v, token)
            return os.path.expanduser(token)
        why = walk(tool_input.get("command") or "", cwd, human_check(hr), expand)
    return why and (f"guard-human-repo: refused: {why}. {hr} is the human's (HUMAN_REPO): read, build and test it, "
                    "never write it. Copy what you need into the session's scratch/ and edit the copy.")


def main(mode):
    try:
        data = json.loads(sys.stdin.read())
    except ValueError:
        data = None
    if not isinstance(data, dict):
        why = f"{mode}: refused: the hook input on stdin is empty or not a JSON object; failing closed"
    else:
        why = judge(mode, data)
    if why:
        print(why, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
