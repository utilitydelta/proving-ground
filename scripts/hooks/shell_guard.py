#!/usr/bin/env python3
"""Claude Code PreToolUse guards, shared by the hook wrappers in this folder.

  shell_guard.py no-rm-rf        Bash: refuse recursive deletes outside session scratch and .run/tmp, .run/out
  shell_guard.py human-repo      Edit, Write, NotebookEdit, Bash: refuse writes under HUMAN_REPO

no-rm-rf judges, in any repo: rm -r, find -delete or -exec rm, xargs rm, rsync --delete (its destination), python
rmtree( with a literal or unreadable target (raw text, best effort), and git clean without -n/--dry-run (its paths,
else the directory it runs in). Each target must resolve inside sessions/<s>/scratch, .run/tmp or .run/out.

human-repo refuses, when the working directory, a -C/--prefix/--dir/--directory/--manifest-path/-p/--project/-f
value or an operand resolves into HUMAN_REPO:
  - writes: redirects, tee, sed/perl -i, mv, cp/rsync/install into it, rm, touch, mkdir, chmod, ln, dd of=
  - git: anything but reads (GIT_READ, branch/tag/stash/remote/worktree/submodule listing, config get forms,
    reflog show, archive without -o into it), with every global option peeled (-C, -c, --git-dir, --work-tree,
    --no-pager, -P, ...)
  - package managers: npm/pnpm/yarn/bun install, add, ci, update, remove...; pip install -e or of a tree path;
    cargo add/update/remove/fmt/fix
  - formatters and fixers: black, isort, rustfmt (without --check), gofmt/goimports -w, clang-format -i, prettier
    --write, eslint/ruff --fix, ruff format, cargo/go/dotnet fmt|format, any --write or --fix
  - builds that write into the tree: make, tsc without --noEmit, dotnet build/run/test/publish/pack/restore, go build
    without -o elsewhere, go generate/get/mod tidy, cargo build/test/run/check/clippy/bench/doc without
    CARGO_TARGET_DIR (env, export, or scripts/run.sh) or --target-dir outside the human repo
  - Python on the tree (python, pytest) unless -B, PYTHONDONTWRITEBYTECODE or PYTHONPYCACHEPREFIX outside the repo
    is set (scripts/run.sh sets the prefix); pytest also needs -p no:cacheprovider
Allowed, since they write nothing in the tree: go test and go vet (cache in the user cache dir), cargo with an outside
target dir, Python with the prefix, every git read. Out of scope: `node -e`, `npm test`/`npm run` and any script
the project runs (they can write anything), and paths built from variables other than $HUMAN_REPO and $HOME.

stdin is the hook's JSON ({"tool_name", "tool_input", "cwd"}). Exit 0 allows; exit 2 blocks, and Claude Code shows the
agent the reason printed on stderr.

These catch slips, not adversaries. The command is tokenised with shlex, split at ; && || | & ( ) and newlines, with
wrappers (sudo, env, nice, timeout, nohup, VAR=x, scripts/run.sh) peeled off, `export VAR=x` remembered, and `bash -c`, `sh -c` and `eval` strings checked
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


ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.S)
# Wrappers that export a build-output policy to the command they run. scripts/run.sh sets CARGO_TARGET_DIR and
# PYTHONPYCACHEPREFIX under .run/build/ unless already set.
RUN_SH_ENV = {"CARGO_TARGET_DIR": ".run/build/cargo", "PYTHONPYCACHEPREFIX": ".run/build/pycache"}


def unwrap(argv, env=None):
    """Peel keywords, VAR=x prefixes and wrapper commands until the real command is first. Returns (argv, env): env
    holds the VAR=x prefixes and what a peeled scripts/run.sh exports, on top of the env passed in."""
    env = dict(env or {})
    while argv:
        name = os.path.basename(argv[0])
        m = ASSIGN.match(argv[0])
        if argv[0] in KEYWORDS:
            argv = argv[1:]
        elif m:
            env[m.group(1)] = m.group(2)
            argv = argv[1:]
        elif name in ("sudo", "command", "builtin", "nohup", "stdbuf", "ionice"):
            argv = drop_options(argv[1:], ("-u", "-g", "-c", "-n"))
        elif name == "env":
            argv = drop_options(argv[1:], ("-u", "-C", "-S"))
            while argv and ASSIGN.match(argv[0]):
                k, v = ASSIGN.match(argv[0]).groups()
                env[k] = v
                argv = argv[1:]
        elif name == "nice":
            argv = drop_options(argv[1:], ("-n",))
        elif name == "timeout":
            argv = drop_options(argv[1:], ("-k", "-s"))[1:]
        elif name == "run.sh":
            for k, v in RUN_SH_ENV.items():
                env.setdefault(k, os.path.join(ROOT, v))
            argv = drop_options(argv[1:], ("-t", "-l"))
        else:
            return argv, env
    return argv, env


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


def walk(command, cwd, check, expand=lambda t: t, env=None):
    """Run check(argv, writes, cwd, env) on every simple command, following cd and export and recursing into nested
    strings. check returns a refusal reason or None; walk returns the first reason. cwd None means unknown."""
    env = dict(env or {})
    for cmd in commands(command):
        argv, cmd_env = unwrap(cmd.argv, env)
        if not argv and cmd.argv and all(ASSIGN.match(a) for a in cmd.argv):
            env = cmd_env
            continue
        if argv and argv[0] == "export":
            for a in argv[1:]:
                m = ASSIGN.match(a)
                if m:
                    env[m.group(1)] = m.group(2)
            continue
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
                why = walk(inner, cwd, check, expand, cmd_env)
                if why:
                    return why
                continue
        why = check(argv, cmd.writes, cwd, cmd_env)
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


GIT_GLOBAL_FLAGS = {"--no-pager", "-P", "--paginate", "-p", "--no-optional-locks", "--bare", "--no-replace-objects",
                    "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs",
                    "--no-advice", "--no-lazy-fetch"}
GIT_GLOBAL_VALUED = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env",
                     "--super-prefix"}


def git_parse(argv, cwd):
    """(subcommand args, places) for a git argv: every global option peeled. places are the resolved directories
    the command acts on (cwd after each -C, --work-tree, --git-dir); None in places means unknown."""
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


def rmtree_problems(command, cwd):
    """Best effort over the raw text: every rmtree( call with a literal target outside scratch, or a non-literal one."""
    for m in re.finditer(r"rmtree\(\s*([^,)]*)", command):
        arg = m.group(1).strip()
        lit = re.fullmatch(r"(?:r?)(['\"])(.*)\1", arg)
        if not lit:
            return f"rmtree of a target this hook cannot read ({arg or '?'}); use a literal path under scratch"
        why = target_problem(lit.group(2), cwd)
        if why:
            return f"rmtree: {why}"
    return None


def check_rm(argv, writes, cwd, env=None):
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
    if name == "rsync" and any(a == "--del" or a.startswith("--delete") for a in argv[1:]):
        paths = [a for a in argv[1:] if not a.startswith("-")]
        if paths:
            why = target_problem(paths[-1], cwd)
            if why:
                return f"rsync --delete: {why}"
    if name.startswith("python") and "-c" in argv and "rmtree" in " ".join(argv):
        why = rmtree_problems(" ".join(argv), cwd)
        if why:
            return why
    if name == "git":
        rest, places = git_parse(argv, cwd)
        if rest and rest[0] == "clean":
            args = rest[1:]
            if any(a in ("-n", "--dry-run") or re.match(r"^-[a-zA-Z]*n", a) for a in args):
                return None
            paths = [a for a in args if not a.startswith("-")]
            where = places[0]
            if where is None:
                return "git clean after a cd or -C this hook cannot follow"
            for t in paths or ["."]:
                why = target_problem(t if os.path.isabs(t) else os.path.join(where, t), where)
                if why:
                    return f"git clean deletes untracked files (session records, scratch, .run): {why}; dry-run with -n"
    return None


def no_rm_rf(data):
    command = (data.get("tool_input") or {}).get("command") or ""
    cwd = data.get("cwd") or os.getcwd()
    why = walk(command, cwd, check_rm)
    if not why and "rmtree" in command and "python" in command:
        why = rmtree_problems(command, cwd)
    if why:
        return (f"no-rm-rf: refused: {why}. Allowed: rm -r, git clean, rsync --delete or rmtree on a literal path "
                f"that resolves inside {ROOT}/sessions/<session>/scratch/ or {ROOT}/.run/tmp/ or .run/out/ "
                "(scripts/clean-tmp.sh clears .run). For a fresh directory, mktemp -d there instead of deleting one; "
                "for build output, the build tool's own clean. This hook catches slips, not adversaries.")
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
            "describe", "shortlog", "rev-list", "for-each-ref", "name-rev", "merge-base", "help", "version",
            "whatchanged", "show-ref", "count-objects", "check-ignore", "var", "show-branch", "range-diff",
            "cherry", "ls-remote", "verify-commit", "verify-tag", "fsck"}
GIT_READ_ARGS = {"branch": {"--list", "-l", "-a", "-r", "-v", "-vv", "--show-current", "--all", "--remotes",
                            "--contains", "--merged", "--no-merged"},
                 "stash": {"list", "show"}, "worktree": {"list"}, "remote": {"-v", "show", "get-url"},
                 "tag": {"-l", "--list", "-v", "--verify", "--contains", "--points-at"},
                 "submodule": {"status", "summary"}}
GIT_CONFIG_GET = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l", "get", "list"}
GIT_CONFIG_WRITE = {"--unset", "--unset-all", "--add", "--replace-all", "--rename-section", "--remove-section",
                    "-e", "--edit", "set", "unset", "rename-section", "remove-section", "edit"}

# Options whose value names the directory or project a build tool acts on.
PATH_OPTS = {"-C", "--prefix", "--dir", "--directory", "--manifest-path", "-p", "--project", "--cwd", "-f", "--file"}
PACKAGE_MANAGERS = {"npm", "pnpm", "yarn", "bun"}
PACKAGE_WRITES = {"install", "i", "add", "ci", "update", "up", "upgrade", "remove", "rm", "uninstall", "un", "link",
                  "dedupe", "prune", "audit"}
CARGO_BUILDS = {"build", "b", "test", "t", "run", "r", "check", "c", "clippy", "bench", "doc", "rustc", "install"}
CARGO_WRITES = {"add", "update", "remove", "rm", "fix", "generate-lockfile", "vendor", "init", "new"}
DOTNET_WRITES = {"build", "run", "test", "publish", "pack", "restore", "clean", "format", "add", "new"}
GO_WRITES = {"generate", "get", "fmt", "fix"}
# Rewrite files in place unless told to only check.
FORMATTERS = {"black": {"--check", "--diff"}, "isort": {"--check", "--check-only", "--diff"}, "rustfmt": {"--check"}}
# Rewrite files in place only with one of these flags.
IN_PLACE = {"gofmt": {"-w"}, "goimports": {"-w"}, "clang-format": {"-i"}, "prettier": {"--write", "-w"},
            "autopep8": {"-i", "--in-place"}, "yapf": {"-i", "--in-place"}, "eslint": {"--fix"},
            "ruff": {"--fix", "format"}}


def expand(token, hr):
    token = re.sub(r"\$\{?HUMAN_REPO\}?", hr, token)
    token = re.sub(r"\$\{?HOME\}?", os.environ.get("HOME", ""), token)
    return os.path.expanduser(token)


def git_problem(argv, cwd, under):
    rest, places = git_parse(argv, cwd)
    hit = [p for p in places if p is not None and under(p)]
    if not rest or not hit:
        return None
    sub, args = rest[0], rest[1:]
    where = hit[0]
    if sub in GIT_READ:
        return None
    if sub == "archive":
        outs = [a.split("=", 1)[1] for a in args if a.startswith("--output=")]
        outs += [args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-o", "--output")]
        return f"git archive -o into the human repo ({where})" if any(under(resolve(o, cwd)) for o in outs) else None
    if sub == "reflog":
        return f"git reflog {args[0]} in the human repo ({where})" if args and args[0] in ("expire", "delete") else None
    if sub == "config":
        positional = [a for a in args if not a.startswith("-")]
        if not any(a in GIT_CONFIG_WRITE for a in args) and \
                (any(a in GIT_CONFIG_GET for a in args) or len(positional) == 1):
            return None
        return f"git config write in the human repo ({where})"
    allowed = GIT_READ_ARGS.get(sub)
    if allowed is not None and (not args and sub in ("branch", "remote", "tag") or any(a in allowed for a in args)):
        return None
    return f"git {sub} in the human repo ({where})"


def option_values(argv, names):
    """Values of the options in names, given as `-x v`, `--x v` or `--x=v`."""
    out = []
    for i, a in enumerate(argv):
        if a in names and i + 1 < len(argv):
            out.append(argv[i + 1])
        elif a.startswith("--") and "=" in a and a.split("=", 1)[0] in names:
            out.append(a.split("=", 1)[1])
    return out


def operands(argv):
    """Positional arguments and the values of --opt=value, as candidate paths."""
    out = []
    for a in argv[1:]:
        if a.startswith("--") and "=" in a:
            out.append(a.split("=", 1)[1])
        elif not a.startswith("-"):
            out.append(a)
    return out


def first_word(argv):
    """The subcommand: the first operand that is not the value of a PATH_OPTS option."""
    skip = False
    for a in argv[1:]:
        if skip:
            skip = False
        elif a in PATH_OPTS:
            skip = True
        elif not a.startswith("-"):
            return a
    return None


def build_problem(name, argv, cwd, env, under):
    """A build, install, format or interpreter run that would write into the human tree, or None. Judged on the
    working directory, the PATH_OPTS values and the operands; env is the command's own environment on top of the
    hook's."""
    def touches(candidates):
        return any(under(resolve(c, cwd)) for c in candidates if c and not UNSAFE.search(c))

    here = [cwd] if cwd else []
    dirs = here + option_values(argv, PATH_OPTS)
    sub = first_word(argv)

    def set_outside(var):
        value = env.get(var) or os.environ.get(var)
        return bool(value) and not under(resolve(value, cwd) or "")

    if name in PACKAGE_MANAGERS and (sub in PACKAGE_WRITES or (sub is None and name in ("yarn", "pnpm", "bun"))) \
            and touches(dirs):
        return f"{name} {sub or 'install'} writes node_modules and the lockfile; run it on a snapshot copy"
    if name in ("pip", "pip3") or (name.startswith("python") and argv[1:3] == ["-m", "pip"]):
        rest = argv[3:] if name.startswith("python") else argv[1:]
        if rest and rest[0] == "install" and (touches(option_values(rest, {"-e", "--editable"}))
                                              or touches([a for a in rest[1:] if a.startswith((".", "/"))])):
            return "pip install of the human tree builds in place (build/, *.egg-info); install from a snapshot copy"
        if rest and rest[0] == "install":
            return None
    if name == "cargo":
        if sub in CARGO_WRITES and touches(dirs):
            return f"cargo {sub} rewrites files in the human tree"
        if sub in CARGO_BUILDS and touches(dirs):
            target = option_values(argv, {"--target-dir"})
            ok = (not under(resolve(target[-1], cwd) or "")) if target else set_outside("CARGO_TARGET_DIR")
            if not ok:
                return (f"cargo {sub} without CARGO_TARGET_DIR or --target-dir outside the human repo writes "
                        "target/ there; run it through scripts/run.sh")
    if name == "dotnet" and sub in DOTNET_WRITES and touches(dirs + operands(argv)[1:]):
        if sub == "format" and "--verify-no-changes" in argv:
            return None
        return f"dotnet {sub} writes obj/ and bin/ (or sources) in the human tree; run it on a snapshot copy"
    if name == "go" and touches(here + operands(argv)[1:]):
        if sub in GO_WRITES or argv[1:3] == ["mod", "tidy"]:
            return f"go {sub} rewrites files in the human tree"
        if sub == "build":
            out = option_values(argv, {"-o"})
            if not out or under(resolve(out[-1], cwd) or ""):
                return "go build without -o outside the human repo drops a binary there"
    if name in ("make", "gmake") and touches(dirs):
        return "make in the human tree writes build output there; run it on a snapshot copy"
    if name == "tsc" and "--noEmit" not in argv and touches(dirs):
        return "tsc without --noEmit writes .js beside the human sources"
    if name in FORMATTERS and not any(a in FORMATTERS[name] for a in argv) and touches(here + operands(argv)):
        return f"{name} rewrites files in the human tree; pass --check, or format a scratch copy"
    if name in IN_PLACE and any(a in IN_PLACE[name] for a in argv) and touches(here + operands(argv)):
        return f"{name} {' '.join(a for a in argv if a in IN_PLACE[name])} rewrites files in the human tree"
    if sub in ("fmt", "format") and name in ("cargo", "go", "dotnet", "ruff", "deno", "zig", "terraform") \
            and touches(dirs + operands(argv)[1:]) and not any(a in ("--check", "--verify-no-changes") for a in argv):
        return f"{name} {sub} rewrites files in the human tree; pass --check"
    if any(a in ("--write", "--fix") for a in argv) and touches(here + operands(argv)):
        return f"{name} --write/--fix rewrites files in the human tree"
    python = name.startswith("python") or name in ("pytest", "py.test")
    if python and touches(here + operands(argv)):
        if not ("-B" in argv or env.get("PYTHONDONTWRITEBYTECODE") or os.environ.get("PYTHONDONTWRITEBYTECODE")
                or set_outside("PYTHONPYCACHEPREFIX")):
            return ("Python on the human tree writes __pycache__ beside its sources; run it through scripts/run.sh "
                    "(PYTHONPYCACHEPREFIX) or set PYTHONPYCACHEPREFIX outside the repo")
        is_pytest = name in ("pytest", "py.test") or argv[1:3] == ["-m", "pytest"]
        if is_pytest and not any(a == "no:cacheprovider" or a == "-pno:cacheprovider" for a in argv):
            return "pytest writes .pytest_cache in the human tree; pass -p no:cacheprovider"
    return None


def check_human(hr):
    def under(path):
        return path is not None and inside(path, hr)

    def check(argv, writes, cwd, env=None):
        env = env or {}
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
        return build_problem(name, argv, cwd, {k: expand(v, hr) for k, v in env.items()}, under)
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
