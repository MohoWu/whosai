import os

from langchain_deepseek import ChatDeepSeek


def build_deepseek_chat_model() -> ChatDeepSeek:
    """Build the structured-output-capable DeepSeek model used by AI players."""
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is required.")

    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    if model_name == "deepseek-reasoner":
        raise ValueError("deepseek-reasoner does not support the required structured output.")

    return ChatDeepSeek(
        model=model_name,
        temperature=0.7,
        timeout=60,
        max_retries=2,
    )
