import asyncio
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from whosai.ai.models import AIPlayerDecision
from whosai.ai.simulation import DEFAULT_PLAYERS, simulate_game


class AlwaysParticipatesModel:
    def invoke(
        self,
        input: list[BaseMessage],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> AIPlayerDecision:
        if config is None:
            raise AssertionError("Trace configuration is required.")
        metadata = config["metadata"]
        player_id = str(metadata["player_id"])
        phase = str(metadata["phase"])
        batch = int(metadata["batch"])

        if phase == "voting":
            target = next(candidate for candidate in DEFAULT_PLAYERS if candidate != player_id)
            return AIPlayerDecision(
                action="vote",
                response=None,
                target_player_id=target,
                decision_summary="Cast a valid scripted vote.",
            )

        return AIPlayerDecision(
            action="speak",
            response=f"Message from {player_id} in batch {batch}.",
            target_player_id=None,
            decision_summary="Participate in the scripted discussion.",
        )


def test_simulation_runs_parallel_batches_then_collects_every_vote() -> None:
    result = asyncio.run(
        simulate_game(
            AlwaysParticipatesModel(),
            game_id="test-simulation",
            message_threshold=4,
            max_discussion_batches=2,
        )
    )

    assert result.discussion_batches == 1
    assert len(result.messages) == 5
    assert result.messages[0].content == "how's everyone doing?"
    assert set(result.votes) == set(DEFAULT_PLAYERS)
    assert all(voter != target for voter, target in result.votes.items())
