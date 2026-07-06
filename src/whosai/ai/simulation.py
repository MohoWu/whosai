import argparse
import asyncio
import os
from collections.abc import Sequence
from datetime import UTC, datetime

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict

from whosai.ai.graph import (
    AIPlayerState,
    DecisionModel,
    build_ai_player_graph,
    with_decision_schema,
)
from whosai.ai.models import AIPlayerDecision, ChatMessage, GamePhase
from whosai.ai.providers import build_deepseek_chat_model
from whosai.domain.game import PlayerRoundBrief
from whosai.domain.keywords import LocalizedText

DEFAULT_PLAYERS = ("Player 1", "Player 2", "Player 3", "Player 4")
SEED_MESSAGE = ChatMessage(player_id="Player 1", content="how's everyone doing?")
SIMULATION_ROUND_BRIEF = PlayerRoundBrief(
    category=LocalizedText(en="Public places", zh_cn="公共场所"),
    keyword=LocalizedText(en="airport", zh_cn="机场"),
)


class SimulatedTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch: int
    player_id: str
    phase: GamePhase
    decision: AIPlayerDecision


class SimulationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: str
    discussion_batches: int
    messages: list[ChatMessage]
    turns: list[SimulatedTurn]
    votes: dict[str, str]


async def _invoke_player(
    *,
    graph: CompiledStateGraph[AIPlayerState],
    game_id: str,
    player_id: str,
    round_number: int,
    phase: GamePhase,
    chat_history: list[ChatMessage],
    eligible_vote_targets: list[str],
    batch: int,
    new_messages_since_last_turn: int,
) -> AIPlayerDecision:
    state: AIPlayerState = {
        "game_id": game_id,
        "player_id": player_id,
        "round_number": round_number,
        "turn_number": batch,
        "new_messages_since_last_turn": new_messages_since_last_turn,
        "phase": phase,
        "chat_history": chat_history,
        "eligible_vote_targets": eligible_vote_targets,
        "round_brief": SIMULATION_ROUND_BRIEF,
    }
    config: RunnableConfig = {
        "tags": ["ai-game-simulation", f"game:{game_id}", f"phase:{phase}"],
        "metadata": {
            "game_id": game_id,
            "player_id": player_id,
            "round_number": round_number,
            "phase": phase,
            "batch": batch,
            "new_messages_since_last_turn": new_messages_since_last_turn,
            "simulation": True,
        },
    }
    result = await graph.ainvoke(state, config=config)
    return AIPlayerDecision.model_validate(result["decision"])


async def simulate_game(
    decision_model: DecisionModel,
    *,
    game_id: str,
    players: Sequence[str] = DEFAULT_PLAYERS,
    message_threshold: int = 20,
    max_discussion_batches: int = 12,
) -> SimulationResult:
    """Run concurrent discussion batches until messages exceed the threshold, then vote."""
    if len(players) != 4:
        raise ValueError("This simulation requires exactly four players.")
    if len(set(players)) != len(players):
        raise ValueError("Player IDs must be unique.")

    graph = build_ai_player_graph(decision_model)
    messages = [SEED_MESSAGE]
    turns: list[SimulatedTurn] = []
    batch = 0
    new_messages_since_last_turn = 1

    while len(messages) <= message_threshold and batch < max_discussion_batches:
        batch += 1
        snapshot = list(messages)
        decisions = await asyncio.gather(
            *(
                _invoke_player(
                    graph=graph,
                    game_id=game_id,
                    player_id=player_id,
                    round_number=1,
                    phase="discussion",
                    chat_history=snapshot,
                    eligible_vote_targets=[],
                    batch=batch,
                    new_messages_since_last_turn=new_messages_since_last_turn,
                )
                for player_id in players
            )
        )

        new_messages_since_last_turn = 0
        for player_id, decision in zip(players, decisions, strict=True):
            turns.append(
                SimulatedTurn(
                    batch=batch,
                    player_id=player_id,
                    phase="discussion",
                    decision=decision,
                )
            )
            if decision.action == "speak":
                if decision.response is None:
                    raise AssertionError("A speak decision must contain a response.")
                messages.append(ChatMessage(player_id=player_id, content=decision.response))
                new_messages_since_last_turn += 1

    if len(messages) <= message_threshold:
        raise RuntimeError(
            f"Discussion produced {len(messages)} messages after "
            f"{max_discussion_batches} batches; expected more than {message_threshold}."
        )

    vote_decisions = await asyncio.gather(
        *(
            _invoke_player(
                graph=graph,
                game_id=game_id,
                player_id=player_id,
                round_number=1,
                phase="voting",
                chat_history=list(messages),
                eligible_vote_targets=[
                    candidate for candidate in players if candidate != player_id
                ],
                batch=batch + 1,
                new_messages_since_last_turn=new_messages_since_last_turn,
            )
            for player_id in players
        )
    )

    votes: dict[str, str] = {}
    for player_id, decision in zip(players, vote_decisions, strict=True):
        eligible_targets = {candidate for candidate in players if candidate != player_id}
        if decision.action != "vote" or decision.target_player_id not in eligible_targets:
            raise ValueError(
                f"{player_id} returned an invalid vote target: {decision.target_player_id!r}."
            )
        votes[player_id] = decision.target_player_id
        turns.append(
            SimulatedTurn(
                batch=batch + 1,
                player_id=player_id,
                phase="voting",
                decision=decision,
            )
        )

    return SimulationResult(
        game_id=game_id,
        discussion_batches=batch,
        messages=messages,
        turns=turns,
        votes=votes,
    )


def print_simulation(result: SimulationResult) -> None:
    print(f"Simulation: {result.game_id}")
    print(f"Discussion batches: {result.discussion_batches}")
    print(f"Total discussion messages: {len(result.messages)}")
    print()
    print("Transcript")
    for index, message in enumerate(result.messages):
        print(f"{index:02d} | {message.player_id}: {message.content}")

    print()
    print("Wait decisions")
    wait_turns = [turn for turn in result.turns if turn.decision.action == "wait"]
    if not wait_turns:
        print("(none)")
    for turn in wait_turns:
        print(f"batch {turn.batch} | {turn.player_id}: {turn.decision.decision_summary}")

    print()
    print("Votes")
    for player_id, target_player_id in result.votes.items():
        print(f"{player_id} -> {target_player_id}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulate one four-AI game round.")
    parser.add_argument(
        "--game-id",
        default=f"simulation-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
    )
    parser.add_argument("--message-threshold", type=int, default=20)
    parser.add_argument("--max-discussion-batches", type=int, default=12)
    return parser


def main() -> None:
    load_dotenv()
    if os.getenv("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "whosai-dev")

    args = _build_parser().parse_args()
    chat_model = build_deepseek_chat_model()
    decision_model = with_decision_schema(chat_model)
    result = asyncio.run(
        simulate_game(
            decision_model,
            game_id=args.game_id,
            message_threshold=args.message_threshold,
            max_discussion_batches=args.max_discussion_batches,
        )
    )
    print_simulation(result)


if __name__ == "__main__":
    main()
