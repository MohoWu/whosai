import {
  type CSSProperties,
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  LanguageProvider,
  LanguageSwitch,
} from "./i18n";
import type { Game, Match, RoundResult, Seat } from "./types";
import { useLanguage } from "./useLanguage";
import { type SessionError, useGameSession } from "./useGameSession";

function twoDigits(value: number): string {
  return value.toString().padStart(2, "0");
}

function useCountdown(deadline: string | null | undefined): string {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, []);

  if (!deadline) {
    return "--:--";
  }
  const remaining = Math.max(0, Math.ceil((new Date(deadline).getTime() - now) / 1000));
  return `${twoDigits(Math.floor(remaining / 60))}:${twoDigits(remaining % 60)}`;
}

interface GameViewport {
  height: number;
  offsetTop: number;
}

interface GameViewportProperties extends CSSProperties {
  "--game-viewport-height": string;
  "--game-viewport-offset-top": string;
}

function readGameViewport(): GameViewport {
  const viewport = window.visualViewport;
  return {
    height: Math.round(viewport?.height ?? window.innerHeight),
    offsetTop: Math.round(viewport?.offsetTop ?? 0),
  };
}

function useGameViewport(): GameViewport {
  const [viewport, setViewport] = useState(readGameViewport);

  useEffect(() => {
    const visualViewport = window.visualViewport;
    const updateViewport = () => setViewport(readGameViewport());

    window.addEventListener("resize", updateViewport);
    visualViewport?.addEventListener("resize", updateViewport);
    visualViewport?.addEventListener("scroll", updateViewport);
    return () => {
      window.removeEventListener("resize", updateViewport);
      visualViewport?.removeEventListener("resize", updateViewport);
      visualViewport?.removeEventListener("scroll", updateViewport);
    };
  }, []);

  return viewport;
}

function Logo() {
  const { t } = useLanguage();

  return (
    <div className="logo" aria-label={t("meta.title")}>
      <span>WHO&apos;S</span>
      <strong>AI?</strong>
    </div>
  );
}

function ErrorMessage({
  className = "",
  error,
}: {
  className?: string;
  error: SessionError | null;
}) {
  const { t } = useLanguage();
  if (!error) {
    return null;
  }
  return (
    <p className={`error-message ${className}`.trim()}>
      {t(`error.${error}`)}
    </p>
  );
}

function Lobby({
  error,
  joining,
  match,
  onJoin,
}: {
  error: SessionError | null;
  joining: boolean;
  match: Match | null;
  onJoin: () => Promise<void>;
}) {
  const { t } = useLanguage();
  const queued = match?.status === "waiting";

  return (
    <main className="landing-shell">
      <LanguageSwitch className="language-switch-overlay" />
      <div className="landing-grid" aria-hidden="true" />
      <section className="lobby-card" aria-labelledby="game-title">
        <div className="corner-code" aria-hidden="true">
          SYS.2049 / NODE 7
        </div>
        <p className="eyebrow">{t("lobby.eyebrow")}</p>
        <h1 id="game-title">
          WHO&apos;S
          <span>AI?</span>
        </h1>
        <p className="premise">
          {t("lobby.premiseLine1")}
          <br />
          {t("lobby.premiseLine2")}
        </p>

        {queued ? (
          <div className="queue-panel" role="status" aria-live="polite">
            <div className="radar" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
            <div>
              <strong>{t("lobby.linkSent")}</strong>
              <span>{t("lobby.waiting")}</span>
            </div>
          </div>
        ) : (
          <button
            className="primary-button join-button"
            type="button"
            disabled={joining}
            onClick={() => void onJoin()}
          >
            <span>{joining ? t("lobby.transmitting") : t("lobby.enter")}</span>
            <b aria-hidden="true">↗</b>
          </button>
        )}

        <ErrorMessage error={error} />

        <div className="lobby-meta" aria-label={t("lobby.details")}>
          <span>{t("lobby.humans")}</span>
          <span>{t("lobby.unknown")}</span>
          <span>{t("lobby.rounds")}</span>
        </div>
      </section>
      <p className="landing-footnote">{t("lobby.footnote")}</p>
    </main>
  );
}

