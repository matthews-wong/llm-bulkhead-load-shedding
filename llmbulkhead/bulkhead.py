"""Bounded concurrency with per-tenant limits, a priority queue and load shedding."""

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

REASON_QUEUE_FULL = "queue_full"
REASON_SHED = "shed_by_higher_priority"
REASON_TIMEOUT = "wait_timeout"


class Rejected(Exception):
    def __init__(self, reason: str, tenant: str) -> None:
        super().__init__(f"request from tenant {tenant!r} rejected: {reason}")
        self.reason = reason
        self.tenant = tenant


@dataclass
class _Waiter:
    tenant: str
    key: tuple  # (priority, arrival sequence); smaller runs first
    granted: bool = False
    rejected_reason: Optional[str] = None


@dataclass
class Bulkhead:
    max_concurrent: int
    max_queue: int
    tenant_limit: int
    _in_flight: int = 0
    _per_tenant: dict = field(default_factory=dict)
    _waiters: list = field(default_factory=list)
    _seq: int = 0
    _cond: threading.Condition = field(default_factory=threading.Condition)

    def __post_init__(self) -> None:
        if min(self.max_concurrent, self.tenant_limit) < 1 or self.max_queue < 0:
            raise ValueError(
                f"invalid limits: max_concurrent={self.max_concurrent}, "
                f"tenant_limit={self.tenant_limit}, max_queue={self.max_queue}"
            )

    def acquire(self, tenant: str, priority: int, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        with self._cond:
            self._seq += 1
            waiter = _Waiter(tenant, (priority, self._seq))
            self._waiters.append(waiter)
            self._dispatch()
            if not waiter.granted:
                self._shed_overflow()
            while not waiter.granted and waiter.rejected_reason is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._waiters.remove(waiter)
                    waiter.rejected_reason = REASON_TIMEOUT
                    break
                self._cond.wait(remaining)
            if waiter.rejected_reason is not None:
                raise Rejected(waiter.rejected_reason, tenant)

    def release(self, tenant: str) -> None:
        with self._cond:
            self._in_flight -= 1
            self._per_tenant[tenant] -= 1
            self._dispatch()

    def _dispatch(self) -> None:
        # Skip waiters whose tenant is at its limit so they cannot block others.
        for waiter in sorted(self._waiters, key=lambda w: w.key):
            if self._in_flight >= self.max_concurrent:
                return
            if self._per_tenant.get(waiter.tenant, 0) >= self.tenant_limit:
                continue
            self._waiters.remove(waiter)
            self._in_flight += 1
            self._per_tenant[waiter.tenant] = self._per_tenant.get(waiter.tenant, 0) + 1
            waiter.granted = True
        self._cond.notify_all()

    def _shed_overflow(self) -> None:
        while len(self._waiters) > self.max_queue:
            worst = max(self._waiters, key=lambda w: w.key)
            self._waiters.remove(worst)
            # The newest arrival always has the largest key within its priority,
            # so equal-priority overflow rejects the newcomer, not older waiters.
            newest = max(self._waiters + [worst], key=lambda w: w.key[1])
            worst.rejected_reason = REASON_QUEUE_FULL if worst is newest else REASON_SHED
        self._cond.notify_all()
