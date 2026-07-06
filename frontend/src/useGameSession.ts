import { useCallback, useEffect, useState } from "react";

import {
  castVote as castVoteRequest,
  getGame,
  getMatch,
  isExpiredSessionError,
  joinMatchmaking,
  sendChat,
} from "./api";
import type { Game, Match } from "./types";

const SESSION_KEY = "whosai.session";
const POLL_INTERVAL_MS = 1000;

export type SessionError =
  | "join"
  | "send"
  | "sessionExpired"
  | "update"
  | "vote";

function readSession(): Match | null {
  try {
    const value = localStorage.getItem(SESSION_KEY);
    return value ? (JSON.parse(value) as Match) : null;
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function useGameSession() {
  const [match, setMatchState] = useState<Match | null>(readSession);
  const [game, setGame] = useState<Game | null>(null);
  const [joining, setJoining] = useState(false);
  const [actionPending, setActionPending] = useState(false);
  const [error, setError] = useState<SessionError | null>(null);
  const [votedRound, setVotedRound] = useState<number | null>(null);

  const setMatch = useCallback((nextMatch: Match) => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(nextMatch));
    setMatchState(nextMatch);
  }, []);

  useEffect(() => {
    if (!match) {
      return;
    }

    let active = true;
    let requestRunning = false;

    const poll = async () => {
      if (requestRunning) {
        return;
      }
      requestRunning = true;
      try {
        if (match.status === "waiting") {
          const nextMatch = await getMatch(match);
          if (
            active &&
            (nextMatch.status !== match.status ||
              nextMatch.game_id !== match.game_id ||
              nextMatch.seat_id !== match.seat_id)
          ) {
            setMatch(nextMatch);
          }
        } else {
          const nextGame = await getGame(match);
          if (active) {
            setGame(nextGame);
            setError(null);
          }
        }
      } catch (updateError) {
        if (!active) {
          return;
        }
        if (isExpiredSessionError(updateError)) {
          active = false;
          window.clearInterval(interval);
          localStorage.removeItem(SESSION_KEY);
          setMatchState(null);
          setGame(null);
          setVotedRound(null);
          setError("sessionExpired");
          return;
        }
        setError("update");
      } finally {
        requestRunning = false;
      }
    };

    void poll();
    const interval = window.setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [match, setMatch]);

  const join = async () => {
    setJoining(true);
    setError(null);
    try {
      setMatch(await joinMatchmaking());
    } catch {
      setError("join");
    } finally {
      setJoining(false);
    }
  };

  const postMessage = async (content: string) => {
    if (!match) {
      return;
    }
    setActionPending(true);
    setError(null);
    try {
      setGame(await sendChat(match, content));
    } catch (chatError) {
      setError("send");
      throw chatError;
    } finally {
      setActionPending(false);
    }
  };

  const vote = async (targetId: string) => {
    if (!match || !game) {
      return;
    }
    setActionPending(true);
    setError(null);
    try {
      setGame(await castVoteRequest(match, targetId));
      setVotedRound(game.round_number);
    } catch (voteError) {
      setError("vote");
      throw voteError;
    } finally {
      setActionPending(false);
    }
  };

  const leave = () => {
    localStorage.removeItem(SESSION_KEY);
    setMatchState(null);
    setGame(null);
    setError(null);
    setVotedRound(null);
  };

  return {
    actionPending,
    error,
    game,
    join,
    joining,
    leave,
    match,
    postMessage,
    vote,
    votedRound,
  };
}
