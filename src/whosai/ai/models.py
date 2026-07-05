from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

GamePhase = Literal["discussion", "voting"]


class ChatMessage(BaseModel):
    """One public chat message from the current discussion round."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    player_id: str = Field(min_length=1, description="Anonymous seat label, such as Player 2.")
    content: str = Field(min_length=1, description="Public message text.")


class AIPlayerDecision(BaseModel):
    """A structured chat, wait, or vote decision from an AI player."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    action: Literal["speak", "wait", "vote"] = Field(
        description="Speak or wait during discussion; vote during voting."
    )
    response: str | None = Field(
        description="The public chat message for speak; null for wait and vote."
    )
    target_player_id: str | None = Field(
        description="The anonymous player ID for vote; null for speak and wait."
    )
    decision_summary: str = Field(
        min_length=1,
        description=(
            "A brief, high-level explanation of the choice for debugging. "
            "Do not provide private chain-of-thought."
        ),
    )

    @model_validator(mode="after")
    def fields_match_action(self) -> Self:
        if self.action == "speak" and not self.response:
            raise ValueError("A speak decision requires a response.")
        if self.action == "speak" and self.target_player_id is not None:
            raise ValueError("A speak decision must not have a vote target.")
        if self.action == "wait" and (
            self.response is not None or self.target_player_id is not None
        ):
            raise ValueError("A wait decision must have a null response and vote target.")
        if self.action == "vote" and self.response is not None:
            raise ValueError("A vote decision must have a null response.")
        if self.action == "vote" and not self.target_player_id:
            raise ValueError("A vote decision requires a target player ID.")
        return self

    def validate_for_phase(self, phase: GamePhase) -> Self:
        if phase == "discussion" and self.action == "vote":
            raise ValueError("A vote decision is not valid during discussion.")
        if phase == "voting" and self.action != "vote":
            raise ValueError("Only a vote decision is valid during voting.")
        return self
