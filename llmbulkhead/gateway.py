"""Gateway that runs every provider call inside the bulkhead."""

from .bulkhead import Bulkhead
from .provider import Provider, Request, Response


class Gateway:
    def __init__(self, provider: Provider, bulkhead: Bulkhead, wait_timeout_s: float = 1.0) -> None:
        self._provider = provider
        self._bulkhead = bulkhead
        self._wait_timeout_s = wait_timeout_s

    def complete(self, request: Request) -> Response:
        self._bulkhead.acquire(request.tenant, request.priority, self._wait_timeout_s)
        try:
            return self._provider.complete(request)
        finally:
            self._bulkhead.release(request.tenant)