function Roster({
  game,
  playerSeatId,
}: {
  game: Game;
  playerSeatId: string | null;
}) {
  const { seatName, t } = useLanguage();
  const livingCount = game.seats.filter((seat) => seat.alive).length;

  return (
    <aside className="roster-panel panel" aria-labelledby="roster-heading">
      <div className="panel-heading">
        <div>
          <span className="section-index">01</span>
          <h2 id="roster-heading">{t("roster.heading")}</h2>
        </div>
        <span className="count-chip">
          {livingCount}/{game.seats.length}
        </span>
      </div>
      <ul className="roster-list">
        {game.seats.map((seat, index) => {
          const isPlayer = seat.id === playerSeatId;
          return (
            <li
              className={`${seat.alive ? "is-alive" : "is-eliminated"} ${
                isPlayer ? "is-player" : ""
              }`}
              key={seat.id}
            >
              <span className="avatar" aria-hidden="true">
                {twoDigits(index + 1)}
              </span>
              <span className="seat-copy">
                <strong data-testid={isPlayer ? "player-seat" : undefined}>
                  {seatName(seat.id)}
                </strong>
                <small>
                  {seat.alive ? t("roster.active") : t("roster.disconnected")}
                  {isPlayer ? ` / ${t("roster.you")}` : ""}
                </small>
              </span>
              <span
                className="life-dot"
                aria-label={
                  seat.alive ? t("roster.alive") : t("roster.eliminated")
                }
              />
            </li>
          );
        })}
      </ul>
      <div className="roster-footer">
        <span>{t("roster.identities")}</span>
        <strong>
          {game.phase === "finished" ? t("roster.decrypted") : t("roster.encrypted")}
        </strong>
      </div>
    </aside>
  );
}

function RoundReport({ result }: { result: RoundResult }) {
  const { seatName, t } = useLanguage();

  return (
    <section className="round-report" aria-labelledby={`round-${result.round_number}-result`}>
      <div className="report-kicker">
        {t("round.result", { round: twoDigits(result.round_number) })}
      </div>
      <h3 id={`round-${result.round_number}-result`}>
        {result.eliminated_id ? (
          <>
            <span>{seatName(result.eliminated_id)}</span>
            {t("round.wasEliminated")}
          </>
        ) : (
          t("round.noConsensus")
        )}
      </h3>
      <div className="vote-trace" aria-label={t("round.votingRecord")}>
        {result.votes.length ? (
          result.votes.map((vote) => (
            <div key={vote.voter_id}>
              <span>{seatName(vote.voter_id)}</span>
              <b aria-hidden="true">→</b>
              <strong>{seatName(vote.target_id)}</strong>
            </div>
          ))
        ) : (
          <p>{t("round.noVotes")}</p>
        )}
      </div>
    </section>
  );
}

function Transcript({
  game,
  playerSeatId,
  viewportHeight,
}: {
  game: Game;
  playerSeatId: string | null;
  viewportHeight: number;
}) {
  const { language, seatName, t } = useLanguage();
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const transcript = transcriptRef.current;
    if (transcript) {
      transcript.scrollTop = transcript.scrollHeight;
    }
  }, [game.messages, viewportHeight]);

  return (
    <div
      className="transcript"
      ref={transcriptRef}
      aria-live="polite"
      aria-label={t("transcript.label")}
    >
      {game.messages.length === 0 ? (
        <div className="empty-transcript">
          <span aria-hidden="true">&gt;_</span>
          <p>{t("transcript.empty")}</p>
        </div>
      ) : (
        game.messages.map((message) => {
          const ownMessage = message.seat_id === playerSeatId;
          return (
            <article className={`message ${ownMessage ? "own-message" : ""}`} key={message.id}>
              <div className="message-meta">
                <strong>{seatName(message.seat_id)}</strong>
                <time dateTime={message.sent_at}>
                  {new Date(message.sent_at).toLocaleTimeString(language, {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
              </div>
              <p>{message.content}</p>
            </article>
          );
        })
      )}
    </div>
  );
}

function Composer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (message: string) => Promise<void>;
}) {
  const { t } = useLanguage();
  const [message, setMessage] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const content = message.trim();
    if (!content || disabled) {
      return;
    }
    await onSend(content);
    setMessage("");
  };

  return (
    <form className="composer" onSubmit={(event) => void submit(event)}>
      <label htmlFor="chat-message">{t("composer.label")}</label>
      <div>
        <span aria-hidden="true">&gt;</span>
        <input
          id="chat-message"
          maxLength={500}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={t("composer.placeholder")}
          disabled={disabled}
          autoComplete="off"
          enterKeyHint="send"
        />
        <button
          type="submit"
          disabled={disabled || !message.trim()}
          aria-label={t("composer.sendLabel")}
        >
          {t("composer.send")}
          <b aria-hidden="true">↗</b>
        </button>
      </div>
    </form>
  );
}

