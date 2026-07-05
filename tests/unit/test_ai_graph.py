import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from whosai.ai.graph import build_ai_player_graph
from whosai.ai.models import AIPlayerDecision, ChatMessage
from whosai.ai.player import LangGraphAIPlayer
from whosai.ai.prompt import (
    build_model_messages,
    build_system_prompt,
    load_phase_prompt_definition,
    load_system_prompt_definition,
)
from whosai.application.models import AIPlayerRequest
from whosai.domain.game import ChatMessage as DomainChatMessage
from whosai.domain.game import Phase


class StubDecisionModel:
    def __init__(self, decision: AIPlayerDecision | dict[str, Any]) -> None:
        self.decision = decision
        self.messages: list[BaseMessage] = []
        self.config: RunnableConfig | None = None

    def invoke(
        self,
        input: list[BaseMessage],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> AIPlayerDecision | dict[str, Any]:
        self.messages = input
        self.config = config
        return self.decision


def test_system_prompt_assigns_identity_and_explains_the_game() -> None:
    prompt = build_system_prompt("Player 4")

    assert "You are Player 4" in prompt
    assert "4 to 8 anonymous players" in prompt
    assert "Humans win when every AI player has been eliminated" in prompt
    assert "AI side wins when the number of living humans equals" in prompt
    assert "Be smart and adaptive" in prompt
    assert "do not need to speak every time" in prompt
    assert 'action is "vote"' in prompt


def test_system_prompt_definition_declares_player_parameter() -> None:
    definition = load_system_prompt_definition()

    assert definition.name == "ai-player-system"
    assert definition.version == 1
    assert set(definition.parameters) == {"player_id"}
    assert "{player_id}" in definition.template


def test_model_messages_include_every_current_round_message_in_order() -> None:
    messages = build_model_messages(
        player_id="Player 3",
        round_number=2,
        turn_number=3,
        new_messages_since_last_turn=0,
        phase="discussion",
        chat_history=[
            ChatMessage(player_id="Player 1", content="Player 4 sounds suspicious."),
            ChatMessage(player_id="Player 4", content="Why me?"),
            ChatMessage(player_id="Player 2", content="Player 3, what do you think?"),
        ],
        eligible_vote_targets=[],
    )

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    transcript = str(messages[1].content)
    assert transcript.index("Player 1: Player 4 sounds suspicious.") < transcript.index(
        "Player 4: Why me?"
    )
    assert transcript.index("Player 4: Why me?") < transcript.index(
        "Player 2: Player 3, what do you think?"
    )
    assert "Current discussion round: 2" in transcript
    assert "Current turn: 3" in transcript
    assert "New messages since previous turn: 0" in transcript
    assert "This is discussion turn 3." in transcript
    assert 'action "wait" is not allowed' in transcript
    assert transcript.rstrip().endswith("target_player_id must be null in this phase.")


def test_voting_message_ends_with_phase_and_eligible_targets() -> None:
    messages = build_model_messages(
        player_id="Player 3",
        round_number=2,
        turn_number=6,
        new_messages_since_last_turn=4,
        phase="voting",
        chat_history=[ChatMessage(player_id="Player 1", content="Time to vote.")],
        eligible_vote_targets=["Player 1", "Player 2", "Player 4"],
    )

    prompt = str(messages[1].content)
    assert "Current phase: VOTING." in prompt
    assert "Eligible vote targets: Player 1, Player 2, Player 4" in prompt
    assert prompt.rstrip().endswith(
        "Set target_player_id to exactly one eligible player ID and response to null."
    )


def test_phase_prompt_definition_contains_discussion_and_voting() -> None:
    definition = load_phase_prompt_definition()

    assert definition.name == "ai-player-phase-instructions"
    assert definition.version == 1
    assert set(definition.phases) == {"discussion", "voting"}


def test_graph_returns_a_speak_decision_and_adds_trace_metadata() -> None:
    model = StubDecisionModel(
        AIPlayerDecision(
            action="speak",
            response="I think Player 4 is deflecting.",
            target_player_id=None,
            decision_summary="A direct answer helps avoid looking evasive.",
        )
    )
    graph = build_ai_player_graph(model)

    result = graph.invoke(
        {
            "game_id": "game-1",
            "player_id": "Player 3",
            "round_number": 1,
            "turn_number": 1,
            "new_messages_since_last_turn": 1,
            "phase": "discussion",
            "chat_history": [ChatMessage(player_id="Player 2", content="Player 3, any thoughts?")],
            "eligible_vote_targets": [],
        }
    )

    assert result["decision"].action == "speak"
    assert result["decision"].response == "I think Player 4 is deflecting."
    assert model.config is not None
    assert "ai-player" in model.config["tags"]
    assert model.config["metadata"]["game_id"] == "game-1"
    assert model.config["metadata"]["player_id"] == "Player 3"
    assert model.config["metadata"]["round_number"] == 1


def test_graph_can_choose_to_wait() -> None:
    model = StubDecisionModel(
        {
            "action": "wait",
            "response": None,
            "target_player_id": None,
            "decision_summary": "No one addressed this player and the discussion is active.",
        }
    )
    graph = build_ai_player_graph(model)

    result = graph.invoke(
        {
            "game_id": "game-2",
            "player_id": "Player 1",
            "round_number": 3,
            "turn_number": 2,
            "new_messages_since_last_turn": 4,
            "phase": "discussion",
            "chat_history": [ChatMessage(player_id="Player 2", content="I agree with Player 4.")],
            "eligible_vote_targets": [],
        }
    )

    assert result["decision"].action == "wait"
    assert result["decision"].response is None


def test_graph_can_vote_for_an_eligible_player() -> None:
    model = StubDecisionModel(
        {
            "action": "vote",
            "response": None,
            "target_player_id": "Player 4",
            "decision_summary": "Player 4 drew the most suspicion during discussion.",
        }
    )
    graph = build_ai_player_graph(model)

    result = graph.invoke(
        {
            "game_id": "game-3",
            "player_id": "Player 1",
            "round_number": 3,
            "turn_number": 5,
            "new_messages_since_last_turn": 4,
            "phase": "voting",
            "chat_history": [
                ChatMessage(player_id="Player 2", content="Player 4 contradicted themselves.")
            ],
            "eligible_vote_targets": ["Player 2", "Player 3", "Player 4"],
        }
    )

    assert result["decision"].action == "vote"
    assert result["decision"].response is None
    assert result["decision"].target_player_id == "Player 4"


@pytest.mark.parametrize(
    ("action", "response", "target_player_id"),
    [
        ("speak", None, None),
        ("speak", "Hello", "Player 2"),
        ("wait", "I should not be present.", None),
        ("wait", None, "Player 2"),
        ("vote", "Player 2", "Player 2"),
        ("vote", None, None),
    ],
)
def test_decision_rejects_inconsistent_action_fields(
    action: str,
    response: str | None,
    target_player_id: str | None,
) -> None:
    with pytest.raises(ValidationError):
        AIPlayerDecision.model_validate(
            {
                "action": action,
                "response": response,
                "target_player_id": target_player_id,
                "decision_summary": "Test decision.",
            }
        )


def test_decision_rejects_action_from_wrong_phase() -> None:
    decision = AIPlayerDecision(
        action="wait",
        response=None,
        target_player_id=None,
        decision_summary="Nothing to add.",
    )

    with pytest.raises(ValueError, match="Only a vote decision"):
        decision.validate_for_phase("voting")


def test_langgraph_player_adapts_the_application_request_and_vote_decision() -> None:
    async def scenario() -> None:
        model = StubDecisionModel(
            AIPlayerDecision(
                action="vote",
                response=None,
                target_player_id="Player 2",
                decision_summary="Player 2 was inconsistent.",
            )
        )
        player = LangGraphAIPlayer(build_ai_player_graph(model))

        decision = await player.decide(
            AIPlayerRequest(
                game_id="game-1",
                seat_id="Player 4",
                round_number=2,
                phase=Phase.VOTING,
                turn_number=3,
                new_message_count=2,
                direct_mention=True,
                chat_history=(
                    DomainChatMessage(
                        id="message-1",
                        seat_id="Player 2",
                        content="I suspect Player 4.",
                        sent_at=datetime(2026, 7, 5, 12, 0, tzinfo=UTC),
                    ),
                ),
                eligible_vote_targets=("Player 1", "Player 2", "Player 3"),
            )
        )

        assert decision.action == "vote"
        assert decision.target_seat_id == "Player 2"
        assert model.config is not None
        assert model.config["metadata"]["direct_mention"] is True

    asyncio.run(scenario())
