# ADR-0001: Four-seat MVP rules

## Status

Accepted as a temporary MVP policy.

## Context

The first playable backend slice needs explicit policies for the product decisions that are intentionally unresolved in `AGENTS.md`.
These policies are narrow defaults for the four-seat in-memory prototype and are expected to be revisited after playtesting.

## Decision

- A match starts when three human tickets are waiting.
- The server creates exactly four seats and assigns exactly one AI role.
- Seat and role assignment use an injected random source so tests can provide a stable seed.
- Discussion lasts 300 seconds and voting lasts 30 seconds.
- The first valid vote from a living player is final for that round.
- A living player may vote for their own seat.
- There is no explicit abstain action.
- A player who has not voted by the deadline contributes no vote.
- A unique highest vote total eliminates that seat.
- A tie eliminates nobody and starts another discussion round.
- A disconnected human remains alive and may reconnect with the same player capability token.
- Each chat message is limited to 500 characters after surrounding whitespace is removed.
- Roles remain null in public snapshots until the game finishes.
- Completed round snapshots expose the eliminated seat and the final voter-to-target mapping.
- Current-round votes remain private until the voting deadline resolves.

## Consequences

The server can run deterministic lifecycle tests without paid model calls or durable infrastructure.
An application phase scheduler now advances games at server deadlines through cancellable infrastructure timers.
Application commands still reconcile an expired deadline as a defensive fallback.
The separate AI scheduler debounces discussion triggers and invokes living AI seats once when voting starts.
Browser smoke tests may explicitly enable authenticated test-only phase controls and a deterministic AI controller.
WebSocket broadcasts remain necessary for real-time phase delivery to clients.
