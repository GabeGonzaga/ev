"""What stands between a browser tab and this machine.

Until this surface existed, the answer was "nothing can address it": a Unix
socket has no origin to forge and no port to find. A loopback port has both,
and every tab the user has open can try. So the guarantees here are written as
code with tests rather than as intentions:

* a token, per daemon run, that a page can only have been given
* a `Host` that must be loopback, which is what stops DNS rebinding: a hostile
  site resolving its own name to 127.0.0.1 still sends *its* name in `Host`
* an `Origin` that must be this server or absent, so a cross-site `fetch`
  cannot act even with a stolen token

None of these is clever. All of them are the difference between a local tool
and a remote hole, and each one has failed in real products by being skipped.
"""

from __future__ import annotations

import hmac
import secrets
from pathlib import Path

TOKEN_FILE = "web-token"
TOKEN_BYTES = 32


def token_path(state_dir: Path) -> Path:
    return state_dir / TOKEN_FILE


def issue(state_dir: Path) -> str:
    """A new token for this run, readable by this user alone.

    Per run rather than persistent: a token that outlives the process it
    authorised is a credential nobody remembers granting.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    path = token_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Written 0600 from the start rather than created and then narrowed: the
    # gap between those two is a readable secret.
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(token, encoding="utf-8")
    return token


def matches(expected: str, given: str | None) -> bool:
    """Constant time, because a token check that leaks its progress is a token
    check that can be walked one character at a time."""
    if not given:
        return False
    return hmac.compare_digest(expected, given)


def local_host(host: str | None, port: int) -> bool:
    """`Host` must name loopback.

    This is the DNS rebinding defence. A hostile page can point its own domain
    at 127.0.0.1 and reach this port, but the browser still sends that domain
    in `Host`, and this refuses it.
    """
    if not host:
        return False

    name = host.rsplit(":", 1)[0].strip("[]").lower()
    if host.rsplit(":", 1)[-1].isdigit() and int(host.rsplit(":", 1)[-1]) != port:
        return False

    return name in {"localhost", "127.0.0.1", "::1"}


def same_origin(origin: str | None, port: int) -> bool:
    """No `Origin` (a same-origin navigation or a direct client) or ours.

    A cross-site `fetch` always carries one, so this refuses a page on another
    origin acting with a token it should not have.
    """
    if origin is None:
        return True

    for scheme in ("http://", "https://"):
        if origin.startswith(scheme):
            return local_host(origin.removeprefix(scheme), port)
    return False
