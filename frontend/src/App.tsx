import {
  type CSSProperties,
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { Game, Match, RoundResult, Seat } from "./types";
import { useGameSession } from "./useGameSession";

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
  return (
    <div className="logo" aria-label="Who's AI?">
      <span>WHO&apos;S</span>
      <strong>AI?</strong>
    </div>
  );
}

function Lobby({
  error,
  joining,
  match,
  onJoin,
}: {
  error: string | null;
  joining: boolean;
  match: Match | null;
  onJoin: () => Promise<void>;
}) {
  const queued = match?.status === "waiting";

  return (
    <main className="landing-shell">
      <div className="landing-grid" aria-hidden="true" />
      <section className="lobby-card" aria-labelledby="game-title">
        <div className="corner-code" aria-hidden="true">
          SYS.2049 / NODE 7
        </div>
        <p className="eyebrow">ANONYMOUS SOCIAL DEDUCTION</p>
        <h1 id="game-title">
          WHO&apos;S
          <span>AI?</span>
        </h1>
        <p className="premise">
          Four voices enter the channel.
          <br />
          One of them was never human.
        </p>

        {queued ? (
          <div className="queue-panel" role="status" aria-live="polite">
            <div className="radar" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
            <div>
              <strong>LINK REQUEST SENT</strong>
              <span>Waiting for a three-human cell...</span>
            </div>
          </div>
        ) : (
          <button
            className="primary-button join-button"
            type="button"
            disabled={joining}
            onClick={() => void onJoin()}
          >
            <span>{joining ? "TRANSMITTING..." : "ENTER THE NETWORK"}</span>
            <b aria-hidden="true">↗</b>
          </button>
        )}

        {error ? <p className="error-message">{error}</p> : null}

        <div className="lobby-meta" aria-label="Game details">
          <span>03 HUMANS</span>
          <span>01 UNKNOWN</span>
          <span>05:00 ROUNDS</span>
        </div>
      </section>
      <p className="landing-footnote">TRUST IS A VULNERABILITY</p>
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
  const livingCount = game.seats.filter((seat) => seat.alive).length;

  return (
    <aside className="roster-panel panel" aria-labelledby="roster-heading">
      <div className="panel-heading">
        <div>
          <span className="section-index">01</span>
          <h2 id="roster-heading">ACTIVE NODES</h2>
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
                <strong data-testid={isPlayer ? "player-seat" : undefined}>{seat.id}</strong>
                <small>
                  {seat.alive ? "SIGNAL ACTIVE" : "DISCONNECTED"}
                  {isPlayer ? " / YOU" : ""}
                </small>
              </span>
              <span className="life-dot" aria-label={seat.alive ? "alive" : "eliminated"} />
            </li>
          );
        })}
      </ul>
      <div className="roster-footer">
        <span>IDENTITIES</span>
        <strong>{game.phase === "finished" ? "DECRYPTED" : "ENCRYPTED"}</strong>
      </div>
    </aside>
  );
}

