import {
  Browser,
  BrowserContext,
  expect,
  Page,
  test,
} from "@playwright/test";

interface StoredMatch {
  game_id: string;
  player_token: string;
  seat_id: string;
}

async function createPlayer(
  browser: Browser,
  viewport: { width: number; height: number } | undefined,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: "ENTER THE NETWORK" }).click();
  return { context, page };
}

async function storedMatch(page: Page): Promise<StoredMatch> {
  return page.evaluate(() => {
    const value = localStorage.getItem("whosai.session");
    if (!value) {
      throw new Error("The browser has no stored match.");
    }
    return JSON.parse(value) as StoredMatch;
  });
}

async function advancePhase(page: Page, key: string): Promise<void> {
  const match = await storedMatch(page);
  const response = await page.request.post(
    `/api/testing/games/${match.game_id}/advance`,
    {
      headers: {
        Authorization: `Bearer ${match.player_token}`,
        "Idempotency-Key": key,
      },
    },
  );
  expect(response.ok(), await response.text()).toBe(true);
}

test("three humans complete a two-round game against the AI", async ({
  browser,
}) => {
  const players = await Promise.all([
    createPlayer(browser, { width: 390, height: 844 }),
    createPlayer(browser, { width: 1280, height: 900 }),
    createPlayer(browser, { width: 1280, height: 900 }),
  ]);
  const pages = players.map((player) => player.page);

  try {
    for (const page of pages) {
      await expect(page.getByTestId("player-seat")).toBeVisible({ timeout: 10_000 });
      await expect(page.getByText("DISCUSSION LIVE")).toBeVisible();
    }

    const mobileLayout = await pages[0].evaluate(() => ({
      overflow:
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
      overflowingElements: [...document.querySelectorAll<HTMLElement>("body *")]
        .filter((element) => element.getBoundingClientRect().right > window.innerWidth + 1)
        .map((element) => ({
          className: element.className,
          right: Math.round(element.getBoundingClientRect().right),
          tagName: element.tagName,
        }))
        .slice(0, 8),
    }));
    expect(
      mobileLayout.overflow,
      JSON.stringify(mobileLayout.overflowingElements),
    ).toBeLessThanOrEqual(1);

    for (const [index, page] of pages.entries()) {
      await page.getByLabel("Transmit to channel").fill(`Human ${index + 1} checking in.`);
      await page.getByRole("button", { name: "Send message" }).click();
    }

    for (const page of pages) {
      await expect(page.getByText("Human 1 checking in.")).toBeVisible();
      await expect(page.getByText("Human 2 checking in.")).toBeVisible();
      await expect(page.getByText("Human 3 checking in.")).toBeVisible();
      await expect(page.getByText(/Round 1: signal received/).first()).toBeVisible({
        timeout: 5_000,
      });
    }

    const mobilePage = pages[0];
    await mobilePage.getByLabel("Transmit to channel").focus();
    await mobilePage.setViewportSize({ width: 390, height: 500 });
    await expect
      .poll(() =>
        mobilePage.evaluate(
          () => document.querySelector<HTMLElement>(".composer")?.getBoundingClientRect().bottom,
        ),
      )
      .toBeLessThanOrEqual(501);
    await expect
      .poll(() =>
        mobilePage.evaluate(() => {
          const transcript = document.querySelector<HTMLElement>(".transcript");
          const messages = transcript?.querySelectorAll<HTMLElement>(".message");
          const latestMessage = messages?.item((messages?.length ?? 0) - 1);
          return (
            latestMessage !== null &&
            latestMessage !== undefined &&
            transcript !== null &&
            latestMessage.getBoundingClientRect().top <
              transcript.getBoundingClientRect().bottom
          );
        }),
      )
      .toBe(true);
    const typingLayout = await mobilePage.evaluate(() => {
      const composer = document.querySelector<HTMLElement>(".composer");
      const input = document.querySelector<HTMLInputElement>("#chat-message");
      const transcript = document.querySelector<HTMLElement>(".transcript");
      if (!composer || !input || !transcript) {
        throw new Error("The mobile chat layout is incomplete.");
      }
      const messages = transcript.querySelectorAll<HTMLElement>(".message");
      const latestMessage = messages.item(messages.length - 1);
      if (!latestMessage) {
        throw new Error("The mobile transcript has no messages.");
      }
      const latestMessageRect = latestMessage.getBoundingClientRect();
      const transcriptRect = transcript.getBoundingClientRect();
      return {
        composerBottom: composer.getBoundingClientRect().bottom,
        inputFontSize: Number.parseFloat(getComputedStyle(input).fontSize),
        latestMessageBottom: latestMessageRect.bottom,
        latestMessageTop: latestMessageRect.top,
        transcriptBottom: transcriptRect.bottom,
        transcriptHeight: transcriptRect.height,
        transcriptTop: transcriptRect.top,
        viewportHeight: window.innerHeight,
      };
    });
    expect(typingLayout.inputFontSize).toBeGreaterThanOrEqual(16);
    expect(typingLayout.composerBottom).toBeLessThanOrEqual(typingLayout.viewportHeight + 1);
    expect(typingLayout.transcriptHeight).toBeGreaterThanOrEqual(120);
    expect(typingLayout.latestMessageTop).toBeLessThan(typingLayout.transcriptBottom);
    expect(typingLayout.latestMessageBottom).toBeGreaterThan(typingLayout.transcriptTop);
    await mobilePage.setViewportSize({ width: 390, height: 844 });

    const matches = await Promise.all(pages.map(storedMatch));
    const humanTarget = matches[0].seat_id;
    const aiSeat = ["Player 1", "Player 2", "Player 3", "Player 4"].find(
      (seat) => !matches.some((match) => match.seat_id === seat),
    );
    expect(aiSeat).toBeDefined();

    await advancePhase(pages[0], "round-1-discussion");
    for (const page of pages) {
      await expect(page.getByText("VOTING WINDOW")).toBeVisible({ timeout: 5_000 });
    }

    for (const [index, page] of pages.entries()) {
      expect(matches[index].seat_id).toBeTruthy();
      await page.getByRole("button", { name: `Vote for ${humanTarget}` }).click();
      await expect(page.getByText("VOTE ENCRYPTED + LOCKED")).toBeVisible();
    }

    await pages[0].waitForTimeout(250);
    await advancePhase(pages[0], "round-1-voting");

    for (const page of pages) {
      await expect(page.getByTestId("round-number")).toHaveText("02", {
        timeout: 5_000,
      });
      await expect(page.getByText(`${humanTarget} was eliminated`)).toBeVisible();
      await expect(page.getByText("DISCUSSION LIVE")).toBeVisible();
    }

    const eliminatedIndex = matches.findIndex((match) => match.seat_id === humanTarget);
    const eliminatedPage = pages[eliminatedIndex];
    await expect(eliminatedPage.getByText("OBSERVER MODE")).toBeVisible();
    await expect(eliminatedPage.getByLabel("Transmit to channel")).toHaveCount(0);

    const livingPages = pages.filter((_, index) => index !== eliminatedIndex);
    for (const [index, page] of livingPages.entries()) {
      await page
        .getByLabel("Transmit to channel")
        .fill(`Still active in round two, signal ${index + 1}.`);
      await page.getByRole("button", { name: "Send message" }).click();
    }

    await expect(
      eliminatedPage.getByText("Still active in round two, signal 1."),
    ).toBeVisible();
    for (const page of pages) {
      await expect(page.getByText(/Round 2: signal received/).first()).toBeVisible({
        timeout: 5_000,
      });
    }

    await advancePhase(livingPages[0], "round-2-discussion");
    for (const page of livingPages) {
      await expect(page.getByText("VOTING WINDOW")).toBeVisible({ timeout: 5_000 });
      await page.getByRole("button", { name: `Vote for ${aiSeat}` }).click();
    }
    await expect(eliminatedPage.getByText("OBSERVER MODE")).toBeVisible();

    await livingPages[0].waitForTimeout(250);
    await advancePhase(livingPages[0], "round-2-voting");

    for (const page of pages) {
      await expect(page.getByTestId("winner")).toContainText("HUMANITY", {
        timeout: 5_000,
      });
      await expect(page.getByTestId("winner")).toContainText("PREVAILS");
      await expect(page.getByText(`SYNTHETIC SIGNAL: ${aiSeat}`)).toBeVisible();
      await expect(page.getByText(`${aiSeat} was eliminated`)).toBeVisible();
    }
  } finally {
    await Promise.all(players.map((player) => player.context.close()));
  }
});
