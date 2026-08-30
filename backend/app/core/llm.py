"""LLM provider resolution: OpenAI-compatible (default) or Gemini."""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.config import settings


def get_llm(
    provider: str = "openai",
    model_name: str = "deepseek/deepseek-chat-v3.1",
    api_key: str | None = None,
    temperature: float = 0.2,
    base_url: str | None = None,
):
    """Create the chat LLM instance for the requested provider."""
    if provider == "openai":
        return ChatOpenAI(
            model_name=model_name,
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url,
            temperature=temperature,
            max_retries=4,
            timeout=120,
            request_timeout=120,
        )
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            convert_system_message_to_human=True,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")
