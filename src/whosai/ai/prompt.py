from functools import cache
from importlib.resources import files

import yaml
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

from whosai.ai.models import ChatMessage, GamePhase


class PromptParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str


class PromptSnippet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parameters: dict[str, PromptParameter]
    template: str

    def render(self, **values: str) -> str:
        expected = set(self.parameters)
        supplied = set(values)
        if missing := expected - supplied:
            raise ValueError(f"Missing prompt parameters: {', '.join(sorted(missing))}")
        if unexpected := supplied - expected:
            raise ValueError(f"Unexpected prompt parameters: {', '.join(sorted(unexpected))}")
        return self.template.format_map(values)


class PromptDefinition(PromptSnippet):
    name: str
    version: int


class PhasePromptDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: int
    phases: dict[GamePhase, PromptSnippet]


@cache
def load_system_prompt_definition() -> PromptDefinition:
    prompt_file = files("whosai.ai.prompts").joinpath("system.yaml")
    raw_definition = yaml.safe_load(prompt_file.read_text(encoding="utf-8"))
    return PromptDefinition.model_validate(raw_definition)


@cache
def load_phase_prompt_definition() -> PhasePromptDefinition:
    prompt_file = files("whosai.ai.prompts").joinpath("phases.yaml")
    raw_definition = yaml.safe_load(prompt_file.read_text(encoding="utf-8"))
    return PhasePromptDefinition.model_validate(raw_definition)


def build_system_prompt(player_id: str) -> str:
    """Build the stable game instructions for one anonymous AI seat."""
    return load_system_prompt_definition().render(player_id=player_id)


def build_phase_instruction(
    *,
    phase: GamePhase,
    player_id: str,
    turn_number: int,
    new_messages_since_last_turn: int,
    eligible_vote_targets: list[str],
) -> str:
    definition = load_phase_prompt_definition().phases[phase]
    if phase == "discussion":
        return definition.render(
            player_id=player_id,
            turn_number=str(turn_number),
            new_messages_since_last_turn=str(new_messages_since_last_turn),
        )
    if not eligible_vote_targets:
        raise ValueError("Voting requires at least one eligible target.")
    return definition.render(
        player_id=player_id,
        eligible_vote_targets=", ".join(eligible_vote_targets),
    )


def render_chat_history(chat_history: list[ChatMessage]) -> str:
    """Render all current-round messages in chronological order."""
    if not chat_history:
        return "(No messages have been sent in this round.)"
    return "\n".join(f"{message.player_id}: {message.content}" for message in chat_history)


def build_model_messages(
    *,
    player_id: str,
    round_number: int,
    turn_number: int,
    new_messages_since_last_turn: int,
    phase: GamePhase,
    chat_history: list[ChatMessage],
    eligible_vote_targets: list[str],
) -> list[BaseMessage]:
    """Create the model input for one decision without retaining earlier rounds."""
    transcript = render_chat_history(chat_history)
    phase_instruction = build_phase_instruction(
        phase=phase,
        player_id=player_id,
        turn_number=turn_number,
        new_messages_since_last_turn=new_messages_since_last_turn,
        eligible_vote_targets=eligible_vote_targets,
    )
    return [
        SystemMessage(content=build_system_prompt(player_id)),
        HumanMessage(
            content=f"""Current discussion round: {round_number}
Current turn: {turn_number}
New messages since previous turn: {new_messages_since_last_turn}

Current-round public chat, oldest message first:
<chat_history>
{transcript}
</chat_history>

{phase_instruction}"""
        ),
    ]
