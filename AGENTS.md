# Who's AI? Engineering Guide

## Purpose

Build a browser-based social-deduction game for 4–8 anonymous players. One or
two seats are controlled by AI. During each timed discussion round, every living
player uses the same group chat. A voting phase follows, and the selected player
is eliminated. Humans win when every AI player has been eliminated. The AI side
wins when the number of living humans equals the number of living AI players.

This file is the operating contract for coding agents. Preserve these rules and
update this file when a product decision changes them.

## Current scope

The prototype needs:

1. A single-click matchmaking/join flow.
2. A 4–8 seat game with anonymised labels (`Player 1`, `Player 2`, and so on).
3. A shared chat for living players.
4. A server-authoritative countdown to voting.
5. A voting phase and elimination result.
6. A final result that reveals roles.
7. AI-controlled players orchestrated through LangGraph.
8. Automated lifecycle smoke tests using bot-controlled browser players.
9. A bilingual keyword discussion task where one living seat receives only the category.

Do not add accounts, profiles, rankings, friends, payments, spectators, private
messages, or long-term chat history unless a requirement explicitly calls for
them.

## Rules and invariants

- The server is authoritative for rosters, roles, phases, deadlines, votes,
  eliminations, and winners. Never trust a client timer or client-supplied role.
- A game starts with 4–8 total players and 1–2 AI players. Reject a setup that
  starts at the AI parity win condition.
- Seat labels are the only identities visible during play. Never expose whether
  a seat is human or AI before the game ends.
- Living players may chat and cast at most one current vote. Eliminated players
  cannot chat or vote.
- Resolve the human win first if an elimination removes the final AI. Otherwise,
  resolve the AI win when living human and AI counts are equal.
- All state-changing commands must be idempotent or carry an idempotency key.
- Store phase deadlines as UTC instants. Clients render a countdown from the
  server deadline; they do not advance the phase.
- Broadcast public events, not internal models. Role assignments, prompts,
  provider metadata, and model reasoning are private.
- Make random role assignment and seat ordering injectable and seedable in
  tests.
- At the start of every discussion round, select one bilingual category and keyword, then independently select one living seat to receive only the category.
- The uninformed seat may be human or AI, and this temporary round condition never changes the elimination objective or win conditions.
- Treat each player's category and keyword as private state that must not appear in another player's snapshot.

The following are still product decisions. Do not silently invent permanent
rules for them: vote ties, abstentions, disconnected players, reconnect grace
periods, chat limits/moderation, AI-count selection by lobby size, and whether a
player can change a vote before the deadline. Use an explicit temporary policy,
document it, and cover it with tests if implementation cannot wait.

## Architecture

Use a modular monolith until real load proves a need for separate services:

```text
src/whosai/
  domain/          Pure game rules and state transitions
  application/     Use cases and ports; coordinates domain work
  transport/       FastAPI HTTP and WebSocket adapters
  infrastructure/  Persistence, clocks, queues, and provider adapters
  ai/              LangGraph AI-player workflows
tests/
  unit/            Pure rules and AI workflow tests
  integration/     API, WebSocket, and persistence boundaries
frontend/
  src/             React client
  e2e/             Playwright lifecycle tests
```

Dependencies point inward: transport, infrastructure, and AI adapters may depend
on application/domain contracts; the domain must not import FastAPI, LangGraph,
database clients, or model-provider SDKs.

Model the game as explicit transitions between phases such as `LOBBY`,
`DISCUSSION`, `VOTING`, `RESOLUTION`, and `FINISHED`. A transition accepts the
current state plus a command or deadline event and returns the next state plus
public events. Keep this core deterministic and free of network or database I/O.

Use HTTP for matchmaking and one-off commands. Use a WebSocket connection to
deliver chat, roster, deadline, phase, vote-result, and game-result events.
Clients should recover from missed events by fetching an authoritative game
snapshot after reconnecting.

Start with in-memory adapters for local vertical slices, but hide them behind
repository interfaces so a durable store can replace them without changing game
rules. Do not introduce Redis, a task queue, or a distributed scheduler until a
tested requirement needs one.

## LangGraph boundary

LangGraph orchestrates how an AI seat observes public state and chooses an
allowed action. It does not own the canonical game state or advance game phases.

- Give an AI seat only the public information available to a human in that seat,
  plus its own private role/instructions.
