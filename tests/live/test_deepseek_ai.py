import os

import pytest
from dotenv import load_dotenv

from whosai.ai.graph import build_ai_player_graph, with_decision_schema
from whosai.ai.models import AIPlayerDecision, ChatMessage
from whosai.ai.providers import build_deepseek_chat_model
from whosai.domain.game import PlayerRoundBrief
from whosai.domain.keywords import LocalizedText


@pytest.mark.live_model
def test_default_deepseek_model_completes_one_ai_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("WHOSAI_RUN_LIVE_MODEL_TESTS") != "1":
        pytest.skip("Set WHOSAI_RUN_LIVE_MODEL_TESTS=1 to call the live model.")

    load_dotenv()
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is required for the live model smoke test.")

    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_BASE", raising=False)
    graph = build_ai_player_graph(with_decision_schema(build_deepseek_chat_model()))

    result = graph.invoke(
        {
            "game_id": "live-smoke-game",
            "player_id": "Player 4",
            "round_number": 1,
            "turn_number": 1,
            "new_messages_since_last_turn": 1,
            "phase": "discussion",
            "chat_history": [
                ChatMessage(
                    player_id="Player 1",
                    content="Player 4, who seems suspicious?",
                )
            ],
            "eligible_vote_targets": [],
            "round_brief": PlayerRoundBrief(
                category=LocalizedText(en="Public places", zh_cn="公共场所"),
                keyword=LocalizedText(en="airport", zh_cn="机场"),
            ),
        }
    )

    decision = AIPlayerDecision.model_validate(result["decision"])
    assert decision.action in {"speak", "wait"}
