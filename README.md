# llm-bulkhead-load-shedding

A small concurrency guard for LLM calls. It caps in-flight requests, gives each
tenant its own slice of those slots, queues the rest by priority and sheds the
least important work when the queue is full or a wait runs out.

Pure standard-library Python, offline, with a deterministic fake provider.

## Why

One noisy tenant with a burst of batch jobs should not starve an interactive
user. A global semaphore does not prevent that; a per-tenant limit plus a
priority queue does.

## Usage

```python
from llmbulkhead import Bulkhead, FakeProvider, Gateway, Rejected, Request

gateway = Gateway(
    FakeProvider(),
    Bulkhead(max_concurrent=4, max_queue=8, tenant_limit=3),
    wait_timeout_s=0.5,
)
try:
    reply = gateway.complete(Request("hello", tenant="ui", priority=0))
except Rejected as exc:
    print(exc.reason)  # queue_full, shed_by_higher_priority or wait_timeout
```

Swap `FakeProvider` for anything with `complete(request) -> Response`.

## Behaviour

- Lower `priority` numbers run first; ties run in arrival order.
- A tenant at `tenant_limit` waits without blocking other tenants.
- When the queue is over `max_queue`, the lowest-priority, newest waiter is
  rejected. An equal-priority newcomer is rejected rather than older waiters.
- The slot is released when the provider raises.

## Validate

```
make validate
```

This runs the unit tests and a simulation.

## Simulation

`scripts/simulate.py` sends 60 batch and 10 interactive requests at a fake
provider with 4 slots, a queue of 8 and a 50 ms delay. It is synthetic, and
counts vary a little between runs.

```
same priority    interactive ok 8/10  batch ok 12/60
tenant limit 3   interactive ok 9/10  batch ok 11/60
ui priority      interactive ok 10/10  batch ok 10/60
```

Priority does most of the work here. The tenant limit helps only a little
because the queue is still shared, so a burst can fill it. Per-tenant queue
quotas are the obvious next step.
