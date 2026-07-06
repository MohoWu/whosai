import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { Game, Match } from "./types";

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => {
      values.delete(key);
    },
    setItem: (key, value) => {
      values.set(key, value);
    },
  };
}

const matchedSession: Match = {
  ticket_id: "ticket-1",
  player_token: "token-1",
  status: "matched",
  game_id: "game-1",
  seat_id: "Player 1",
};

const discussionGame: Game = {
  id: "game-1",
  seats: [
    { id: "Player 1", alive: true, role: null },
    { id: "Player 2", alive: true, role: null },
    { id: "Player 3", alive: true, role: null },
    { id: "Player 4", alive: true, role: null },
  ],
  phase: "discussion",
  round_number: 1,
  phase_deadline: null,
  winner: null,
  messages: [],
  round_results: [],
  round_brief: null,
};

function mockGameResponse(game: Game) {
  return vi.fn().mockImplementation(() =>
    Promise.resolve(
      new Response(JSON.stringify(game), {
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("requests matchmaking and shows the waiting state", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            ticket_id: "ticket-1",
            player_token: "token-1",
            status: "waiting",
            game_id: null,
            seat_id: null,
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "ENTER THE NETWORK" }));

    expect(await screen.findByRole("status")).toHaveTextContent("LINK REQUEST SENT");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/matchmaking/join",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("restores a waiting match and polls for updates every second", async () => {
    localStorage.setItem(
      "whosai.session",
      JSON.stringify({
        ticket_id: "ticket-1",
        player_token: "token-1",
        status: "waiting",
        game_id: null,
        seat_id: null,
      }),
    );
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            ticket_id: "ticket-1",
            player_token: "token-1",
            status: "waiting",
            game_id: null,
            seat_id: null,
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => window.setTimeout(resolve, 1050));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("clears a persisted match when the backend rejects its game token", async () => {
    localStorage.setItem("whosai.session", JSON.stringify(matchedSession));
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            detail: "The player token does not belong to this game.",
          }),
          {
            status: 403,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByRole("button", { name: "ENTER THE NETWORK" }),
    ).toBeVisible();
    expect(screen.getByText("Your saved game expired. Join again.")).toBeVisible();
    expect(localStorage.getItem("whosai.session")).toBeNull();
    await new Promise((resolve) => window.setTimeout(resolve, 1050));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("switches the lobby to Chinese and persists the selection", () => {
    vi.stubGlobal("fetch", vi.fn());

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(screen.getByText("匿名社交推理")).toBeVisible();
    expect(screen.getByRole("button", { name: "进入网络" })).toBeVisible();
    expect(screen.getByLabelText("游戏详情")).toHaveTextContent("03 人类");
    expect(screen.queryByText("ANONYMOUS SOCIAL DEDUCTION")).not.toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("lang", "zh-CN");
    expect(document.title).toBe("谁是 AI？");
    expect(localStorage.getItem("whosai.language")).toBe("zh-CN");
  });

  it("switches every live-game control and seat label to Chinese", async () => {
    localStorage.setItem("whosai.session", JSON.stringify(matchedSession));
    vi.stubGlobal("fetch", mockGameResponse(discussionGame));

    render(<App />);

    expect(await screen.findByText("DISCUSSION LIVE")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(screen.getByText("讨论进行中")).toBeVisible();
    expect(screen.getByText("活动节点")).toBeVisible();
    expect(screen.getByTestId("player-seat")).toHaveTextContent("玩家 1");
    expect(screen.getByTestId("round-number")).toHaveAttribute("data-prefix", "回");
    expect(screen.getByLabelText("向频道发送消息")).toBeVisible();
    expect(screen.getByRole("button", { name: "发送消息" })).toBeDisabled();
    expect(screen.getByText("任务情报")).toBeVisible();
    expect(screen.queryByText("MISSION INTEL")).not.toBeInTheDocument();
  });

  it("can leave a stale saved game after an update failure", async () => {
    localStorage.setItem("whosai.session", JSON.stringify(matchedSession));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Missing game")));

    render(<App />);

    expect(await screen.findByText("Unable to update the game.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "RETURN TO NETWORK" }));

    expect(
      await screen.findByRole("button", { name: "ENTER THE NETWORK" }),
    ).toBeVisible();
    expect(localStorage.getItem("whosai.session")).toBeNull();
  });

  it("renders the complete result view in the persisted language", async () => {
    const finishedGame: Game = {
      ...discussionGame,
      seats: discussionGame.seats.map((seat, index) => ({
        ...seat,
        alive: index !== 3,
        role: index === 3 ? "ai" : "human",
      })),
      phase: "finished",
      winner: "humans",
      round_results: [
        {
          round_number: 1,
          eliminated_id: "Player 4",
          votes: [
            { voter_id: "Player 1", target_id: "Player 4" },
            { voter_id: "Player 2", target_id: "Player 4" },
          ],
        },
      ],
    };
    localStorage.setItem("whosai.session", JSON.stringify(matchedSession));
    localStorage.setItem("whosai.language", "zh-CN");
    vi.stubGlobal("fetch", mockGameResponse(finishedGame));

    render(<App />);

    expect(await screen.findByTestId("winner")).toHaveTextContent("人类胜利");
    expect(screen.getByText("身份揭晓")).toBeVisible();
    expect(screen.getByText("投票档案")).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 3, name: "玩家 4 已被淘汰" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "返回网络" })).toBeVisible();
  });
});
