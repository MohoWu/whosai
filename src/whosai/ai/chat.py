import argparse
import os
import sys
from collections.abc import Sequence
from typing import TextIO

from dotenv import load_dotenv

from whosai.ai.graph import DecisionModel, build_ai_player_graph, with_decision_schema
from whosai.ai.models import AIPlayerDecision, ChatMessage
from whosai.ai.providers import build_deepseek_chat_model
from whosai.domain.game import PlayerRoundBrief
from whosai.domain.keywords import LocalizedText

DEFAULT_AI_PLAYER = "Player 4"
DEFAULT_HUMAN_PLAYER = "Player 1"
DEFAULT_CATEGORY = LocalizedText(en="Public places", zh_cn="公共场所")
DEFAULT_KEYWORD = LocalizedText(en="airport", zh_cn="机场")


def chat_with_ai(
    decision_model: DecisionModel,
    *,
    ai_player_id: str = DEFAULT_AI_PLAYER,
    human_player_id: str = DEFAULT_HUMAN_PLAYER,
    round_brief: PlayerRoundBrief | None = None,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> None:
    """Run an interactive discussion against one AI player using the production graph."""
    if ai_player_id == human_player_id:
        raise ValueError("The AI and human player IDs must be different.")

    brief = round_brief or PlayerRoundBrief(
        category=DEFAULT_CATEGORY,
        keyword=DEFAULT_KEYWORD,
    )
    graph = build_ai_player_graph(decision_model)
    messages: list[ChatMessage] = []
    turn_number = 0

    print(
        f"Chatting as {human_player_id} with {ai_player_id}. Type /quit or press Ctrl-D to stop.",
        file=output_stream,
    )
    print(
        f"Private AI brief: {brief.category.en}"
        + (f" / {brief.keyword.en}" if brief.keyword is not None else " / no keyword"),
        file=output_stream,
    )

    while True:
        output_stream.write(f"{human_player_id}> ")
        output_stream.flush()
        line = input_stream.readline()
        if not line:
            output_stream.write("\n")
            return

        content = line.strip()
        if not content:
            continue
        if content == "/quit":
            return

        messages.append(ChatMessage(player_id=human_player_id, content=content))
        turn_number += 1
        result = graph.invoke(
            {
                "game_id": "interactive-prompt-test",
                "player_id": ai_player_id,
                "round_number": 1,
                "turn_number": turn_number,
                "new_messages_since_last_turn": 1,
                "phase": "discussion",
                "chat_history": list(messages),
                "eligible_vote_targets": [],
                "round_brief": brief,
            }
        )
        decision = AIPlayerDecision.model_validate(result["decision"])

        if decision.action == "speak":
            if decision.response is None:
                raise AssertionError("A speak decision must contain a response.")
            messages.append(ChatMessage(player_id=ai_player_id, content=decision.response))
            print(f"{ai_player_id}> {decision.response}", file=output_stream)
        else:
            print(f"{ai_player_id}> [wait]", file=output_stream)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chat with one AI player through the production decision graph."
    )
    parser.add_argument("--ai-player", default=DEFAULT_AI_PLAYER)
    parser.add_argument("--human-player", default=DEFAULT_HUMAN_PLAYER)
    parser.add_argument("--category", default=DEFAULT_CATEGORY.en)
    parser.add_argument("--category-zh", default=DEFAULT_CATEGORY.zh_cn)
    parser.add_argument("--keyword", default=DEFAULT_KEYWORD.en)
    parser.add_argument("--keyword-zh", default=DEFAULT_KEYWORD.zh_cn)
    parser.add_argument(
        "--uninformed",
        action="store_true",
        help="Give the AI only the category, matching an uninformed round.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    load_dotenv()
    if os.getenv("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "whosai-dev")

    args = _build_parser().parse_args(argv)
    round_brief = PlayerRoundBrief(
        category=LocalizedText(en=args.category, zh_cn=args.category_zh),
        keyword=(
            None if args.uninformed else LocalizedText(en=args.keyword, zh_cn=args.keyword_zh)
        ),
    )
    chat_with_ai(
        with_decision_schema(build_deepseek_chat_model()),
        ai_player_id=args.ai_player,
        human_player_id=args.human_player,
        round_brief=round_brief,
    )


if __name__ == "__main__":
    main()
