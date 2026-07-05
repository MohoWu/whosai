from datetime import UTC, datetime, timedelta

from whosai.domain.game import (
    GameConfig,
    Phase,
    Role,
    Winner,
    advance_game,
    cast_vote,
    create_four_seat_game,
    post_chat,
    public_game_state,
)


def test_four_seat_game_starts_discussion_with_exactly_one_ai() -> None:
    now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    config = GameConfig()

    game = create_four_seat_game(
        game_id="game-1",
        ai_seat_id="Player 3",
        now=now,
        config=config,
    )

    assert config.discussion_duration == timedelta(seconds=300)
    assert [seat.id for seat in game.seats] == [
        "Player 1",
        "Player 2",
        "Player 3",
        "Player 4",
    ]
    assert [seat.id for seat in game.seats if seat.role is Role.AI] == ["Player 3"]
    assert game.phase is Phase.DISCUSSION
    assert game.round_number == 1
    assert game.phase_deadline == now + config.discussion_duration


def test_public_game_state_hides_roles_during_play() -> None:
    game = create_four_seat_game(
        game_id="game-1",
        ai_seat_id="Player 3",
        now=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
    )

    snapshot = public_game_state(game)

    assert [seat.id for seat in snapshot.seats] == [
        "Player 1",
        "Player 2",
        "Player 3",
        "Player 4",
    ]
    assert all(seat.role is None for seat in snapshot.seats)


def test_discussion_deadline_opens_voting() -> None:
    discussion_started_at = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    config = GameConfig()
    game = create_four_seat_game(
        game_id="game-1",
        ai_seat_id="Player 3",
        now=discussion_started_at,
        config=config,
    )
    deadline = discussion_started_at + config.discussion_duration

    advanced = advance_game(game, now=deadline)

    assert advanced.phase is Phase.VOTING
    assert advanced.phase_deadline == deadline + config.voting_duration


def test_living_player_can_chat_during_discussion() -> None:
    now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    game = create_four_seat_game(
        game_id="game-1",
        ai_seat_id="Player 3",
        now=now,
    )

    updated = post_chat(
        game,
        message_id="message-1",
        seat_id="Player 1",
        content="  Player 3 feels suspicious.  ",
        now=now + timedelta(seconds=5),
    )

    assert [(message.seat_id, message.content) for message in updated.messages] == [
        ("Player 1", "Player 3 feels suspicious.")
    ]
    assert public_game_state(updated).messages == updated.messages


def test_living_player_can_vote_for_their_own_seat() -> None:
    now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    config = GameConfig()
    game = create_four_seat_game(
        game_id="game-1",
        ai_seat_id="Player 3",
        now=now,
        config=config,
    )
    game = advance_game(game, now=now + config.discussion_duration)

    updated = cast_vote(game, voter_id="Player 1", target_id="Player 1")

    assert updated.votes[0].voter_id == "Player 1"
    assert updated.votes[0].target_id == "Player 1"


def test_eliminating_the_ai_ends_the_game_with_roles_revealed() -> None:
    started_at = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    config = GameConfig()
    game = create_four_seat_game(
        game_id="game-1",
        ai_seat_id="Player 3",
        now=started_at,
        config=config,
    )
    voting_started_at = started_at + config.discussion_duration
    game = advance_game(game, now=voting_started_at)
    for voter_id in ("Player 1", "Player 2", "Player 4"):
        game = cast_vote(game, voter_id=voter_id, target_id="Player 3")

    finished = advance_game(game, now=voting_started_at + config.voting_duration)

    assert finished.phase is Phase.FINISHED
    assert finished.winner is Winner.HUMANS
    assert finished.phase_deadline is None
    assert next(seat for seat in finished.seats if seat.id == "Player 3").alive is False
    assert finished.round_results[0].round_number == 1
    assert finished.round_results[0].eliminated_id == "Player 3"
    assert [vote.voter_id for vote in finished.round_results[0].votes] == [
        "Player 1",
        "Player 2",
        "Player 4",
    ]
    assert [seat.role for seat in public_game_state(finished).seats] == [
        Role.HUMAN,
        Role.HUMAN,
        Role.AI,
        Role.HUMAN,
    ]


def test_ai_wins_when_an_elimination_reaches_parity() -> None:
    now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    config = GameConfig()
    game = create_four_seat_game(
        game_id="game-1",
        ai_seat_id="Player 4",
        now=now,
        config=config,
    )

    now += config.discussion_duration
    game = advance_game(game, now=now)
    for voter_id in ("Player 1", "Player 2", "Player 4"):
        game = cast_vote(game, voter_id=voter_id, target_id="Player 3")
    now += config.voting_duration
    game = advance_game(game, now=now)

    assert game.phase is Phase.DISCUSSION
    assert game.round_number == 2
    assert game.round_results[0].eliminated_id == "Player 3"

    now += config.discussion_duration
    game = advance_game(game, now=now)
    for voter_id in ("Player 1", "Player 4"):
        game = cast_vote(game, voter_id=voter_id, target_id="Player 2")
    now += config.voting_duration
    finished = advance_game(game, now=now)

    assert finished.phase is Phase.FINISHED
    assert finished.winner is Winner.AI
