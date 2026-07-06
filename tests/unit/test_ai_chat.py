from io import StringIO
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from whosai.ai.chat import chat_with_ai
from whosai.ai.models import AIPlayerDecision


class RecordingDecisionModel:
    def __init__(self, decisions: list[AIPlayerDecision]) -> None:
        self.decisions = iter(decisions)
        self.invocations: list[list[BaseMessage]] = []

    def invoke(
        self,
        input: list[BaseMessage],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> AIPlayerDecision:
        self.invocations.append(input)
        return next(self.decisions)


def test_chat_with_ai_keeps_a_current_round_transcript() -> None:
    model = RecordingDecisionModel(
        [
            AIPlayerDecision(
                action="speak",
                response="not sure, Player 2 maybe",
                target_player_id=None,
                decision_summary="Answer the question.",
            ),
            AIPlayerDecision(
                action="wait",
                response=None,
                target_player_id=None,
                decision_summary="Nothing useful to add.",
            ),
        ]
    )
    output = StringIO()

    chat_with_ai(
        model,
        input_stream=StringIO("who seems sus?\nyeah maybe\n/quit\n"),
        output_stream=output,
    )

    assert "Player 4> not sure, Player 2 maybe" in output.getvalue()
    assert "Player 4> [wait]" in output.getvalue()
    assert len(model.invocations) == 2
    second_turn = str(model.invocations[1][1].content)
    assert "Player 1: who seems sus?" in second_turn
    assert "Player 4: not sure, Player 2 maybe" in second_turn
    assert "Player 1: yeah maybe" in second_turn


def test_chat_with_ai_rejects_using_the_same_player_for_both_sides() -> None:
    model = RecordingDecisionModel([])

    try:
        chat_with_ai(
            model,
            ai_player_id="Player 2",
            human_player_id="Player 2",
            input_stream=StringIO(),
            output_stream=StringIO(),
        )
    except ValueError as error:
        assert str(error) == "The AI and human player IDs must be different."
    else:
        raise AssertionError("Expected chat_with_ai to reject duplicate player IDs.")
