import type { Game, Match } from "./types";

interface ApiErrorBody {
  detail?: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isExpiredSessionError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 403 || error.status === 404)
  );
}

function idempotencyKey(prefix: string): string {
  const id =
    typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${id}`;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new ApiError(
      body.detail ?? `Request failed with status ${response.status}.`,
      response.status,
    );
  }
  return (await response.json()) as T;
}

function authorization(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function joinMatchmaking(): Promise<Match> {
  return readJson<Match>(
    await fetch("/api/matchmaking/join", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey("join") },
    }),
  );
}

export async function getMatch(match: Match): Promise<Match> {
  return readJson<Match>(
    await fetch(`/api/matchmaking/${match.ticket_id}`, {
      headers: authorization(match.player_token),
    }),
  );
}

export async function getGame(match: Match): Promise<Game> {
  if (!match.game_id) {
    throw new Error("The match has no game ID.");
  }
  return readJson<Game>(
    await fetch(`/api/games/${match.game_id}`, {
      headers: authorization(match.player_token),
    }),
  );
}

export async function sendChat(match: Match, content: string): Promise<Game> {
  if (!match.game_id) {
    throw new Error("The match has no game ID.");
  }
  return readJson<Game>(
    await fetch(`/api/games/${match.game_id}/chat`, {
      method: "POST",
      headers: {
        ...authorization(match.player_token),
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey("chat"),
      },
      body: JSON.stringify({ content }),
    }),
  );
}

export async function castVote(match: Match, targetId: string): Promise<Game> {
  if (!match.game_id) {
    throw new Error("The match has no game ID.");
  }
  return readJson<Game>(
    await fetch(`/api/games/${match.game_id}/votes`, {
      method: "POST",
      headers: {
        ...authorization(match.player_token),
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey("vote"),
      },
      body: JSON.stringify({ target_id: targetId }),
    }),
  );
}
