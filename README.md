# llm-bulkhead-load-shedding

A small concurrency guard for LLM calls. It caps in-flight requests, gives each
tenant its own slice of those slots, queues the rest by priority and sheds the
least important work when the queue is full or a wait runs out.

Pure standard-library Python, offline, with a deterministic fake provider.

## Why

One noisy tenant with a burst of batch jobs should not starve an interactive
user. A global semaphore does not prevent that; a per-tenant limit plus a
priority queue does.

## Layout

- `llmbulkhead/` the library
- `tests/` unit tests (`python3 -m unittest`)
- `scripts/` a seeded simulation

Usage and results are added as the pieces land.
