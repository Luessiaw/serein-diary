"""Mint and inspect the ai-writer bearer token.

Run this where the API settings are available (the server host, or inside the
api container with its environment), then store the digest as
`DIARY_AI_TOKEN_SHA256`. The token itself is printed once and never persisted
by this tool.

    python -m serein.issue_ai_token            # new token + digest
    python -m serein.issue_ai_token --verify   # check a pasted token

Only an operator with host access can issue a token, because minting is done
here rather than through the HTTP API: there is deliberately no endpoint that
turns a password into write access.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import secrets
import sys

from serein.config import ConfigError, load_settings


def digest_of(token: str) -> str:
    """Return the hex sha256 an operator must put in DIARY_AI_TOKEN_SHA256."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="read a token from stdin and compare it with the configured digest",
    )
    args = parser.parse_args(argv)

    # 签发阶段不能强依赖完整配置：DIARY_AI_WRITER_ENABLED=true 时
    # load_settings 会要求 DIARY_AI_TOKEN_SHA256，而那个值正是本次要产出的，
    # 直接加载会陷入先有鸡还是先有蛋。所以签发路径在配置不全时降级继续，
    # 只有 --verify 才必须拿到已配置的摘要。
    try:
        settings = load_settings()
        config_error = None
    except ConfigError as error:
        settings = None
        config_error = error

    if settings is None and args.verify:
        print(f"ERROR: {config_error}", file=sys.stderr)
        return 2
    if settings is None:
        print(
            f"NOTE: 配置尚未就绪（{config_error}），仍可签发 token。",
            file=sys.stderr,
        )

    if args.verify:
        token = sys.stdin.readline().strip()
        if not token:
            print("ERROR: no token on stdin", file=sys.stderr)
            return 2
        if not settings.ai_token_sha256:
            print("ERROR: DIARY_AI_WRITER_ENABLED is off; no digest configured", file=sys.stderr)
            return 2
        if hmac.compare_digest(digest_of(token), settings.ai_token_sha256):
            print("OK: token matches the configured digest")
            return 0
        print("MISMATCH: token does not match the configured digest", file=sys.stderr)
        return 1

    # 32 bytes of entropy, url-safe: long enough that it is never guessed, and
    # safe to paste into an HTTP header without quoting. The token is an opaque
    # secret, not a signed blob: the server only ever compares its digest.
    token = secrets.token_urlsafe(32)
    print("AI writer token (store this in the agent's config, never in chat):")
    print(f"  {token}")
    print()
    print("Digest for .env (safe to store on the server):")
    print(f"  DIARY_AI_TOKEN_SHA256={digest_of(token)}")
    print("  DIARY_AI_WRITER_ENABLED=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
