from langgraph.graph.state import CompiledStateGraph

from whosai.ai.graph import AIPlayerState
from whosai.ai.models import AIPlayerDecision as GraphDecision
from whosai.ai.models import ChatMessage, GamePhase
from whosai.application.models import AIPlayerDecision, AIPlayerRequest
from whosai.domain.game import Phase


class LangGraphAIPlayer:
    """Adapt the AI graph to the provider-neutral application port."""

    def __init__(self, graph: CompiledStateGraph[AIPlayerState]) -> None:
        self._graph = graph

    async def decide(self, request: AIPlayerRequest) -> AIPlayerDecision:
        phase: GamePhase
        if request.phase is Phase.DISCUSSION:
            phase = "discussion"
        elif request.phase is Phase.VOTING:
            phase = "voting"
        else:
            raise ValueError(f"AI decisions are not allowed during {request.phase.value}.")
        state: AIPlayerState = {
            "game_id": request.game_id,
            "player_id": request.seat_id,
            "round_number": request.round_number,
            "turn_number": request.turn_number,
            "new_messages_since_last_turn": request.new_message_count,
            "direct_mention": request.direct_mention,
            "phase": phase,
            "chat_history": [
                ChatMessage(player_id=message.seat_id, content=message.content)
                for message in request.chat_history
            ],
            "eligible_vote_targets": list(request.eligible_vote_targets),
            "round_brief": request.round_brief,
        }
        result = await self._graph.ainvoke(state)
        decision = GraphDecision.model_validate(result["decision"])
        return AIPlayerDecision(
            action=decision.action,
            response=decision.response,
            target_seat_id=decision.target_player_id,
        )
