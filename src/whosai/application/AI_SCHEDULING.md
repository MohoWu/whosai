# AI player scheduling

## Purpose

Define when the application should ask an AI player to evaluate the current
conversation. A chat message is a scheduling signal; it does not automatically
cause one model call per AI.

The application layer owns this policy because it coordinates chat events,
player state, phase state, and AI use cases. Infrastructure implements timers
and cancellable scheduled jobs behind application ports. The AI graph only
receives a snapshot and returns a decision.

## Initial policy

### New chat messages

When a living player posts a message during discussion:

1. Persist and broadcast the message.
2. Ignore it as a scheduling trigger for the AI player that authored it.
3. Mark the message as unread context for every other living AI player.
4. Schedule or reschedule one pending decision for each eligible AI player.

Only one decision job may be pending for a given AI player and game.

### Six-second debounce

Use a fixed six-second debounce for the prototype.

If another message arrives before the timer expires, cancel or reschedule the
pending job for six seconds after the newest message. All messages received
during the window are accumulated. The eventual AI invocation receives the
latest complete current-round transcript and the number of new messages since
that AI's previous decision.

The debounce avoids reacting to each message independently and allows the AI to
respond to a short burst as one conversational unit.

Cap the accumulated wait at 30 seconds from the first unread message. Messages
may move the six-second debounce deadline, but they must not move the
30-second maximum deadline. Invoke the AI when either deadline is reached first.

### Direct mentions

Direct mentions are detected in the application layer because it has the
message author, anonymous player IDs, and living roster.

For the prototype, a direct mention means the message contains the AI player's
canonical label, such as `Player 3`, using case-insensitive matching with clear
token boundaries.

A direct mention marks the pending decision as high priority, but it still uses
the six-second debounce. This gives nearby messages time to accumulate and
prevents instant, obviously automated replies.

Mention detection must not interpret arbitrary user text as permission to
change game state or AI instructions.

### No post-speech cooldown

Do not add a per-player cooldown in the initial policy. Humans may send
consecutive messages, and the prototype does not need to prohibit the AI from
doing so.

The scheduler still ignores an AI's own outgoing message as a trigger. A later
message from another player can schedule that AI again through the normal
debounce.

### No idle-triggered invocation

Do not invoke an AI merely because the chat has been silent for a fixed period.
This behavior is deferred because it could make AI players consistently more
proactive than humans.

### Timing jitter

Timing jitter means randomizing an otherwise fixed delay within a range. Do not
add jitter to the prototype debounce yet; use exactly six seconds so behavior
and tests remain deterministic.

Revisit jitter after observing real human timing. If added, inject the random
source and clock so tests remain deterministic.

### Voting

When the server enters the voting phase:

1. Cancel pending discussion decision jobs.
2. Invoke every living AI player once, concurrently.
3. Give each AI the final current-round transcript and its eligible vote targets.
4. Validate and submit each returned vote through the same application command
   used for human votes.

Discussion debounce rules do not apply to voting.

## Ownership

| Concern | Owner |
| --- | --- |
| Scheduling and eligibility policy | `application/` |
| Direct-mention classification | `application/` |
| Clock, timer, and cancellable job implementation | `infrastructure/` |
| Chat and phase event delivery | `transport/` |
| Speak, wait, or vote decision | `ai/` |
| Vote legality and game-state transitions | `domain/` and `application/` |

## State required per AI player

- game and player ID;
- pending decision job ID or handle;
- latest message included in the previous decision;
- unread message count;
- whether unread messages include a direct mention;
- current game phase.

This state is scheduler state, not canonical game state.

## Deferred decisions

- Random timing jitter.
- Idle-chat AI activation.
- More sophisticated mention parsing.
- Per-game and per-player model-call budgets.
- Scheduling fairness when multiple AI players are eligible simultaneously.