function VotingControls({
  actionPending,
  game,
  ownSeat,
  onVote,
  voted,
}: {
  actionPending: boolean;
  game: Game;
  ownSeat: Seat | undefined;
  onVote: (target: string) => Promise<void>;
  voted: boolean;
}) {
  const { seatName, t } = useLanguage();

  if (!ownSeat?.alive) {
    return (
      <div className="spectator-notice" role="status">
        <strong>{t("observer.title")}</strong>
        <span>{t("observer.vote")}</span>
      </div>
    );
  }

  if (voted) {
    return (
      <div className="vote-locked" role="status">
        <strong>{t("vote.locked")}</strong>
        <span>{t("vote.waiting")}</span>
      </div>
    );
  }

  return (
    <div className="voting-controls">
      <div className="voting-instruction">
        <strong>{t("vote.instruction")}</strong>
        <span>{t("vote.final")}</span>
      </div>
      <div className="vote-grid">
        {game.seats
          .filter((seat) => seat.alive)
          .map((seat) => (
            <button
              type="button"
              key={seat.id}
              disabled={actionPending}
              onClick={() => void onVote(seat.id)}
              aria-label={t("vote.for", { seat: seatName(seat.id) })}
            >
              <span>
                {seatName(seat.id)}
                {seat.id === ownSeat.id ? ` / ${t("roster.you")}` : ""}
              </span>
              <b>{t("vote.action")}</b>
            </button>
          ))}
      </div>
    </div>
  );
}

function GameHeader({ game, onLeave }: { game: Game; onLeave: () => void }) {
  const { language, t } = useLanguage();
  const countdown = useCountdown(game.phase_deadline);
  const phaseName =
    game.phase === "voting" ? t("header.voting") : t("header.discussion");

  return (
    <header className="game-header">
      <Logo />
      <div className="round-status">
        <span>{t("header.round")}</span>
        <strong
          data-prefix={language === "zh-CN" ? "回" : "R"}
          data-testid="round-number"
        >
          {twoDigits(game.round_number)}
        </strong>
      </div>
      <div className={`phase-status phase-${game.phase}`} role="status" aria-live="polite">
        <i aria-hidden="true" />
        <span>{phaseName}</span>
      </div>
      <div
        className="countdown"
        aria-label={t("header.remainingLabel", { time: countdown })}
      >
        <span>{t("header.timeRemaining")}</span>
        <strong>{countdown}</strong>
      </div>
      <LanguageSwitch />
      <button className="leave-button" type="button" onClick={onLeave}>
        {t("header.exit")}
      </button>
    </header>
  );
}

function GameView({
  actionPending,
  error,
  game,
  match,
  onLeave,
  onSend,
  onVote,
  votedRound,
}: {
  actionPending: boolean;
  error: SessionError | null;
  game: Game;
  match: Match;
  onLeave: () => void;
  onSend: (message: string) => Promise<void>;
  onVote: (target: string) => Promise<void>;
  votedRound: number | null;
}) {
  const { seatName, t } = useLanguage();
  const viewport = useGameViewport();
  const ownSeat = game.seats.find((seat) => seat.id === match.seat_id);
  const latestResult = game.round_results.at(-1);
  const showRoundReport =
    latestResult !== undefined && latestResult.round_number === game.round_number - 1;
  const viewportProperties: GameViewportProperties = {
    "--game-viewport-height": `${viewport.height}px`,
    "--game-viewport-offset-top": `${viewport.offsetTop}px`,
  };

  return (
    <main className="game-shell" style={viewportProperties}>
      <GameHeader game={game} onLeave={onLeave} />
      <div className="game-layout">
        <Roster game={game} playerSeatId={match.seat_id} />
        <section className="channel-panel panel" aria-labelledby="channel-heading">
          <div className="panel-heading channel-heading">
            <div>
              <span className="section-index">02</span>
              <h2 id="channel-heading">{t("channel.heading")}</h2>
            </div>
            <span className="encrypted-chip">{t("channel.encrypted")}</span>
          </div>

          {showRoundReport ? <RoundReport result={latestResult} /> : null}
          <Transcript
            game={game}
            playerSeatId={match.seat_id}
            viewportHeight={viewport.height}
          />

          {game.phase === "discussion" ? (
            ownSeat?.alive ? (
              <Composer disabled={actionPending} onSend={onSend} />
            ) : (
              <div className="spectator-notice" role="status">
                <strong>{t("observer.title")}</strong>
                <span>{t("observer.chat")}</span>
              </div>
            )
          ) : (
            <VotingControls
              actionPending={actionPending}
              game={game}
              ownSeat={ownSeat}
              onVote={onVote}
              voted={votedRound === game.round_number}
            />
          )}
          <ErrorMessage className="game-error" error={error} />
        </section>
        <aside className="intel-panel panel" aria-labelledby="intel-heading">
          <div className="panel-heading">
            <div>
              <span className="section-index">03</span>
              <h2 id="intel-heading">{t("intel.heading")}</h2>
            </div>
          </div>
          <div className="intel-block">
            <span>{t("intel.objective")}</span>
            <p>{t("intel.objectiveCopy")}</p>
          </div>
          <div className="intel-block">
            <span>{t("intel.currentPhase")}</span>
            <p>
              {game.phase === "discussion"
                ? t("intel.discussion")
                : t("intel.voting")}
            </p>
          </div>
          <div className="signal-graphic" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
          <div className="your-id">
            <span>{t("intel.callsign")}</span>
            <strong>{match.seat_id ? seatName(match.seat_id) : ""}</strong>
          </div>
        </aside>
      </div>
    </main>
  );
}

