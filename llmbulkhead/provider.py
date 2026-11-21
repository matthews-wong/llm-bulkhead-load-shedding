"""Provider seam and a deterministic fake."""

import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Request:
    prompt: str
    tenant: str = "default"
    priority: int = 1  # lower number = more important
    max_tokens: int = 256


@dataclass(frozen=True)
class Response:
    text: str
    tokens: int


class Provider(Protocol):
    def complete(self, request: Request) -> Response: ...


class FakeProvider:
    """Echoes the prompt after a fixed delay, so tests and simulations are repeatable."""

    def __init__(self, delay_s: float = 0.0) -> None:
        self._delay_s = delay_s

    def complete(self, request: Request) -> Response:
        if self._delay_s:
            time.sleep(self._delay_s)
        text = f"echo: {request.prompt}"
        return Response(text=text, tokens=len(text.split()))
