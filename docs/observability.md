# AI observability

The first observability backend is LangSmith. It integrates directly with
LangChain and LangGraph, and its standalone CLI emits JSON intended for scripts
and coding agents. Langfuse remains a reasonable option if self-hosting or an
open data platform becomes more important than the native LangGraph tooling.

Tracing is disabled by default. To enable it for local development, set:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=lsv2_your_key
export LANGSMITH_PROJECT=whosai-dev
# EU accounts:
# export LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
# Set this for organization-scoped keys or keys with multiple workspaces:
# export LANGSMITH_WORKSPACE_ID=your_workspace_id
```

If trace ingestion returns `403 Forbidden`, first confirm that
`LANGSMITH_ENDPOINT` matches the account region. Do not leave placeholder values
such as `<workspace-id>` in `.env`; omit `LANGSMITH_WORKSPACE_ID` unless the key
actually requires it.

The graph names each top-level trace `ai-player-turn`. Its model call includes
the `game_id`, anonymous `player_id`, round number, and phase as metadata. It
does not add a chain-of-thought field.

## Trace contents and privacy

LangSmith normally records graph and model inputs and outputs, including the
chat transcript. Keep these settings enabled unless synthetic development data
is being used and prompt inspection is explicitly required:

```bash
export LANGSMITH_HIDE_INPUTS=true
export LANGSMITH_HIDE_OUTPUTS=true
```

Never put real identities, credentials, role assignments for other seats, or
provider secrets in trace metadata. Define retention and redaction policies
before enabling prompt capture outside local development.

## Querying from the CLI

The CLI is currently alpha, so pin or review upgrades before using it in CI.
Install it with the official installer, then authenticate:

```bash
curl -fsSL https://cli.langsmith.com/install.sh | sh
langsmith auth login
```

Useful coding-agent queries:

```bash
langsmith trace list --project whosai-dev --limit 20 --last-n-minutes 60
langsmith trace list --project whosai-dev --error --full
langsmith trace get TRACE_ID --project whosai-dev --full
langsmith run list --project whosai-dev --run-type llm --include-metadata
langsmith trace export ./traces --project whosai-dev --limit 100 --full
```

The default output is JSON. Add `--format pretty` before the resource name for a
human-readable table.