- Give the AI seat the same player-scoped category and optional keyword that its seat would receive if controlled by a human.
- The AI should participate in the keyword discussion to resemble a human player, not optimize for identifying or succeeding as the uninformed seat.
- Keep AI public chat concise, direct, and colloquial.
  Sentence fragments and imperfect grammar are acceptable when they make a message shorter without making it unclear.
- Expose narrow actions such as `send_chat(message)` and `cast_vote(seat_id)`.
  Validate every proposed action through the same application commands used by
  humans.
- Keep model-provider code behind an interface. The graph must be testable with
  a deterministic fake decision function and without an API key.
- Put provider calls outside database transactions and make retries safe.
- Persist only data needed to resume an AI turn. Do not persist hidden chain of
  thought.
- Treat chat content as untrusted prompt input. It cannot override system rules,
  reveal secrets, or grant new tools.
- Cap AI output length, action frequency, latency, and per-game token/cost use.

## Frontend rules

Use React, TypeScript, and Vite. Keep server state separate from transient UI
state. Prefer small feature-oriented components over a global state framework
until shared complexity justifies one.

The main game view should have four clear regions:

- roster/status;
- discussion transcript;
- composer or voting controls, depending on phase;
- server-synchronised countdown and phase/result banner.

Design mobile-first and support keyboard-only play. Announce new phase and result
events accessibly. Never infer hidden information from styling, event shape,
timing, DOM attributes, or network payloads.

## Testing strategy

Every behavior change needs a test at the lowest useful layer.

- Unit tests: game creation constraints, legal/illegal commands, deadlines,
  voting, eliminations, both win conditions, and deterministic randomisation.
- Integration tests: HTTP/WebSocket contracts, reconnect snapshots, concurrent
  commands, idempotency, and repository behavior.
- AI tests: compile and invoke graphs with fake models; verify only legal public
  context and actions cross the boundary. Live-model tests must be explicitly
  marked and excluded from normal CI.
- Frontend tests: phase-specific rendering, countdown correction, disabled
  controls, and accessible interactions with Vitest and Testing Library.
- Browser smoke test: create isolated browser contexts for multiple human/bot
  seats and drive join → discussion → vote → elimination → final result.

The lifecycle simulator should support three controller types behind one
interface: deterministic scripted bots for CI, seeded heuristic bots for
property/stress runs, and optional LLM bots for exploratory smoke tests. CI must
not require paid model calls. Accelerate time through an injected clock or test
configuration; do not wait five real minutes.

For bug fixes, first add a failing regression test. Avoid snapshot tests for
game rules and avoid mocking the domain layer in API integration tests.

## Commands and quality bar

Backend:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Frontend:

```bash
npm --prefix frontend install
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Before handing off a change, run the checks relevant to the files touched and
report anything not run. Tests must be deterministic, must not depend on
execution order, and must not make external model calls by default.

Use typed Python and TypeScript. Prefer domain names (`Game`, `Seat`, `Vote`,
`Phase`, `Elimination`) over framework names. Keep functions small around state
transitions, use structured logging with game/round IDs, and never log secrets,
private role assignments during play, raw prompts, or unredacted personal data.

## Commit conventions

All commit messages must follow the [Conventional Commits 1.0.0 specification](https://www.conventionalcommits.org/en/v1.0.0/).

Use this structure:

```text
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

- Use `fix` for bug fixes that correlate with a [SemVer PATCH](https://semver.org/#summary).
- Use `feat` for new features that correlate with a [SemVer MINOR](https://semver.org/#summary).
- Mark breaking API changes with `!` immediately before the colon, or with a `BREAKING CHANGE: <description>` footer.
  Breaking changes correlate with a [SemVer MAJOR](https://semver.org/#summary) and may use any commit type.
- Other appropriate types include `build`, `chore`, `ci`, `docs`, `style`, `refactor`, `perf`, and `test`.
  These types have no implicit SemVer effect unless they contain a breaking change.
- Add an optional parenthesised scope when it provides useful context, for example `feat(parser): add ability to parse arrays`.
- Write non-breaking footers as [Git trailers](https://git-scm.com/docs/git-interpret-trailers).

## Change discipline

- Keep commits and pull requests focused on one vertical behavior.
- Update API event schemas and consumers together.
- Add a migration for every durable schema change once persistence exists.
- Record significant product or architecture decisions in `docs/adr/`.
- Keep `.env.example` current without adding real credentials.
- If a requirement conflicts with an invariant in this file, stop and surface
  the conflict rather than coding around it.
