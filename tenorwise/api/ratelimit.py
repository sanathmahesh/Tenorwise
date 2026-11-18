"""Daily caps on the AI endpoints, per IP and global (PLAN.md section 9).

Counts live in Upstash Redis (REST API), keyed by a salted hash of the IP: the
raw IP is never stored. If Redis cannot be reached, or limits are not
configured, the AI endpoints refuse; nothing else is affected.

A request that hits the per-IP cap does not count towards the global cap.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

import httpx

KEY_TTL_S = 2 * 24 * 3600  # keys are per UTC day; expire after two days


class RedisUnavailable(Exception):
    pass


class Counter(Protocol):
    def incr_with_expiry(self, key: str, ttl_s: int) -> int: ...


class UpstashRedis:
    def __init__(self, url: str, token: str, timeout_s: float = 2.0) -> None:
        self.url, self._token, self.timeout_s = url.rstrip("/"), token, timeout_s

    def incr_with_expiry(self, key: str, ttl_s: int) -> int:
        try:
            r = httpx.post(
                f"{self.url}/pipeline",
                json=[["INCR", key], ["EXPIRE", key, str(ttl_s)]],
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self.timeout_s,
            )
            r.raise_for_status()
            return int(r.json()[0]["result"])
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise RedisUnavailable("rate-limit store unavailable") from None


@dataclass
class FakeRedis:
    """In-process counter for tests and local development only (never on Vercel)."""

    store: dict[str, int] = field(default_factory=dict)

    def incr_with_expiry(self, key: str, ttl_s: int) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]


def ip_key(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


@dataclass
class Limiter:
    counter: Counter
    salt: str
    per_ip_per_day: int
    global_per_day: int

    def check(self, ip: str, today: str | None = None) -> str | None:
        """None if allowed, otherwise the reason. Raises RedisUnavailable."""
        day = today or datetime.now(UTC).date().isoformat()
        if self.counter.incr_with_expiry(f"tw:ai:{day}:ip:{ip_key(ip, self.salt)}", KEY_TTL_S) > self.per_ip_per_day:
            return f"per-IP daily limit of {self.per_ip_per_day} AI requests reached; try again tomorrow (UTC)"
        if self.counter.incr_with_expiry(f"tw:ai:{day}:global", KEY_TTL_S) > self.global_per_day:
            return f"global daily limit of {self.global_per_day} AI requests reached; try again tomorrow (UTC)"
        return None


_LOCAL_DEV_COUNTER = FakeRedis()


def limiter_from_env() -> Limiter:
    """Build the limiter from environment variables, or raise RedisUnavailable."""
    try:
        per_ip = int(os.environ["AI_LIMIT_PER_IP_PER_DAY"])
        global_ = int(os.environ["AI_LIMIT_GLOBAL_PER_DAY"])
        salt = os.environ["IP_HASH_SALT"]
    except (KeyError, ValueError):
        raise RedisUnavailable("rate limits are not configured") from None
    if os.environ.get("RATE_LIMIT_BACKEND") == "memory":
        if os.environ.get("VERCEL"):
            raise RedisUnavailable("the in-memory rate limiter is for local development only")
        return Limiter(_LOCAL_DEV_COUNTER, salt, per_ip, global_)
    url, token = os.environ.get("UPSTASH_REDIS_REST_URL"), os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not (url and token):
        raise RedisUnavailable("rate-limit store is not configured")
    return Limiter(UpstashRedis(url, token), salt, per_ip, global_)
