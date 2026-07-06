# Who's AI?

A social-deduction game for 4–8 anonymous players. One or two players are
controlled by AI; humans win by eliminating every AI player, while the AI side
wins when the number of living humans equals the number of living AI players.

This repository currently contains:

- FastAPI backend managed by `uv`
- an authoritative in-memory four-seat game with one hidden AI role
- capability-protected matchmaking, snapshot, chat, and voting HTTP APIs
- deterministic discussion, voting, elimination, and winner transitions
- independent deadline and AI-action schedulers over cancellable asyncio timers
- LangGraph boundary for AI-player decision workflows
- React, TypeScript, and Vite frontend
- pytest backend tests, Vitest component tests, and Playwright browser tests

## Why this frontend

React with Vite is the smallest useful fit for the prototype. The game is a
real-time single-page application and does not currently need server rendering,
SEO, or Next.js server features. Keep the backend authoritative and communicate
through HTTP for commands and WebSockets for live game events.

## Local setup

Prerequisites: Python 3.12, `uv`, Node.js 22 or newer, and npm.

```bash
uv sync
npm --prefix frontend install
```

Run the backend:

```bash
uv run uvicorn whosai.main:app --app-dir src --reload --port 8000
```

Run the frontend in another terminal:

```bash
npm --prefix frontend run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` and `/ws` to the backend.

## Render deployment

The repository includes a `render.yaml` Blueprint for one free Render web service.
The Render build installs locked Python and frontend dependencies, builds the Vite application, and starts one Uvicorn process.
FastAPI serves the generated frontend and the `/api` routes from the same origin.

1. Push this repository to GitHub, GitLab, or Bitbucket.
2. In Render, create a new Blueprint and select the repository.
3. Enter `DEEPSEEK_API_KEY` when Render prompts for the unsynchronised secret.
4. Deploy the Blueprint and open the generated `onrender.com` URL.

Do not enable `WHOSAI_E2E` on Render.
That mode uses the scripted browser-test AI and exposes phase controls intended only for automated tests.

The prototype stores matches and games in one process.
Keep the service at one instance, and expect active games to disappear whenever the free service sleeps, restarts, or redeploys.

## Four-seat backend slice

Three calls to `POST /api/matchmaking/join` create one game with three human seats and one AI seat.
Every state-changing request requires an `Idempotency-Key` header.
The join response contains an opaque player token that clients send as `Authorization: Bearer <token>`.

The current HTTP surface is:

- `POST /api/matchmaking/join`
- `GET /api/matchmaking/{ticket_id}`
- `GET /api/games/{game_id}`
- `POST /api/games/{game_id}/chat`
- `POST /api/games/{game_id}/votes`

Game snapshots expose seat labels and alive status while keeping roles null until the game finishes.
See [ADR-0001](docs/adr/0001-four-seat-mvp-rules.md) for the temporary timing, tie, abstention, reconnect, and chat policies.

## Checks

```bash
uv run pytest
uv run ruff check .
uv run mypy src
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Install a Playwright browser once, then run the browser smoke test:

```bash
npm --prefix frontend exec playwright install chromium
npm --prefix frontend run test:e2e
```

See [AGENTS.md](AGENTS.md) for product invariants, architecture boundaries, and
the expected test strategy.

## AI player

The discussion graph accepts an injected LangChain chat model configured for
structured output. During discussion it returns either `speak` with one public
message or `wait` with a null response. During voting it returns `vote` with an
explicit `target_player_id`. This keeps provider selection outside the game
logic and allows deterministic fake models in tests.

LangSmith tracing is opt-in and adds anonymous game, player, round, and phase
metadata to AI decisions. See [docs/observability.md](docs/observability.md) for
privacy settings and coding-agent CLI queries.

Run the four-player DeepSeek simulation after adding `DEEPSEEK_API_KEY` and
`LANGSMITH_API_KEY` to `.env`:

```bash
uv run whosai-simulate-ai
```

The simulator invokes all four players concurrently for each discussion batch,
continues until the transcript exceeds 20 messages, and then collects one vote
from every player.

To test the production prompt conversationally without starting a game, run:

```bash
uv run whosai-chat-ai
```

Each line is added to a current-round transcript as `Player 1` and triggers one decision by `Player 4`.
The command uses the same graph, system prompt, structured decision schema, and DeepSeek provider as the game.
Use `--help` to change the player labels, category, keyword, or uninformed status.
Each message makes a paid provider call.

Run the one-call live smoke test before deploying a provider or default-model change:

```bash
WHOSAI_RUN_LIVE_MODEL_TESTS=1 uv run pytest -m live_model tests/live
```

The live smoke test loads `DEEPSEEK_API_KEY` from `.env`, uses the default model configuration, and incurs one paid model call.
Normal test runs exclude all tests marked `live_model`.
