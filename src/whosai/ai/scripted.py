from whosai.application.models import AIPlayerDecision, AIPlayerRequest
from whosai.domain.game import Phase


class ScriptedAIPlayer:
    """Deterministic AI controller for browser smoke tests."""

    async def decide(self, request: AIPlayerRequest) -> AIPlayerDecision:
        if request.phase is Phase.DISCUSSION:
            return AIPlayerDecision(
                action="speak",
                response=(
                    f"Round {request.round_number}: signal received. "
                    "I am watching the timing and the votes."
                ),
                target_seat_id=None,
            )
        if request.phase is Phase.VOTING and request.eligible_vote_targets:
            return AIPlayerDecision(
                action="vote",
                response=None,
                target_seat_id=request.eligible_vote_targets[0],
            )
        return AIPlayerDecision(
            action="wait",
            response=None,
            target_seat_id=None,
        )
