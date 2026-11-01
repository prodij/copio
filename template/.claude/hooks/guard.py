"""PreToolUse guard for agents (spec §10): exit 2 with a reason on stderr blocks the tool call.

Blocks: reading `.env*` (not `.env.example`) or anything under `.bootstrap/`; any `sk_live_` string;
`git push` to main/master (explicitly, via `--all`/`--mirror`, or a bare push while on main);
force pushes; and `rm -r`/`rm -rf` of anything outside this repo (or the repo itself).
Input it cannot read is blocked too: a guard that fails open guards nothing.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # this file lives in <repo>/.claude/hooks/
PATH_KEYS = ("file_path", "path", "notebook_path")
LIVE_KEY = re.compile(r"sk_live_[0-9A-Za-z]+")
SECRET_PATH = re.compile(r"(^|[\s/'\"=<>:;|&(])(\.env(\.(?!example\b)[\w.-]+)?|\.bootstrap)(?=$|[\s/'\";|&)<>])")
SEPARATORS = re.compile(r"&&|\|\||[;|\n&]")
PROTECTED = {"main", "master"}


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


def check_path(path: str) -> None:
    parts = Path(path).parts
    name = parts[-1] if parts else ""
    if ".bootstrap" in parts:
        raise Blocked("reading .bootstrap/ (tokens and ids) is not allowed")
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        raise Blocked("reading .env is not allowed; .env.example lists the names")


def words(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def strip_prefixes(argv: list[str]) -> list[str]:
    while argv and (argv[0] in {"sudo", "command", "exec", "nohup", "time"} or "=" in argv[0]):
        argv = argv[1:]
    return argv


def current_branch(cwd: Path) -> str:
    out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
                         capture_output=True, text=True, check=False)
    return out.stdout.strip()


def check_push(args: list[str], cwd: Path) -> None:
    positional = [a for a in args if not a.startswith("-")]
    flags = [a for a in args if a.startswith("-")]
    for flag in flags:
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
            raise Blocked("pushing to main is not allowed; push your branch and open a PR")
    if not refspecs and current_branch(cwd) in PROTECTED:
        raise Blocked("pushing to main is not allowed; push your branch and open a PR")


def check_rm(args: list[str], cwd: Path) -> None:
    flags = [a for a in args if a.startswith("-") and a != "--"]
    recursive = any(f in {"--recursive"} or (not f.startswith("--") and ("r" in f or "R" in f)) for f in flags)
    if not recursive:
        return
    for target in (a for a in args if not a.startswith("-")):
        if any(c in target for c in "$`"):
            raise Blocked(f"rm -r of {target!r}: the path is not known before it runs")
        path = (cwd / Path(target).expanduser()).resolve()
        if path == REPO or not path.is_relative_to(REPO):
            raise Blocked(f"rm -r outside this repo ({path}) is not allowed")


def check_bash(command: str, cwd: Path) -> None:
    if SECRET_PATH.search(command):
        raise Blocked("reading .env or .bootstrap/ is not allowed; use the make targets")
    for segment in SEPARATORS.split(command):
        argv = strip_prefixes(words(segment))
        if not argv:
            continue
        if argv[0] == "cd":
            cwd = (cwd / Path(argv[1] if len(argv) > 1 else "~").expanduser()).resolve()
        elif argv[0] == "git":
            rest = argv[1:]
            while rest and rest[0] in {"-C", "-c"} and len(rest) > 1:
                if rest[0] == "-C":
                    cwd = (cwd / rest[1]).resolve()
                rest = rest[2:]
            if rest and rest[0] == "push":
                check_push(rest[1:], cwd)
        elif argv[0] == "rm":
            check_rm(argv[1:], cwd)


def check(event: dict[str, object]) -> None:
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise Blocked("guard: hook input has no tool_input")
    if any(LIVE_KEY.search(s) for s in strings(tool_input)):
        raise Blocked("live Stripe keys (sk_live_) are not allowed; Stripe runs in test mode only")
    for key in PATH_KEYS:
        if isinstance(tool_input.get(key), str):
            check_path(str(tool_input[key]))
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