function RoundReport({ result }: { result: RoundResult }) {
  return (
    <section className="round-report" aria-labelledby={`round-${result.round_number}-result`}>
      <div className="report-kicker">ROUND {twoDigits(result.round_number)} / VOTE RESULT</div>
      <h3 id={`round-${result.round_number}-result`}>
        {result.eliminated_id ? (
          <>
            <span>{result.eliminated_id}</span> was eliminated
          </>
        ) : (
          "No consensus. No elimination."
        )}
      </h3>
      <div className="vote-trace" aria-label="Voting record">
        {result.votes.length ? (
          result.votes.map((vote) => (
            <div key={vote.voter_id}>
              <span>{vote.voter_id}</span>
              <b aria-hidden="true">→</b>
              <strong>{vote.target_id}</strong>
            </div>
          ))
        ) : (
          <p>No votes were recorded.</p>
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
      aria-label="Discussion transcript"
    >
      {game.messages.length === 0 ? (
        <div className="empty-transcript">
          <span aria-hidden="true">&gt;_</span>
          <p>Channel open. Say something human.</p>
        </div>
      ) : (
        game.messages.map((message) => {
          const ownMessage = message.seat_id === playerSeatId;
          return (
            <article className={`message ${ownMessage ? "own-message" : ""}`} key={message.id}>
              <div className="message-meta">
                <strong>{message.seat_id}</strong>
                <time dateTime={message.sent_at}>
                  {new Date(message.sent_at).toLocaleTimeString([], {
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
      <label htmlFor="chat-message">Transmit to channel</label>
      <div>
        <span aria-hidden="true">&gt;</span>
        <input
          id="chat-message"
          maxLength={500}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="TYPE A MESSAGE..."
          disabled={disabled}
          autoComplete="off"
          enterKeyHint="send"
        />
        <button
          type="submit"
          disabled={disabled || !message.trim()}
          aria-label="Send message"
        >
          SEND
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
  if (!ownSeat?.alive) {
    return (
      <div className="spectator-notice" role="status">
        <strong>OBSERVER MODE</strong>
        <span>Your signal was cut. You can watch, but cannot vote.</span>
      </div>
    );
  }

  if (voted) {
    return (
      <div className="vote-locked" role="status">
        <strong>VOTE ENCRYPTED + LOCKED</strong>
        <span>Waiting for remaining nodes or the server deadline.</span>
      </div>
    );
  }

  return (
    <div className="voting-controls">
      <div className="voting-instruction">
        <strong>SELECT A SIGNAL TO TERMINATE</strong>
        <span>Your first vote is final.</span>
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
              aria-label={`Vote for ${seat.id}`}
            >
              <span>
                {seat.id}
                {seat.id === ownSeat.id ? " / YOU" : ""}
              </span>
              <b>VOTE</b>
            </button>
          ))}
      </div>
    </div>
  );
}

function GameHeader({ game, onLeave }: { game: Game; onLeave: () => void }) {
  const countdown = useCountdown(game.phase_deadline);
  const phaseName = game.phase === "voting" ? "VOTING WINDOW" : "DISCUSSION LIVE";

  return (
    <header className="game-header">
      <Logo />
      <div className="round-status">
        <span>ROUND</span>
        <strong data-testid="round-number">{twoDigits(game.round_number)}</strong>
      </div>
      <div className={`phase-status phase-${game.phase}`} role="status" aria-live="polite">
        <i aria-hidden="true" />
        <span>{phaseName}</span>
      </div>
      <div className="countdown" aria-label={`${countdown} remaining`}>
        <span>TIME REMAINING</span>
        <strong>{countdown}</strong>
      </div>
      <button className="leave-button" type="button" onClick={onLeave}>
        EXIT
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
  error: string | null;
  game: Game;
  match: Match;
  onLeave: () => void;
  onSend: (message: string) => Promise<void>;
  onVote: (target: string) => Promise<void>;
  votedRound: number | null;
}) {
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
              <h2 id="channel-heading">OPEN CHANNEL</h2>
            </div>
            <span className="encrypted-chip">● ENCRYPTED</span>
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
                <strong>OBSERVER MODE</strong>
                <span>Your signal was cut. You can watch, but cannot chat.</span>
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
          {error ? <p className="error-message game-error">{error}</p> : null}
        </section>
        <aside className="intel-panel panel" aria-labelledby="intel-heading">
          <div className="panel-heading">
            <div>
              <span className="section-index">03</span>
              <h2 id="intel-heading">MISSION INTEL</h2>
            </div>
          </div>
          <div className="intel-block">
            <span>OBJECTIVE</span>
            <p>Identify and eliminate the synthetic signal before it reaches parity.</p>
          </div>
          <div className="intel-block">
            <span>CURRENT PHASE</span>
            <p>
              {game.phase === "discussion"
                ? "Interrogate the channel. Every hesitation is data."
                : "Commit one final vote before the channel closes."}
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
            <span>YOUR CALLSIGN</span>
            <strong>{match.seat_id}</strong>
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
        <span>SESSION TERMINATED / IDENTITIES DECRYPTED</span>
      </header>
      <section className="result-hero" aria-labelledby="result-title">
        <p>FINAL VERDICT</p>
        <h1 id="result-title" data-testid="winner">
          {humanWin ? (
            <>
              HUMANITY
              <span>PREVAILS</span>
            </>
          ) : (
            <>
              THE SYSTEM
              <span>WINS</span>
            </>
          )}
        </h1>
        <p className="result-summary">
          {humanWin
            ? "The synthetic signal was found and disconnected."
            : "The synthetic signal reached parity. Trust collapsed."}
        </p>
      </section>

      <section className="identity-reveal" aria-labelledby="identity-heading">
        <div className="panel-heading">
          <div>
            <span className="section-index">01</span>
            <h2 id="identity-heading">IDENTITY REVEAL</h2>
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
              <strong>{seat.id}</strong>
              <b>{seat.role === "ai" ? "SYNTHETIC" : "HUMAN"}</b>
              <small>{seat.alive ? "ACTIVE AT END" : "ELIMINATED"}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="round-history" aria-labelledby="history-heading">
        <div className="panel-heading">
          <div>
            <span className="section-index">02</span>
            <h2 id="history-heading">VOTE ARCHIVE</h2>
          </div>
        </div>
        {game.round_results.map((result) => (
          <RoundReport key={result.round_number} result={result} />
        ))}
      </section>

      <footer className="results-footer">
        <span>
          SYNTHETIC SIGNAL: <strong>{aiSeats.map((seat) => seat.id).join(", ")}</strong>
        </span>
        <button className="primary-button" type="button" onClick={onLeave}>
          RETURN TO NETWORK
        </button>
      </footer>
    </main>
  );
}

export function App() {
  const session = useGameSession();

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
        <Logo />
        <div className="loading-line" aria-hidden="true" />
        <strong>ESTABLISHING SECURE CHANNEL...</strong>
        {session.error ? <p className="error-message">{session.error}</p> : null}
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
