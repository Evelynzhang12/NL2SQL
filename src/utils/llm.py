"""LLM client management"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

from openai import OpenAI

from src.config import settings
from src.exceptions import ConfigurationError, LLMError
from src.utils.logger import get_logger

logger = get_logger(__name__)

_openai_client: Optional[OpenAI] = None
_anthropic_client: Optional[Any] = None
_gemini_client: Optional[Any] = None
_groq_client: Optional[OpenAI] = None
_deepseek_client: Optional[OpenAI] = None
_grok_client: Optional[OpenAI] = None

# Minimum seconds between consecutive calls to each free-tier provider,
# enforced per call (not just per question) — a single question can make
# 2-3 LLM calls (generation, correction, summarization), and free-tier
# rate limits are per-minute, so pacing only "between questions" still
# bursts past them. Conservative defaults; not documented exact quotas,
# so err on the side of slower-but-reliable over fast-but-429s.
_MIN_CALL_INTERVAL = {"gemini": 4.5, "groq": 2.5}
_last_call_time: dict = {}

# Every OpenAI-compatible client below (openai, groq, deepseek, grok) uses
# this instead of the SDK's default max_retries=2. A silent client-side
# retry re-sends the full prompt and shows up as a separate billed request
# on the provider's own dashboard with no trace in our logs — observed
# directly on a Grok run where the provider's request count came in ~4x
# our own call count, all clustered at the same timestamps. 1 retry still
# absorbs a single transient blip without quietly multiplying cost.
_CLIENT_MAX_RETRIES = 1

# Every completion call appends one record here (provider, model, token
# counts). The eval harness reads this via get_usage_log() after a run to
# report real per-provider usage instead of reverse-engineering it from a
# provider's billing dashboard after the fact.
_usage_log: list = []


def record_usage(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    _usage_log.append({
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    })


def get_usage_log() -> list:
    """Return a copy of every completion call's usage recorded since the last reset_usage_log()."""
    return list(_usage_log)


def reset_usage_log() -> None:
    _usage_log.clear()


def _throttle(provider: str) -> None:
    min_interval = _MIN_CALL_INTERVAL.get(provider)
    if min_interval is None:
        return
    last = _last_call_time.get(provider)
    now = time.monotonic()
    if last is not None:
        wait = min_interval - (now - last)
        if wait > 0:
            time.sleep(wait)
    _last_call_time[provider] = time.monotonic()


def get_openai_client() -> OpenAI:
    """
    Get or create the OpenAI client.

    Returns:
        OpenAI client instance
    """
    global _openai_client

    if _openai_client is None:
        logger.info("Initializing OpenAI client...")
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=_CLIENT_MAX_RETRIES)
        logger.info("OpenAI client initialized")

    return _openai_client


def get_anthropic_client() -> Any:
    """
    Get or create the Anthropic client.

    Only used by the eval harness (scripts/run_model_comparison.py) — the
    production API never calls this. Raises lazily so the server and every
    OpenAI-only script keep working with no ANTHROPIC_API_KEY set.
    """
    global _anthropic_client

    if _anthropic_client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise ConfigurationError("ANTHROPIC_API_KEY is not set")
        import anthropic

        logger.info("Initializing Anthropic client...")
        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=_CLIENT_MAX_RETRIES)
        logger.info("Anthropic client initialized")

    return _anthropic_client


def get_gemini_client() -> Any:
    """
    Get or create the Gemini client.

    Only used by the eval harness — the production API never calls this.
    Raises lazily so the server and every OpenAI-only script keep working
    with no GEMINI_API_KEY set.
    """
    global _gemini_client

    if _gemini_client is None:
        if not settings.GEMINI_API_KEY:
            raise ConfigurationError("GEMINI_API_KEY is not set")
        from google import genai

        logger.info("Initializing Gemini client...")
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Gemini client initialized")

    return _gemini_client


def get_deepseek_client() -> OpenAI:
    """
    Get or create the DeepSeek client.

    DeepSeek also exposes an OpenAI-compatible chat-completions API, so
    this reuses the `openai` SDK pointed at DeepSeek's endpoint. Only used
    by the eval harness.
    """
    global _deepseek_client

    if _deepseek_client is None:
        if not settings.DEEPSEEK_API_KEY:
            raise ConfigurationError("DEEPSEEK_API_KEY is not set")

        logger.info("Initializing DeepSeek client...")
        _deepseek_client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", max_retries=_CLIENT_MAX_RETRIES)
        logger.info("DeepSeek client initialized")

    return _deepseek_client


