#!/usr/bin/env python3
"""Claude Code PreToolUse guards, shared by the hook wrappers in this folder.

  shell_guard.py no-rm-rf        Bash: refuse recursive deletes outside session scratch and .run/tmp, .run/out
  shell_guard.py human-repo      Edit, Write, NotebookEdit, Bash: refuse writes under HUMAN_REPO

stdin is the hook's JSON ({"tool_name", "tool_input", "cwd"}). Exit 0 allows; exit 2 blocks, and Claude Code shows the
agent the reason printed on stderr.

These catch slips, not adversaries. The command is tokenised with shlex, split at ; && || | & ( ) and newlines, with
wrappers (sudo, env, nice, timeout, nohup, VAR=x) peeled off and `bash -c`, `sh -c` and `eval` strings checked
recursively; `cd <literal>` moves the working directory for the commands after it. Variables are not expanded, except
$HUMAN_REPO, $HOME and ~ for the human-repo guard. A heredoc body is read as commands, so a script written through
`cat <<EOF` that contains a refused command is refused too: write it with the Write tool instead.

The project root is this file's ../..; HUMAN_REPO comes from the environment, else project.env, relative to the root.
"""
import json
import os
import re
import shlex
import sys

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SEPARATORS = {";", ";;", "&&", "||", "|", "|&", "&", "(", ")"}
KEYWORDS = {"{", "}", "!", "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "time", "exec"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
UNSAFE = re.compile(r"[$`*?\[{~]")


class Command:
    """One simple command: its argv and its output redirection targets."""

    def __init__(self, argv, writes):
        self.argv, self.writes = argv, writes


def tokens(command):
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.replace("\n", " ; ").split()


def commands(command):
    """Split a command line into simple commands. Redirections leave argv; `>` and `>>` targets are kept as writes."""
    out, argv, writes, skip = [], [], [], False
    toks = tokens(command)
    for i, tok in enumerate(toks):
        if skip:
            skip = False
            continue
        if tok and set(tok) <= set("();<>|&"):
            if "<" in tok or ">" in tok:
                if argv and argv[-1].isdigit():
                    argv.pop()
                if not tok.endswith("&") and i + 1 < len(toks):
                    if ">" in tok:
                        writes.append(toks[i + 1])
                    skip = True
                elif tok.endswith("&"):
                    skip = True
                continue
            if argv or writes:
                out.append(Command(argv, writes))
            argv, writes = [], []
            continue
        argv.append(tok)
    if argv or writes:
        out.append(Command(argv, writes))
    return out


def drop_options(argv, takes_value=()):
    """argv without its leading options; options in takes_value consume the next token."""
    i = 0
    while i < len(argv) and argv[i].startswith("-") and argv[i] != "--":
        i += 2 if argv[i] in takes_value else 1
    if i < len(argv) and argv[i] == "--":
        i += 1
    return argv[i:]


def unwrap(argv):
    """Peel keywords, VAR=x prefixes and wrapper commands until the real command is first."""
    while argv:
        name = os.path.basename(argv[0])
        if argv[0] in KEYWORDS or re.match(r"^[A-Za-z_]\w*=", argv[0]):
            argv = argv[1:]
        elif name in ("sudo", "command", "builtin", "nohup", "stdbuf", "ionice"):
            argv = drop_options(argv[1:], ("-u", "-g", "-c", "-n"))
        elif name == "env":
            argv = drop_options(argv[1:], ("-u", "-C", "-S"))
            while argv and re.match(r"^[A-Za-z_]\w*=", argv[0]):
                argv = argv[1:]
        elif name == "nice":
            argv = drop_options(argv[1:], ("-n",))
        elif name == "timeout":
            argv = drop_options(argv[1:], ("-k", "-s"))[1:]
        else:
            return argv
    return argv


def nested(argv):
    """The command string a shell -c or eval would run, or None."""
    name = os.path.basename(argv[0])
    if name == "eval":
        return " ".join(argv[1:])
    if name in SHELLS:
        for i, a in enumerate(argv[1:], 1):
            if re.match(r"^-[a-zA-Z]*c[a-zA-Z]*$", a) and i + 1 < len(argv):
                return argv[i + 1]
    return None


def walk(command, cwd, check, expand=lambda t: t):
    """Run check(argv, writes, cwd) on every simple command, following cd and recursing into nested strings.
    check returns a refusal reason or None; walk returns the first reason. cwd None means unknown."""
    for cmd in commands(command):
        argv = unwrap(cmd.argv)
        if argv and argv[0] in ("cd", "pushd"):
            target = expand(argv[1]) if len(argv) > 1 else None
            if target is None or UNSAFE.search(target):
                cwd = None
            elif os.path.isabs(target):
                cwd = target
            elif cwd:
                cwd = os.path.join(cwd, target)
            continue
        if argv:
            inner = nested(argv)
            if inner is not None:
                why = walk(inner, cwd, check, expand)
                if why:
                    return why
                continue
        why = check(argv, cmd.writes, cwd)
        if why:
            return why
    return None


def resolve(path, cwd):
    """Absolute real path, or None when it is relative and the working directory is unknown."""
    if os.path.isabs(path):
        return os.path.realpath(path)
    return os.path.realpath(os.path.join(cwd, path)) if cwd else None


def inside(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


# --- no-rm-rf ----------------------------------------------------------------------------------------------------

def deletable(path):
    """Inside <ROOT>/sessions/<s>/scratch, <ROOT>/.run/tmp or <ROOT>/.run/out."""
    rel = os.path.relpath(path, ROOT).split(os.sep)
    if len(rel) >= 3 and rel[0] == "sessions" and rel[2] == "scratch" and rel[1] not in ("..", "."):
        return True
    return len(rel) >= 2 and rel[0] == ".run" and rel[1] in ("tmp", "out")


def target_problem(target, cwd):
    if UNSAFE.search(target):
        return f"recursive delete of a path built from a variable, glob, ~ or substitution: {target}"
    path = resolve(target, cwd)
    if path is None:
        return f"recursive delete of relative path {target} after a cd this hook cannot follow"
    if not deletable(path):
        return f"recursive delete outside session scratch and .run/tmp: {target} ({path})"
    return None


def recursive_rm(argv):
    flags = []
    for a in argv[1:]:
        if a == "--":
            break
        if a.startswith("-"):
            flags.append(a)
    return any(f == "--recursive" or (not f.startswith("--") and re.search("[rR]", f)) for f in flags)


def rm_targets(argv):
    out, after_dashes = [], False
    for a in argv[1:]:
        if a == "--" and not after_dashes:
            after_dashes = True
        elif after_dashes or not a.startswith("-"):
            out.append(a)
    return out


def find_starts(argv):
    rest = drop_options(argv[1:], ())
    starts = []
    for a in rest:
        if a.startswith("-") or a in ("(", "!"):
            break
        starts.append(a)
    return starts or ["."]


def check_rm(argv, writes, cwd):
    if not argv:
        return None
    name = os.path.basename(argv[0])
    if name == "rm" and recursive_rm(argv):
        for t in rm_targets(argv):
            why = target_problem(t, cwd)
            if why:
                return why
    if name == "xargs" and any(os.path.basename(a) == "rm" for a in argv[1:]):
        return "xargs rm takes its targets from stdin, which this hook cannot see; list literal paths"
    if name == "find":
        execs_rm = any(a in ("-exec", "-execdir", "-ok") and i + 1 < len(argv) and os.path.basename(argv[i + 1]) == "rm"
                       for i, a in enumerate(argv))
        if "-delete" in argv or execs_rm:
            for t in find_starts(argv):
                why = target_problem(t, cwd)
                if why:
                    return f"find -delete/-exec rm: {why}"
    if name == "git":
        rest = argv[1:]
        while rest and rest[0] in ("-C", "-c"):
            rest = rest[2:]
        if rest and rest[0] == "clean" and any(re.match(r"^-[a-zA-Z]*[xX]", a) for a in rest[1:]):
            return "git clean -x/-X deletes ignored files too: session scratch, .run and every build cache"
    return None


def no_rm_rf(data):
    command = (data.get("tool_input") or {}).get("command") or ""
    why = walk(command, data.get("cwd") or os.getcwd(), check_rm)
    if why:
        return (f"no-rm-rf: refused: {why}. Allowed: rm -r on a literal path that resolves inside {ROOT}/sessions/"
                f"<session>/scratch/ or {ROOT}/.run/tmp/ (scripts/clean-tmp.sh clears .run/tmp and .run/out). For a "
                "fresh directory, mktemp -d there instead of deleting one; for build output, the build tool's own "
                "clean. This hook catches slips, not adversaries.")
    return None


# --- human repo --------------------------------------------------------------------------------------------------

def human_repo():
    value = os.environ.get("HUMAN_REPO")
    if value is None:
        try:
            with open(os.path.join(ROOT, "project.env")) as f:
                for line in f:
                    m = re.match(r"^HUMAN_REPO=(.*)$", line.strip())
                    if m:
                        value = m.group(1).strip().strip("'\"")
        except OSError:
            return None
    if not value:
        return None
    value = value.replace("$HOME", os.environ.get("HOME", ""))
    return os.path.realpath(value if os.path.isabs(value) else os.path.join(ROOT, value))


WRITERS = {"rm", "rmdir", "mv", "touch", "mkdir", "chmod", "chown", "chgrp", "truncate", "tee", "ln", "unlink", "shred"}
DEST_LAST = {"cp", "install", "rsync"}
GIT_READ = {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "blame", "grep", "cat-file",
            "describe", "shortlog", "rev-list", "archive", "for-each-ref", "name-rev", "merge-base", "help", "version",
            "whatchanged", "show-ref", "count-objects", "check-ignore", "var"}
GIT_READ_ARGS = {"branch": {"--list", "-l", "-a", "-r", "-v", "-vv", "--show-current", "--all", "--remotes"},
                 "stash": {"list", "show"}, "worktree": {"list"}, "remote": {"-v", "show", "get-url"},
                 "config": {"--get", "--get-all", "--get-regexp", "--list", "-l"}}


def expand(token, hr):
    token = re.sub(r"\$\{?HUMAN_REPO\}?", hr, token)
    token = re.sub(r"\$\{?HOME\}?", os.environ.get("HOME", ""), token)
    return os.path.expanduser(token)


def git_problem(argv, cwd, under):
    rest, where = argv[1:], cwd
    while rest and (rest[0] in ("-C", "-c") or rest[0].startswith(("--git-dir=", "--work-tree=", "-c"))):
        if rest[0] == "-C" and len(rest) > 1:
            where = resolve(rest[1], where)
        rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
    if not rest or where is None or not under(where):
        return None
    sub, args = rest[0], rest[1:]
    if sub in GIT_READ:
        return None
    allowed = GIT_READ_ARGS.get(sub)
    if allowed is not None and (not args and sub in ("branch", "remote") or any(a in allowed for a in args)):
        return None
    return f"git {sub} in the human repo ({where})"


def check_human(hr):
    def under(path):
        return path is not None and inside(path, hr)

    def check(argv, writes, cwd):
        for w in writes:
            w = expand(w, hr)
            if not w.startswith("/dev/") and under(resolve(w, cwd)):
                return f"redirect into the human repo: > {w}"
        if not argv:
            return None
        argv = [expand(a, hr) for a in argv]
        name = os.path.basename(argv[0])
        paths = [a for a in argv[1:] if not a.startswith("-")]
        if name in WRITERS and any(under(resolve(p, cwd)) for p in paths):
            return f"{name} on a path in the human repo"
        if name in DEST_LAST and paths and under(resolve(paths[-1], cwd)):
            return f"{name} into the human repo"
        if name in ("sed", "perl") and any(re.match(r"^(-i|--in-place|-[a-zA-Z]*i)", a) for a in argv[1:]) \
                and any(under(resolve(p, cwd)) for p in paths):
            return f"{name} -i on a file in the human repo"
        if name == "dd" and any(a.startswith("of=") and under(resolve(a[3:], cwd)) for a in argv[1:]):
            return "dd of= into the human repo"
        if name == "git":
            return git_problem(argv, cwd, under)
        return None
    return check


def human_repo_guard(data):
    hr = human_repo()
    if not hr:
        return None
    tool = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    why = None
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if target and inside(resolve(target, cwd), hr):
            why = f"{tool} on {target}"
    elif tool == "Bash":
        why = walk(tool_input.get("command") or "", cwd, check_human(hr), lambda t: expand(t, hr))
    if why:
        return (f"guard-human-repo: refused: {why}. {hr} is the human's (HUMAN_REPO): agents read, build and test "
                "it, never write it. Copy what you need into the session's scratch/ and edit the copy. This hook "
                "catches slips, not adversaries.")
    return None


def main(mode):
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    why = {"no-rm-rf": no_rm_rf, "human-repo": human_repo_guard}[mode](data)
    if why:
        print(why, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
