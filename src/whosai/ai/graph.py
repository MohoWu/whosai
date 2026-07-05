from typing import Any, NotRequired, Protocol, TypedDict, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import merge_configs
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from whosai.ai.models import AIPlayerDecision, ChatMessage, GamePhase
from whosai.ai.prompt import build_model_messages


class AIPlayerState(TypedDict):
    """Everything required to make one AI decision during a discussion round."""

    game_id: str
    player_id: str
    round_number: int
    turn_number: int
    new_messages_since_last_turn: int
    direct_mention: NotRequired[bool]
    phase: GamePhase
    chat_history: list[ChatMessage]
    eligible_vote_targets: list[str]
    decision: NotRequired[AIPlayerDecision]


class DecisionModel(Protocol):
    """A chat model that has already been configured for structured output."""

    def invoke(
        self,
        input: list[BaseMessage],
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> AIPlayerDecision | dict[str, Any]: ...


def with_decision_schema(model: BaseChatModel) -> DecisionModel:
    """Constrain a provider-backed chat model to the AI player decision schema."""
    structured_model = model.with_structured_output(AIPlayerDecision)
    return cast(DecisionModel, structured_model)


def build_ai_player_graph(
    decision_model: DecisionModel,
) -> CompiledStateGraph[AIPlayerState]:
    """Compile the single-node workflow used for one AI discussion turn."""

    def decide(
        state: AIPlayerState,
        config: RunnableConfig,
    ) -> dict[str, AIPlayerDecision]:
        messages = build_model_messages(
            player_id=state["player_id"],
            round_number=state["round_number"],
            turn_number=state["turn_number"],
            new_messages_since_last_turn=state["new_messages_since_last_turn"],
            phase=state["phase"],
            chat_history=state["chat_history"],
            eligible_vote_targets=state["eligible_vote_targets"],
        )
        trace_config = merge_configs(
            config,
            {
                "run_name": "ai-player-model-decision",
                "tags": ["ai-player", f"phase:{state['phase']}"],
                "metadata": {
                    "game_id": state["game_id"],
                    "player_id": state["player_id"],
                    "round_number": state["round_number"],
                    "turn_number": state["turn_number"],
                    "new_messages_since_last_turn": state["new_messages_since_last_turn"],
                    "direct_mention": state.get("direct_mention", False),
                    "phase": state["phase"],
                },
            },
        )
        raw_decision = decision_model.invoke(messages, config=trace_config)
        decision = AIPlayerDecision.model_validate(raw_decision).validate_for_phase(state["phase"])
        return {"decision": decision}

    builder = StateGraph(AIPlayerState)
    builder.add_node("decide", decide)
    builder.add_edge(START, "decide")
    builder.add_edge("decide", END)
    return builder.compile(name="ai-player-turn")
