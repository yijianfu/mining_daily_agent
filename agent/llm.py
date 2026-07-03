"""Unified LLM factory — multi-provider model initialization.

Supports Anthropic, OpenAI, DeepSeek, Qwen, Zhipu, Moonshot.
Usage: model = get_model()  # reads MODEL_PROVIDER from env
"""

import os
import re
from typing import Optional

from loguru import logger
from langchain_core.language_models import BaseChatModel


def _env(key: str, default: str = "") -> str:
    """Read an env var, stripping whitespace and inline # comments.

    .env lines like ``KEY=value  # explanation`` or ``KEY=# commented out``
    are cleaned to ``value`` / ``""`` regardless of how dotenv parses them.
    """
    val = os.environ.get(key, default)
    # Cut at first '#' that is either at the start or preceded by whitespace
    val = re.sub(r"(?:^|\s+)#.*$", "", val)
    return val.strip()


PROVIDERS: dict[str, dict] = {
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
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": None,
        "default_model": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "type": "anthropic",
    },
    "openai": {
        "name": "OpenAI GPT",
        "base_url": None,
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "type": "openai",
    },
}


def get_model(provider: Optional[str] = None) -> BaseChatModel:
    """Create an LLM model instance from environment configuration.

    Selection order:
    1. Explicit `provider` argument
    2. `MODEL_PROVIDER` environment variable
    3. First provider with its API key set in the environment

    Raises ValueError if no API key is configured for any provider.
    """
    provider_key = provider or _env("MODEL_PROVIDER", "")

    # If MODEL_PROVIDER is explicitly set, use it (or warn and fall through)
    if provider_key and provider_key in PROVIDERS:
        cfg = PROVIDERS[provider_key]
        api_key = _env(cfg["api_key_env"], "").strip()
        if api_key:
            return _build_model(cfg, api_key)
        else:
            logger.warning(
                f"{cfg['name']} specified but {cfg['api_key_env']} not set, "
                f"trying auto-detect..."
            )

    # Auto-detect: first provider with an available API key
    for key, cfg in PROVIDERS.items():
        api_key = _env(cfg["api_key_env"], "").strip()
        if api_key:
            logger.info(f"Auto-detected provider: {cfg['name']} ({key})")
            return _build_model(cfg, api_key)

    supported = "\n".join(
        f"  {k:12s} → set {v['api_key_env']}"
        for k, v in PROVIDERS.items()
    )
    raise ValueError(
        f"No LLM API key configured. Supported providers:\n{supported}\n\n"
        f"Run with --standalone for offline mode (no LLM required)."
    )


def _build_model(cfg: dict, api_key: str) -> BaseChatModel:
    """Build a LangChain model instance from provider config."""
    model_name = _env("MODEL_NAME", "").strip() or cfg["default_model"]
    temperature = float(_env("MODEL_TEMPERATURE", "0.3"))
    max_tokens = int(_env("MODEL_MAX_TOKENS", "4096"))
    timeout = int(_env("MODEL_TIMEOUT", "120"))

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
    """Return a human-readable list of supported providers and their status."""
    lines = ["Supported LLM providers:"]
    for key, cfg in PROVIDERS.items():
        key_set = "✓" if _env(cfg["api_key_env"], "").strip() else "○"
        lines.append(
            f"  {key_set} {key:12s} {cfg['name']:20s} "
            f"({cfg['api_key_env']})"
        )
    return "\n".join(lines)