def get_grok_client() -> OpenAI:
    """
    Get or create the xAI Grok client.

    Grok also exposes an OpenAI-compatible chat-completions API, so this
    reuses the `openai` SDK pointed at xAI's endpoint. Only used by the
    eval harness. Note this is distinct from Groq (get_groq_client) — an
    unrelated inference host for open-weight models.
    """
    global _grok_client

    if _grok_client is None:
        if not settings.GROK_API_KEY:
            raise ConfigurationError("GROK_API_KEY is not set")

        logger.info("Initializing Grok (xAI) client...")
        _grok_client = OpenAI(api_key=settings.GROK_API_KEY, base_url="https://api.x.ai/v1", max_retries=_CLIENT_MAX_RETRIES)
        logger.info("Grok (xAI) client initialized")

    return _grok_client


def get_groq_client() -> OpenAI:
    """
    Get or create the Groq client.

    Groq exposes an OpenAI-compatible chat-completions API, so this reuses
    the `openai` SDK pointed at Groq's endpoint instead of adding a new
    dependency. Only used by the eval harness.
    """
    global _groq_client

    if _groq_client is None:
        if not settings.GROQ_API_KEY:
            raise ConfigurationError("GROQ_API_KEY is not set")

        logger.info("Initializing Groq client...")
        _groq_client = OpenAI(api_key=settings.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1", max_retries=_CLIENT_MAX_RETRIES)
        logger.info("Groq client initialized")

    return _groq_client


def complete(
    prompt: str,
    *,
    system: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Provider-agnostic single-turn completion.

    Used by the eval harness to run the pipeline against OpenAI / Anthropic /
    Gemini interchangeably. Production call sites never pass `provider=`, so
    this always resolves to "openai" and reproduces exactly the call each
    site made before this function existed — this is a behavior-preserving
    refactor, not a change to production behavior.
    """
    resolved_provider = provider or os.environ.get("LLM_DEFAULT_PROVIDER", "openai")
    _throttle(resolved_provider)

    if resolved_provider == "openai":
        return _complete_openai(prompt, temperature=temperature, max_tokens=max_tokens, model=model)
    elif resolved_provider in ("anthropic", "claude"):
        return _complete_anthropic(prompt, system=system, temperature=temperature, max_tokens=max_tokens, model=model)
    elif resolved_provider in ("gemini", "google"):
        return _complete_gemini(prompt, system=system, temperature=temperature, max_tokens=max_tokens, model=model)
    elif resolved_provider == "groq":
        return _complete_groq(prompt, temperature=temperature, max_tokens=max_tokens, model=model)
    elif resolved_provider == "deepseek":
        return _complete_deepseek(prompt, temperature=temperature, max_tokens=max_tokens, model=model)
    elif resolved_provider == "grok":
        return _complete_grok(prompt, temperature=temperature, max_tokens=max_tokens, model=model)
    else:
        raise ConfigurationError(f"Unknown LLM provider: {resolved_provider!r}")


def _complete_openai(
    prompt: str, *, temperature: float, max_tokens: Optional[int], model: Optional[str]
) -> str:
    client = get_openai_client()
    resolved_model = model or settings.LLM_MODEL

    # Reasoning-family models (gpt-5*, o3*, o4*) reject a custom temperature
    # (only the default, 1, is accepted) and use max_completion_tokens
    # instead of max_tokens. gpt-4o*/gpt-4.1* keep the original call shape.
    is_reasoning_model = resolved_model.startswith(("gpt-5", "o3", "o4"))

    kwargs: dict = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if not is_reasoning_model:
        kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
    else:
        # Reasoning-family models spend part of max_completion_tokens on
        # internal reasoning tokens before producing any visible output —
        # a caller-specified budget sized for a non-reasoning model (e.g.
        # 300 for the SQL corrector) can be entirely consumed by reasoning,
        # leaving an empty response. Enforce a generous floor, same fix as
        # applied to Gemini's thinking tokens.
        kwargs["max_completion_tokens"] = max(max_tokens or 0, 2048)
        kwargs["reasoning_effort"] = "low"  # this task doesn't need deep reasoning

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as e:
        raise LLMError(f"OpenAI completion failed: {e}") from e

    content = response.choices[0].message.content
    if not content:
        raise LLMError(f"OpenAI returned empty response (finish_reason={response.choices[0].finish_reason})")

    if response.usage:
        record_usage("openai", resolved_model, response.usage.prompt_tokens, response.usage.completion_tokens)

    return content.strip()


def _complete_groq(
    prompt: str, *, temperature: float, max_tokens: Optional[int], model: Optional[str]
) -> str:
    client = get_groq_client()
    resolved_model = model or settings.GROQ_MODEL
    kwargs: dict = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as e:
        raise LLMError(f"Groq completion failed: {e}") from e

    if response.usage:
        record_usage("groq", resolved_model, response.usage.prompt_tokens, response.usage.completion_tokens)

    return response.choices[0].message.content.strip()


def _complete_deepseek(
    prompt: str, *, temperature: float, max_tokens: Optional[int], model: Optional[str]
) -> str:
    client = get_deepseek_client()
    resolved_model = model or settings.DEEPSEEK_MODEL
    kwargs: dict = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as e:
        raise LLMError(f"DeepSeek completion failed: {e}") from e

    if response.usage:
        record_usage("deepseek", resolved_model, response.usage.prompt_tokens, response.usage.completion_tokens)

    return response.choices[0].message.content.strip()


def _complete_grok(
    prompt: str, *, temperature: float, max_tokens: Optional[int], model: Optional[str]
) -> str:
    client = get_grok_client()
    resolved_model = model or settings.GROK_MODEL
    kwargs: dict = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as e:
        raise LLMError(f"Grok completion failed: {e}") from e

    if response.usage:
        record_usage("grok", resolved_model, response.usage.prompt_tokens, response.usage.completion_tokens)

    return response.choices[0].message.content.strip()


def _complete_anthropic(
    prompt: str,
    *,
    system: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
    model: Optional[str],
) -> str:
    client = get_anthropic_client()
    resolved_model = model or settings.CLAUDE_MODEL
    kwargs: dict = {
        "model": resolved_model,
        # Anthropic's Messages API requires max_tokens explicitly (unlike
        # OpenAI, which has a server-side default) — fall back to a safe
        # default when the caller didn't specify one.
        "max_tokens": max_tokens or 1024,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if system:
        kwargs["system"] = system

    try:
        response = client.messages.create(**kwargs)
    except Exception as e:
        raise LLMError(f"Anthropic completion failed: {e}") from e

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise LLMError(f"Anthropic returned no text content (stop_reason={response.stop_reason})")

    if response.usage:
        record_usage("anthropic", resolved_model, response.usage.input_tokens, response.usage.output_tokens)

    return "".join(text_blocks).strip()


def _complete_gemini(
    prompt: str,
    *,
    system: Optional[str],
    temperature: float,
    max_tokens: Optional[int],
    model: Optional[str],
) -> str:
    client = get_gemini_client()
    from google.genai import types

    # Current Gemini models "think" before answering, and thinking tokens
    # are drawn from the same max_output_tokens budget as the visible
    # answer — with no way to disable it (thinking_budget=0 is rejected as
    # an invalid argument on this model). A caller-specified max_tokens
    # (e.g. 300 for the SQL corrector, sized for OpenAI/Anthropic's
    # answer-only budgets) can be entirely consumed by thinking, leaving
    # an empty response. Enforce a generous floor so thinking + answer
    # both fit; this only widens the ceiling; it doesn't force verbosity.
    resolved_max_tokens = max(max_tokens or 0, 2048)

    config_kwargs: dict = {
        "temperature": temperature,
        "max_output_tokens": resolved_max_tokens,
    }
    if system:
        config_kwargs["system_instruction"] = system

    resolved_model = model or settings.GEMINI_MODEL
    try:
        response = client.models.generate_content(
            model=resolved_model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as e:
        raise LLMError(f"Gemini completion failed: {e}") from e

    if not response.text:
        raise LLMError(f"Gemini returned empty response (finish_reason may indicate why)")

    if response.usage_metadata:
        prompt_tokens = response.usage_metadata.prompt_token_count or 0
        completion_tokens = (response.usage_metadata.candidates_token_count or 0) + (response.usage_metadata.thoughts_token_count or 0)
        record_usage("gemini", resolved_model, prompt_tokens, completion_tokens)

    return response.text.strip()
