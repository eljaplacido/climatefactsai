"""
Unified LLM client for CliLens.AI intelligence services — DeepSeek primary.

All claim extraction, fact-checking, RAG synthesis, and chat responses go
through DeepSeek's OpenAI-compatible API. Translation (api/main.py) may
optionally fall back to Anthropic Claude when ANTHROPIC_API_KEY is set,
but the core intelligence pipeline is DeepSeek-only.
"""

import os
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

try:
    from openai import OpenAI as OpenAIClient
except ImportError:
    OpenAIClient = None
    logger.error("openai package not installed — LLM features unavailable")


def get_llm_client():
    """
    Return the DeepSeek LLM client and model name.

    Returns:
        Tuple of (client, model_name) or (None, model_name) if unavailable.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key:
        logger.error("DEEPSEEK_API_KEY not set — LLM features unavailable")
        return None, model

    if not OpenAIClient:
        logger.error("openai package not installed — LLM features unavailable")
        return None, model

    return OpenAIClient(api_key=api_key, base_url=base_url), model


def llm_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.1,
    client=None,
    model: str = None,
) -> Optional[str]:
    """
    Send a chat completion request to DeepSeek.

    Args:
        prompt: User message
        system_prompt: Optional system message
        max_tokens: Max response tokens
        temperature: Temperature for sampling
        client: Optional pre-created client (reuses connection)
        model: Optional model override

    Returns:
        Response text or None on failure
    """
    if client is None:
        client, default_model = get_llm_client()
        if model is None:
            model = default_model
    elif model is None:
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if client is None:
        logger.error("No LLM client available")
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM call failed: {type(e).__name__}: {e}")
        return None
