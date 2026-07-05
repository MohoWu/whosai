import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

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

describe("lobby", () => {
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
});
