"""PreToolUse guard for agents (spec §10): exit 2 with a reason on stderr blocks the tool call.

Blocks: reading `.env*` (not `.env.example`) or anything under `.bootstrap/` (paths, globs, quoting
tricks, recursive grep over the repo, `docker compose config`); a realistic live Stripe key;
`git push` to main/master (explicitly, via `--all`/`--mirror`, or a bare push while on main);
force pushes; and `rm -r`/`rm -rf` of anything outside this repo (or the repo itself, or paths only
known at run time such as `xargs rm -rf`); Terraform writes (`apply`, `destroy`, `import`, `state`,
`taint`, `untaint`, `force-unlock`); `make infra-*` other than `infra-plan` and `infra-doctor`;
and `aws secretsmanager get-secret-value`. Commands are tokenized like a shell would, wrappers
(`sudo`, `env`, `xargs`, `bash -c`, subshells, `/bin/rm`) are unwrapped. Input it cannot read is
blocked too: a guard that fails open guards nothing.

It is a seatbelt for honest mistakes, not a sandbox: anything that computes a path at run time
(a script, `python -c`) is out of its reach. The deny rules in settings.json back it up.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # this file lives in <repo>/.claude/hooks/
PATH_KEYS = ("file_path", "path", "notebook_path")
LIVE_KEY = re.compile(r"[sr]k_live_[0-9A-Za-z]{20,}")  # real keys are long; `sk_live_x` placeholders pass
SECRET_PATH = re.compile(
    r"(^|[\s/'\"=<>:;|&(){},])(\.env(\.(?!example\b)[\w.-]+)?|\.bootstrap)(?=$|[\s/'\";|&)<>{},])"
)
# Names a glob must not be able to match (a sample of `.env.*`, and the bootstrap state).
SECRET_NAMES = [".env", ".env.local", ".env.production", ".env.test", ".bootstrap"]
SECRET_FILES = [".env", ".env.local", ".bootstrap/backend.pat", "x/.env", "x/.bootstrap/ids.env"]
GLOB_CHARS = set("*?[")
OPERATORS = {"&&", "||", ";", "|", "&", "|&", ";;", "(", ")"}
WRAPPERS = {"sudo", "command", "exec", "nohup", "time", "nice", "builtin", "doas"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
PROTECTED = {"main", "master"}
PUSH_HINT = "push your branch and open a PR"
GREP_HINT = "use `git grep` or `rg` (they skip the git-ignored .env and .bootstrap/), or the Grep tool"


class Blocked(Exception):
    pass


def strings(value: object) -> list[str]:
    """Every string inside a tool input (MultiEdit nests its edits in a list of dicts)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


def is_secret_name(name: str) -> bool:
    return name in {".env", ".bootstrap"} or (name.startswith(".env.") and name != ".env.example")


def check_path(path: str) -> None:
    parts = Path(path).parts
    if ".bootstrap" in parts:
        raise Blocked("reading .bootstrap/ (tokens and ids) is not allowed")
    if parts and is_secret_name(parts[-1]):
        raise Blocked("reading .env is not allowed; .env.example lists the names")


def check_glob(pattern: str) -> None:
    """The Grep tool's `glob`: an explicit glob overrides ripgrep's ignore rules."""
    if any(fnmatchcase(f, p) for p in (pattern, f"**/{pattern}") for f in SECRET_FILES):
        raise Blocked(f"the glob {pattern!r} can match .env or .bootstrap/; narrow it (e.g. '*.py')")


def check_word(word: str) -> None:
    """A shell word after quote removal: `.e""nv`, `<.env`, `--env-file=.env`, `.en?`, `.[e]nv`, `.boot*`."""
    if word.startswith("--exclude"):
        return
    for piece in re.split(r"[=:,{}]", word.lstrip("<>&0123456789")):
        for part in piece.split("/"):
            if is_secret_name(part):
                raise Blocked("reading .env or .bootstrap/ is not allowed; use the make targets")
            # Shell globs match a leading dot only when the pattern starts with one.
            if part.startswith((".", "[.")) and GLOB_CHARS & set(part) and any(
                fnmatchcase(n, part) for n in SECRET_NAMES
            ):
                raise Blocked(f"the glob {part!r} can match .env or .bootstrap/")


def tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError as exc:
        raise Blocked(f"guard: cannot parse the command ({exc})") from exc


def segments(command: str) -> list[list[str]]:
    """Simple commands as argv lists. Redirection targets are checked as words but left out of argv
    (so `rm -rf dist 2>/dev/null` is about `dist`), as is an fd number before the operator."""
    out: list[list[str]] = [[]]
    toks = tokens(command)
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok in OPERATORS:
            out.append([])
        elif set(tok) <= set("<>&"):
            if out[-1] and out[-1][-1].isdigit():
                out[-1].pop()
            if i + 1 < len(toks) and toks[i + 1] not in OPERATORS:
                i += 1
                check_word(toks[i])
        else:
            out[-1].append(tok)
        i += 1
    return [s for s in out if s]