function FinalResults({
  game,
  onLeave,
}: {
  game: Game;
  onLeave: () => void;
}) {
  const { language, seatName, t } = useLanguage();
  const humanWin = game.winner === "humans";
  const aiSeats = useMemo(
    () => game.seats.filter((seat) => seat.role === "ai"),
    [game.seats],
  );

  return (
    <main className="results-shell">
      <div className={`result-glow ${humanWin ? "human-glow" : "ai-glow"}`} />
      <header>
        <Logo />
        <div className="results-header-meta">
          <span>{t("results.terminated")}</span>
          <LanguageSwitch />
        </div>
      </header>
      <section className="result-hero" aria-labelledby="result-title">
        <p>{t("results.verdict")}</p>
        <h1 id="result-title" data-testid="winner">
          {humanWin ? (
            <>
              {t("results.humanity")}
              <span>{t("results.prevails")}</span>
            </>
          ) : (
            <>
              {t("results.system")}
              <span>{t("results.wins")}</span>
            </>
          )}
        </h1>
        <p className="result-summary">
          {humanWin ? t("results.humanSummary") : t("results.aiSummary")}
        </p>
      </section>

      <section className="identity-reveal" aria-labelledby="identity-heading">
        <div className="panel-heading">
          <div>
            <span className="section-index">01</span>
            <h2 id="identity-heading">{t("results.identityReveal")}</h2>
          </div>
        </div>
        <div className="identity-grid">
          {game.seats.map((seat, index) => (
            <article
              className={`${seat.role === "ai" ? "ai-identity" : ""} ${
                seat.alive ? "" : "identity-eliminated"
              }`}
              key={seat.id}
            >
              <span>{twoDigits(index + 1)}</span>
              <strong>{seatName(seat.id)}</strong>
              <b>
                {seat.role === "ai" ? t("results.synthetic") : t("results.human")}
              </b>
              <small>
                {seat.alive ? t("results.activeAtEnd") : t("results.eliminated")}
              </small>
            </article>
          ))}
        </div>
      </section>

      <section className="round-history" aria-labelledby="history-heading">
        <div className="panel-heading">
          <div>
            <span className="section-index">02</span>
            <h2 id="history-heading">{t("results.voteArchive")}</h2>
          </div>
        </div>
        {game.round_results.map((result) => (
          <RoundReport key={result.round_number} result={result} />
        ))}
      </section>

      <footer className="results-footer">
        <span>
          {t("results.syntheticSignal")}:{" "}
          <strong>
            {aiSeats
              .map((seat) => seatName(seat.id))
              .join(language === "zh-CN" ? "、" : ", ")}
          </strong>
        </span>
        <button className="primary-button" type="button" onClick={onLeave}>
          {t("results.return")}
        </button>
      </footer>
    </main>
  );
}

function AppContent() {
  const session = useGameSession();
  const { t } = useLanguage();

  if (!session.match || session.match.status === "waiting") {
    return (
      <Lobby
        error={session.error}
        joining={session.joining}
        match={session.match}
        onJoin={session.join}
      />
    );
  }

  if (!session.game) {
    return (
      <main className="loading-shell" role="status">
        <LanguageSwitch className="language-switch-overlay" />
        <Logo />
        <div className="loading-line" aria-hidden="true" />
        <strong>{t("loading.channel")}</strong>
        <ErrorMessage error={session.error} />
        {session.error ? (
          <button
            className="primary-button loading-return"
            type="button"
            onClick={session.leave}
          >
            {t("results.return")}
          </button>
        ) : null}
      </main>
    );
  }

  if (session.game.phase === "finished") {
    return <FinalResults game={session.game} onLeave={session.leave} />;
  }

  return (
    <GameView
      actionPending={session.actionPending}
      error={session.error}
      game={session.game}
      match={session.match}
      onLeave={session.leave}
      onSend={session.postMessage}
      onVote={session.vote}
      votedRound={session.votedRound}
    />
  );
}

export function App() {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  );
}
