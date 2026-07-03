"""Unified LLM factory — multi-provider model initialization.

Supports Anthropic, OpenAI, and all OpenAI-compatible Chinese LLMs
(DeepSeek, Qwen, Zhipu GLM, Moonshot Kimi) via a single interface.

Usage:
    model = get_model()          # reads MODEL_PROVIDER from env
    model = get_model("qwen")    # explicit provider
"""

import os
from typing import Optional

from loguru import logger
from langchain_core.language_models import BaseChatModel


# ── Provider Registry ─────────────────────────────────────────────────────────
# Each entry: (display_name, base_url, default_model, api_key_env_var)

PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": None,  # uses langchain_anthropic.ChatAnthropic directly
        "default_model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "type": "anthropic",
    },
    "openai": {
        "name": "OpenAI GPT",
        "base_url": None,  # uses default openai base
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "type": "openai",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "type": "openai",
    },
    "qwen": {
        "name": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
        "api_key_env": "QWEN_API_KEY",
        "type": "openai",
    },
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-plus",
        "api_key_env": "ZHIPU_API_KEY",
        "type": "openai",
    },
    "moonshot": {
        "name": "Moonshot Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-128k",
        "api_key_env": "MOONSHOT_API_KEY",
        "type": "openai",
    },
}


def get_model(provider: Optional[str] = None) -> BaseChatModel:
    """Create an LLM model instance from environment configuration.

    Provider selection order:
    1. Explicit `provider` argument
    2. `MODEL_PROVIDER` environment variable
    3. First provider with its API key set in the environment

    Args:
        provider: Optional provider key (e.g. "qwen", "deepseek").

    Returns:
        A LangChain chat model instance.

    Raises:
        ValueError: If no API key is configured for any provider.
    """
    provider_key = provider or os.getenv("MODEL_PROVIDER", "")

    # If provider is explicitly set but has no API key, try to find another
    if provider_key and provider_key in PROVIDERS:
        cfg = PROVIDERS[provider_key]
        api_key = os.getenv(cfg["api_key_env"], "")
        if api_key:
            return _build_model(provider_key, cfg, api_key)
        else:
            logger.warning(
                f"{cfg['name']} API key not set ({cfg['api_key_env']}), "
                f"trying other providers..."
            )

    # Try the explicitly set provider first (even without key check above)
    if provider_key and provider_key in PROVIDERS:
        cfg = PROVIDERS[provider_key]
        api_key = os.getenv(cfg["api_key_env"], "")
        if api_key:
            return _build_model(provider_key, cfg, api_key)

    # Auto-detect: use the first provider with an available API key
    for key, cfg in PROVIDERS.items():
        api_key = os.getenv(cfg["api_key_env"], "")
        if api_key:
            logger.info(f"Auto-detected provider: {cfg['name']} ({key})")
            return _build_model(key, cfg, api_key)

    # List supported providers in the error message
    supported = "\n".join(
        f"  {k:12s} → set {v['api_key_env']}"
        for k, v in PROVIDERS.items()
    )
    raise ValueError(
        f"No LLM API key configured. Supported providers:\n{supported}\n\n"
        f"Or run with --standalone for offline mode (no LLM required)."
    )


def _build_model(key: str, cfg: dict, api_key: str) -> BaseChatModel:
    """Build a LangChain model instance for the given provider.

    Args:
        key: Provider key (e.g. "qwen").
        cfg: Provider configuration dict.
        api_key: The API key string.

    Returns:
        Configured BaseChatModel instance.
    """
    model_name = os.getenv("MODEL_NAME", "") or cfg["default_model"]
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0.3"))
    max_tokens = int(os.getenv("MODEL_MAX_TOKENS", "4096"))
    timeout = int(os.getenv("MODEL_TIMEOUT", "120"))

    logger.info(f"Initializing {cfg['name']}: model={model_name}")

    if cfg["type"] == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    else:
        # OpenAI-compatible (OpenAI, DeepSeek, Qwen, Zhipu, Moonshot, etc.)
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": model_name,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        if cfg.get("base_url"):
            kwargs["base_url"] = cfg["base_url"]

        return ChatOpenAI(**kwargs)


def list_providers() -> str:
    """Return a human-readable list of supported providers."""
    lines = ["Supported LLM providers:"]
    for key, cfg in PROVIDERS.items():
        key_set = "✓" if os.getenv(cfg["api_key_env"]) else "○"
        lines.append(
            f"  {key_set} {key:12s} {cfg['name']:20s} "
            f"({cfg['api_key_env']})"
        )
    return "\n".join(lines)