def unwrap(argv: list[str]) -> list[str]:
    """Drop wrappers and assignments so argv[0] is the real program (by basename)."""
    while argv:
        head = os.path.basename(argv[0])
        if "=" in argv[0] and not argv[0].startswith("-"):
            argv = argv[1:]
        elif head in WRAPPERS:
            argv = argv[1:]
            while argv and argv[0].startswith("-"):
                argv = argv[2:] if argv[0] in {"-u", "-g", "-U", "-C", "-h", "-p", "-n"} else argv[1:]
        elif head == "env":
            argv = argv[1:]
            while argv and (argv[0].startswith("-") or "=" in argv[0]):
                argv = argv[2:] if argv[0] in {"-u", "--unset", "-C", "--chdir", "-S"} else argv[1:]
        elif head == "timeout":
            argv = argv[1:]
            while argv and argv[0].startswith("-"):
                argv = argv[2:] if argv[0] in {"-s", "-k", "--signal", "--kill-after"} else argv[1:]
            argv = argv[1:]  # the duration
        else:
            return [head, *argv[1:]]
    return argv


def current_branch(cwd: Path) -> str:
    out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
                         capture_output=True, text=True, check=False)
    return out.stdout.strip()


def check_push(args: list[str], cwd: Path) -> None:
    positional = [a for a in args if not a.startswith("-")]
    for flag in (a for a in args if a.startswith("-")):
        if flag.startswith("--force") or (not flag.startswith("--") and "f" in flag[1:]):
            raise Blocked("force pushes are not allowed")
        if flag in {"--all", "--mirror", "--branches"}:
            raise Blocked("pushing every branch (including main) is not allowed")
    refspecs = positional[1:]
    if any(r.startswith("+") for r in refspecs):
        raise Blocked("force pushes are not allowed")
    for ref in refspecs:
        dest = ref.split(":")[-1].removeprefix("refs/heads/")
        if dest in PROTECTED or (dest == "HEAD" and current_branch(cwd) in PROTECTED):
            raise Blocked(f"pushing to main is not allowed; {PUSH_HINT}")
    if not refspecs and current_branch(cwd) in PROTECTED:
        raise Blocked(f"pushing to main is not allowed; {PUSH_HINT}")


def check_git(args: list[str], cwd: Path) -> None:
    while args and args[0].startswith("-"):  # global options before the subcommand
        if args[0] in GIT_OPTS_WITH_VALUE and len(args) > 1:
            if args[0] == "-C":
                cwd = (cwd / args[1]).resolve()
            args = args[2:]
        else:
            if args[0].startswith("--git-dir="):
                cwd = (cwd / args[0].split("=", 1)[1]).resolve().parent
            args = args[1:]
    if args and args[0] == "push":
        check_push(args[1:], cwd)


def is_recursive(flags: list[str]) -> bool:
    return any(f == "--recursive" or (not f.startswith("--") and ("r" in f or "R" in f)) for f in flags)


def check_rm(args: list[str], cwd: Path, targets_known: bool = True) -> None:
    if not is_recursive([a for a in args if a.startswith("-") and a != "--"]):
        return
    if not targets_known:
        raise Blocked("rm -r with paths from xargs/stdin is not allowed: the paths are not known before it runs")
    for target in (a for a in args if not a.startswith("-")):
        if any(c in target for c in "$`"):
            raise Blocked(f"rm -r of {target!r}: the path is not known before it runs")
        path = (cwd / Path(target).expanduser()).resolve()
        if path == REPO or not path.is_relative_to(REPO):
            raise Blocked(f"rm -r outside this repo ({path}) is not allowed")


def check_grep(args: list[str], cwd: Path) -> None:
    flags = [a for a in args if a.startswith("-")]
    if not (is_recursive([f for f in flags if not f.startswith("--")]) or
            any(f in {"--recursive", "--dereference-recursive", "--directories=recurse"} for f in flags)):
        return
    excludes = " ".join(f for f in flags if f.startswith("--exclude"))
    if ".env" in excludes and ".bootstrap" in excludes:
        return
    positional: list[str] = []
    pattern_given = False
    rest = iter(args)
    for a in rest:
        if a in {"-e", "-f", "--regexp", "--file"} or a.startswith(("--regexp=", "--file=")):
            pattern_given = True
            if "=" not in a:
                next(rest, None)
        elif a in {"-A", "-B", "-C", "-m", "-d", "-D", "--include", "--exclude", "--exclude-dir"}:
            next(rest, None)
        elif not a.startswith("-"):
            positional.append(a)
    targets = positional if pattern_given else positional[1:]
    for target in targets or ["."]:
        path = (cwd / Path(target).expanduser()).resolve()
        if REPO.is_relative_to(path):
            raise Blocked(f"recursive grep over the repo also reads .env and .bootstrap/; {GREP_HINT}")


