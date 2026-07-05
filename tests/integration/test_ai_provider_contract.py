import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest
from langchain_core.messages import HumanMessage

from whosai.ai.graph import with_decision_schema
from whosai.ai.providers import build_deepseek_chat_model


def test_default_deepseek_model_completes_a_structured_ai_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []

    class DeepSeekContractHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers["Content-Length"])
            request = json.loads(self.rfile.read(content_length))
            requests.append(request)

            if request.get("tool_choice") and request.get("thinking") != {"type": "disabled"}:
                self._send_json(
                    400,
                    {
                        "error": {
                            "message": "Thinking mode does not support this tool_choice",
                            "type": "invalid_request_error",
                            "param": None,
                            "code": "invalid_request_error",
                        }
                    },
                )
                return

            self._send_json(
                200,
                {
                    "id": "chatcmpl-contract-test",
                    "object": "chat.completion",
                    "created": 0,
                    "model": request["model"],
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call-contract-test",
                                        "type": "function",
                                        "function": {
                                            "name": "AIPlayerDecision",
                                            "arguments": json.dumps(
                                                {
                                                    "action": "speak",
                                                    "response": "Player 2 seems unusually quiet.",
                                                    "target_player_id": None,
                                                    "decision_summary": (
                                                        "Contribute one observation."
                                                    ),
                                                }
                                            ),
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 10,
                        "total_tokens": 20,
                    },
                },
            )

        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), DeepSeekContractHandler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "contract-test-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setenv(
        "DEEPSEEK_API_BASE",
        f"http://127.0.0.1:{server.server_address[1]}/v1",
    )

    try:
        decision_model = with_decision_schema(build_deepseek_chat_model())
        decision = decision_model.invoke(
            [HumanMessage(content="Respond with one valid discussion decision.")]
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join()

    assert decision.action == "speak"
    assert requests[0]["model"] == "deepseek-v4-flash"
