"""`make env`: create or complete .env from .env.example.

A blank key with a `# Default: <value>` line above it gets that value; one with a
`# Generate: <openssl command>` line gets a fresh random value of that shape (`password <n>`: n
characters that meet Zitadel's password policy). Keys that already have
a value in .env are kept, and keys with neither marker (the Stripe key) are left for the human.

Host ports (`*_PORT` with a `# Default:`) get their defaults, or, when any of them is already taken on
this machine (say by a second product), all move up by the same step so the next product just works.
"""

import base64
import errno
import re
import secrets
import socket
import string
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
MARKER = re.compile(r"^# (Default|Generate): (.+)$")
# Empty on purpose: mock payment is off unless someone turns it on, so these are not "still to fill".
OFF_BY_DEFAULT = {"BILLING_MODE", "APP_ENV"}
PORT_DEFAULT = re.compile(r"^# Default: (\d+)\n([A-Z][A-Z0-9_]*_PORT)=[ \t]*$", re.M)
PORT_STEP = 10
PORT_TRIES = 50


def _rand_hex(n: int) -> str:
    return secrets.token_hex(n)


def _rand_base64(n: int) -> str:
    return base64.b64encode(secrets.token_bytes(n)).decode()


def _password(n: int) -> str:
    """Random letters and digits plus one symbol: Zitadel's default policy wants lower, upper, digit
    and symbol. `-` needs no quoting in .env or Compose."""
    rng = secrets.SystemRandom()
    chars = [secrets.choice(string.ascii_lowercase), secrets.choice(string.ascii_uppercase),
             secrets.choice(string.digits), "-"]
    chars += [secrets.choice(string.ascii_letters + string.digits) for _ in range(max(n - len(chars), 0))]
    rng.shuffle(chars)
    return "".join(chars)


def _rsa_base64() -> str:
    try:
        pem = subprocess.run(["openssl", "genrsa", "2048"], check=True, capture_output=True).stdout  # noqa: S607
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"make env: `openssl genrsa` failed ({exc}); install OpenSSL") from exc
    return base64.b64encode(pem).decode()


GENERATORS: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str]]] = [
    (re.compile(r"^openssl rand -hex (\d+)$"), lambda m: _rand_hex(int(m[1]))),
    (re.compile(r"^openssl rand -base64 (\d+)$"), lambda m: _rand_base64(int(m[1]))),
    (re.compile(r"^openssl genrsa 2048 \| openssl base64 -A$"), lambda m: _rsa_base64()),
    (re.compile(r"^password (\d+)$"), lambda m: _password(int(m[1]))),
]


def generate(command: str) -> str:
    for pattern, make in GENERATORS:
        match = pattern.match(command)
        if match:
            return make(match)
    raise SystemExit(f"make env: unknown generator {command!r} in .env.example")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            match = KEY.match(line)
            if match:
                values[match[1]] = match[2]
    return values


def port_free(port: int) -> bool:
    """True when nothing listens on this port, on IPv4 or IPv6 loopback. Docker publishes on 127.0.0.1 even
    if something holds ::1, and a browser may then reach that other thing with no error. It sees only what
    is running now, not a stopped stack."""
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        return False
    try:
        with socket.socket(socket.AF_INET6) as probe:
            probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            probe.bind(("::1", port))
    except OSError as exc:  # a host with no IPv6 answers with some other error, and nothing can be there
        return exc.errno not in (errno.EADDRINUSE, errno.EACCES)
    return True


def port_shift(ports: list[int], kept: set[int]) -> int:
    """The smallest step up that makes every port free, so one product's ports stay together. A port kept
    in .env counts as taken even when its service is down."""
    for shift in range(0, PORT_STEP * PORT_TRIES, PORT_STEP):
        if all(port + shift not in kept and port_free(port + shift) for port in ports):
            return shift
    raise SystemExit(f"make env: no free block of ports near {ports}; set the *_PORT values in .env by hand")


def render(example: str, current: dict[str, str]) -> tuple[str, list[str]]:
    """The .env text (example layout, current values kept, blanks filled) and the keys still empty."""
    ports = {name: int(default) for default, name in PORT_DEFAULT.findall(example) if not current.get(name)}
    kept = {int(value) for name, value in current.items() if name.endswith("_PORT") and value.isdigit()}
    shift = port_shift(list(ports.values()), kept) if ports else 0
    if shift:
        moved = ", ".join(f"{name}={port + shift}" for name, port in ports.items())
        print(f"default ports are taken on this machine, so these moved up by {shift}: {moved}")
    lines: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    marker: tuple[str, str] | None = None  # the last `# Default:`/`# Generate:` line above a key
    for line in example.splitlines():
        lines.append(line)
        found = MARKER.match(line)
        if found:
            marker = (found[1], found[2].strip())
            continue
        match = KEY.match(line)
        if not match:
            if not line.startswith("#"):
                marker = None  # a blank line ends the comment block
            continue
        name, value = match[1], current.get(match[1]) or match[2]
        if not value and marker:
            kind, arg = marker
            value = arg if kind == "Default" else generate(arg)
            if name in ports:
                value = str(ports[name] + shift)
        if not value and name not in OFF_BY_DEFAULT:
            missing.append(name)
        lines[-1] = f"{name}={value}"
        seen.add(name)
        marker = None
    lines += [f"{k}={v}" for k, v in current.items() if k not in seen]
    return "\n".join(lines) + "\n", missing


def main(root: Path = ROOT) -> None:
    target = root / ".env"
    text, missing = render((root / ".env.example").read_text(), read_env(target))
    target.write_text(text)
    target.chmod(0o600)
    print(f"wrote {target.name}")
    if missing:
        print("still empty, fill these in .env: " + ", ".join(missing))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT)