def check_docker(args: list[str]) -> None:
    """`docker compose config` (or `docker-compose config`) prints every value read from .env."""
    words = [a for a in args if not a.startswith("-")]
    if "compose" in words and "config" in words:
        raise Blocked("`docker compose config` prints every value from .env; read docker-compose.yml instead")


TERRAFORM_WRITES = {"apply", "destroy", "import", "state", "taint", "untaint", "force-unlock", "test", "refresh",
                    "workspace"}
# Every other `make infra-*` is blocked, so a target added later is blocked by default.
MAKE_INFRA_ALLOWED = {"infra-plan", "infra-doctor"}
INFRA_HINT = "a person runs this one; give them the command (see infra/README.md)"


def check_terraform(args: list[str]) -> None:
    words = [a for a in args if not a.startswith("-")]
    if words and words[0] in TERRAFORM_WRITES:
        raise Blocked(f"`terraform {words[0]}` changes real infrastructure; {INFRA_HINT}")


def check_make(args: list[str]) -> None:
    for word in args:
        if word.startswith("infra-") and word not in MAKE_INFRA_ALLOWED:
            raise Blocked(f"`make {word}` changes real infrastructure; {INFRA_HINT}")


def check_aws(args: list[str]) -> None:
    words = [a for a in args if not a.startswith("-")]
    if "secretsmanager" in words and {"get-secret-value", "batch-get-secret-value"} & set(words):
        raise Blocked("reading secret values is not allowed")


def check_command(argv: list[str], cwd: Path, depth: int) -> Path:
    """Checks one simple command; returns the working directory after it (for `cd`)."""
    argv = unwrap(argv)
    if not argv:
        return cwd
    head, args = argv[0], argv[1:]
    if head == "cd":
        return (cwd / Path(args[0] if args else "~").expanduser()).resolve()
    if head in SHELLS and "-c" in args[:-1] and depth < 5:
        check_bash(args[args.index("-c") + 1], cwd, depth + 1)
    elif head == "xargs":
        rest = args
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in {"-I", "-n", "-P", "-d", "-L", "-s", "-E"} else rest[1:]
        rest = unwrap(rest)
        if rest and rest[0] == "rm":
            check_rm(rest[1:], cwd, targets_known=False)
        elif rest:
            check_command(rest, cwd, depth + 1)
    elif head == "git":
        check_git(args, cwd)
    elif head == "rm":
        check_rm(args, cwd)
    elif head in {"grep", "egrep", "fgrep"}:
        check_grep(args, cwd)
    elif head == "docker":
        check_docker(args)
    elif head == "docker-compose":
        check_docker(["compose", *args])
    elif head in {"terraform", "tofu"}:
        check_terraform(args)
    elif head in {"make", "gmake"}:
        check_make(args)
    elif head == "aws":
        check_aws(args)
    return cwd


def check_bash(command: str, cwd: Path, depth: int = 0) -> None:
    if SECRET_PATH.search(re.sub(r"--exclude\S*", "", command)):
        raise Blocked("reading .env or .bootstrap/ is not allowed; use the make targets")
    for argv in segments(command):
        for word in argv:
            check_word(word)
        if argv[0].startswith("(") or argv[0] == "{":
            argv = [argv[0].lstrip("({"), *argv[1:]] if argv[0].lstrip("({") else argv[1:]
        if argv:
            cwd = check_command(argv, cwd, depth)


def check(event: dict[str, object]) -> None:
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise Blocked("guard: hook input has no tool_input")
    if any(LIVE_KEY.search(s) for s in strings(tool_input)):
        raise Blocked("live Stripe keys are not allowed; Stripe runs in test mode only")
    for key in PATH_KEYS:
        if isinstance(tool_input.get(key), str):
            check_path(str(tool_input[key]))
    if event.get("tool_name") == "Grep" and isinstance(tool_input.get("glob"), str):
        check_glob(str(tool_input["glob"]))
    if event.get("tool_name") == "Bash":
        cwd = Path(str(event.get("cwd") or os.getcwd()))
        check_bash(str(tool_input.get("command", "")), cwd)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise Blocked("guard: hook input is not a JSON object")
        check(event)
    except Blocked as exc:
        print(exc, file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"guard: could not read the hook input ({exc})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
