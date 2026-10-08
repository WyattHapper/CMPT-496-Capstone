"""
agent/llm.py

The one place the agents get their chat model from.

make_llm() reads the key the user selected in "Manage API Keys" (the
ACTIVE_LLM_* values main.js writes to .env) and returns the matching
LangChain chat model for that provider. Every model it returns waits and
retries instead of failing the run:

    429 rate limit   per-minute: wait as long as the provider asks
                     daily limit / out of credit: stop at once, clear message
    503 and friends  provider busy: back off and retry
    network errors   back off and retry

The providers' own SDK retries are switched off (or minimised) because they
give up within seconds and ignore the wait the provider asks for.
"""

import asyncio
import random
import re
import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values

from backend.progress_logging import progress
from backend.token_usage import record_wait, status_code


# Kept so older imports keep working, and used as the model for a legacy
# GOOGLE_API_KEY that has not been migrated yet.
GEMINI_MODEL = "gemini-3-flash-preview"

# Must match where main.js puts the .env (the exe's folder, or the repo root).
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

ENV_PATH = APP_DIR / ".env"

PROVIDER_NAMES = {
    "google": "Google",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "mistral": "Mistral",
    "groq": "Groq",
    "deepseek": "DeepSeek",
    "xai": "xAI",
    "openrouter": "OpenRouter",
}

OPENROUTER_URL = "https://openrouter.ai/api/v1"

# Anthropic requires an explicit output cap on every call.
DEFAULT_MAX_TOKENS = {"anthropic": 8192}

# Longest one AI call keeps waiting and retrying before the run fails.
RETRY_BUDGET_SECONDS = 600

# Wait on a 429 when the provider does not say how long.
DEFAULT_RATE_LIMIT_WAIT = 30

# Back off 2, 4, 8 ... seconds, capped.
BACKOFF_START_SECONDS = 2
BACKOFF_MAX_SECONDS = 60

# Retrying these can help. 429 is handled separately.
TRANSIENT_STATUS_CODES = {408, 500, 502, 503, 504}

NETWORK_ERROR_NAMES = {
    "APIConnectionError", "APITimeoutError", "ConnectError", "ConnectTimeout",
    "ReadTimeout", "RemoteProtocolError", "Timeout",
}

# A 429 containing one of these will not clear in a few minutes.
QUOTA_EXHAUSTED_MARKERS = (
    "perday", "per day", "(rpd)", "(tpd)", "insufficient_quota",
)


class DailyLimitError(RuntimeError):
    """The key's daily quota is used up or it is out of credit."""


class RateLimitTimeoutError(RuntimeError):
    """The provider kept refusing for the whole retry budget."""


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: str


def get_active_config() -> LLMConfig:
    """
    Read the selected key fresh from .env on every call, so changing the key
    or model in the UI takes effect without restarting the backend.
    """
    env = dotenv_values(ENV_PATH)

    key = (env.get("ACTIVE_LLM_API_KEY") or "").strip()
    provider = (env.get("ACTIVE_LLM_PROVIDER") or "").strip().lower()
    model = (env.get("ACTIVE_LLM_MODEL") or "").strip()

    if not key:
        # An old .env that main.js has not migrated yet.
        legacy = (env.get("GOOGLE_API_KEY") or "").strip()
        if legacy:
            return LLMConfig("google", GEMINI_MODEL, legacy)

        raise ValueError(
            "No API key is selected. Open Manage API Keys to add or select one."
        )

    if provider not in PROVIDER_NAMES:
        raise ValueError(f"Unsupported provider in .env: '{provider}'.")

    if not model:
        raise ValueError(
            "The selected API key has no model set. Enter a model name in "
            "Manage API Keys."
        )

    return LLMConfig(provider, model, key)


# ---------------------------------------------------------
# Retry logic (provider-neutral)
# ---------------------------------------------------------

def _chain(exc):
    """The error and everything it was raised from."""
    seen = set()

    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def _is_quota_exhausted(exc):
    return any(
        marker in str(link).lower()
        for link in _chain(exc)
        for marker in QUOTA_EXHAUSTED_MARKERS
    )


def _is_network_error(exc):
    return any(type(link).__name__ in NETWORK_ERROR_NAMES for link in _chain(exc))


def _suggested_wait(exc):
    """
    Seconds the provider asked us to wait: a Retry-After header, Google's
    RetryInfo ("retryDelay": "31s"), or "try again in 6.5s" in the message.
    Falls back to DEFAULT_RATE_LIMIT_WAIT.
    """
    for link in _chain(exc):
        headers = getattr(getattr(link, "response", None), "headers", None)

        if headers:
            try:
                value = headers.get("retry-after")
                if value:
                    return float(value)
            except (TypeError, ValueError, AttributeError):
                pass

    text = str(exc)

    match = re.search(
        r"retry_?[dD]elay['\"]?\s*[:{]\s*['\"]?(?:seconds:\s*)?(\d+(?:\.\d+)?)", text
    )
    if match:
        return float(match.group(1))

    match = re.search(r"try again in (\d+(?:\.\d+)?)\s*(ms|s|m)\b", text, re.I)
    if match:
        amount, unit = float(match.group(1)), match.group(2).lower()
        return amount / 1000 if unit == "ms" else amount * 60 if unit == "m" else amount

    return DEFAULT_RATE_LIMIT_WAIT


def _plan_retry(exc, attempt, waited, label):
    """
    Decide what to do after a failed call.

    Returns (seconds_to_wait, reason) to retry, or raises to give up.
    """
    code = status_code(exc)

    if code == 429:
        if _is_quota_exhausted(exc):
            raise DailyLimitError(
                f"This {label} API key has hit its daily limit or is out of "
                "credit. Try again later, check your plan and billing, or "
                "select a different key."
            ) from exc

        # Jitter so a batch of calls that hit the limit together does not
        # all retry in the same instant.
        wait = _suggested_wait(exc) + random.uniform(0, 3)
        reason = "429"

    elif code in TRANSIENT_STATUS_CODES or (code is None and _is_network_error(exc)):
        wait = min(BACKOFF_START_SECONDS * (2 ** attempt), BACKOFF_MAX_SECONDS)
        wait += random.uniform(0, 1)
        reason = str(code) if code else "network"

    else:
        raise exc

    if waited + wait > RETRY_BUDGET_SECONDS:
        minutes = RETRY_BUDGET_SECONDS // 60

        if reason == "429":
            message = (
                f"{label} kept rate-limiting this API key for over {minutes} "
                "minutes, so the run stopped. Wait a few minutes and try "
                "again, or use a key with a higher limit."
            )
        else:
            message = (
                f"{label} was unavailable or kept turning away requests for "
                f"over {minutes} minutes, so the run stopped. Try again "
                "later, or select a different key."
            )

        raise RateLimitTimeoutError(message) from exc

    return wait, reason


def _announce(reason, wait, label):
    if reason == "429":
        message = f"{label} rate limit reached, waiting {wait:.0f} s before retrying..."
    elif reason == "network":
        message = f"Connection to {label} failed, waiting {wait:.0f} s before retrying..."
    else:
        message = f"{label}'s AI is busy ({reason}), waiting {wait:.0f} s before retrying..."

    progress(message)
    record_wait(reason, wait)


@lru_cache(maxsize=None)
def _retrying(base, label):
    """
    A subclass of the given LangChain chat model that waits out rate limits
    and busy servers.

    Retrying inside _generate/_agenerate, rather than wrapping the model, keeps
    it a chat model: the agents' with_structured_output() still works, and
    token recording sees one call per successful answer.
    """

    def _generate(self, *args, **kwargs):
        attempt, waited = 0, 0.0

        while True:
            try:
                return base._generate(self, *args, **kwargs)
            except Exception as exc:
                wait, reason = _plan_retry(exc, attempt, waited, label)

            _announce(reason, wait, label)
            time.sleep(wait)
            attempt, waited = attempt + 1, waited + wait

    async def _agenerate(self, *args, **kwargs):
        attempt, waited = 0, 0.0

        while True:
            try:
                return await base._agenerate(self, *args, **kwargs)
            except Exception as exc:
                wait, reason = _plan_retry(exc, attempt, waited, label)

            _announce(reason, wait, label)
            await asyncio.sleep(wait)
            attempt, waited = attempt + 1, waited + wait

    return type(
        f"Checkpoint{base.__name__}",
        (base,),
        {"__module__": __name__, "_generate": _generate, "_agenerate": _agenerate},
    )


# ---------------------------------------------------------
# Model construction
# ---------------------------------------------------------

def build_chat_model(config: LLMConfig, max_output_tokens=None, retry=True):
    """
    The LangChain chat model for one provider.

    Imports are inside the branches so a provider's package is only needed
    when that provider is used (PyInstaller still finds them).
    """
    provider = config.provider
    label = PROVIDER_NAMES[provider]
    limit = max_output_tokens or DEFAULT_MAX_TOKENS.get(provider)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI as model_class
        # 1 = no SDK retries (0 would mean "SDK default").
        kwargs = dict(max_retries=1)
        if limit:
            kwargs["max_output_tokens"] = limit

    elif provider in ("openai", "openrouter"):
        from langchain_openai import ChatOpenAI as model_class
        kwargs = dict(max_retries=0)
        if provider == "openrouter":
            kwargs["base_url"] = OPENROUTER_URL
        if limit:
            kwargs["max_tokens"] = limit

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic as model_class
        kwargs = dict(max_retries=0, max_tokens=limit)

    elif provider == "mistral":
        from langchain_mistralai import ChatMistralAI as model_class
        kwargs = dict(max_retries=1)
        if limit:
            kwargs["max_tokens"] = limit

    elif provider == "groq":
        from langchain_groq import ChatGroq as model_class
        kwargs = dict(max_retries=0)
        if limit:
            kwargs["max_tokens"] = limit

    elif provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek as model_class
        kwargs = dict(max_retries=0)
        if limit:
            kwargs["max_tokens"] = limit

    elif provider == "xai":
        from langchain_xai import ChatXAI as model_class
        kwargs = dict(max_retries=0)
        if limit:
            kwargs["max_tokens"] = limit

    else:
        raise ValueError(f"Unsupported provider: {provider}")

    if retry:
        model_class = _retrying(model_class, label)

    return model_class(model=config.model, api_key=config.api_key, **kwargs)


def make_llm(max_output_tokens=None):
    """
    The chat model every agent uses unless a test passes its own.

    max_output_tokens caps one answer (thinking included on models that
    think). Left unset, each provider uses its own default.
    """
    return build_chat_model(get_active_config(), max_output_tokens)


# ---------------------------------------------------------
# Key verification
# ---------------------------------------------------------

def verify_llm_key(provider, model, api_key):
    """
    Check a key by making one tiny real call with the exact provider and model
    the pipeline will use, so a key with no access to that model is caught now
    rather than part-way through a run.

    Returns {"status": "accepted" | "rejected" | "unverified", "message", ...}.
    "unverified" means we could not ask (network down, rate limited): that is
    not a rejection, so the key can still be saved.
    """
    provider = (provider or "").strip().lower()

    if provider not in PROVIDER_NAMES:
        raise ValueError(f"Unsupported provider: '{provider}'.")

    label = PROVIDER_NAMES[provider]
    config = LLMConfig(provider, model, api_key)

    # Not inside the try: a missing package should surface as an error, not
    # be mistaken for an unverifiable key.
    llm = build_chat_model(config, max_output_tokens=32, retry=False)

    try:
        reply = llm.invoke("hi")

    except Exception as exc:
        code = status_code(exc)
        detail = str(exc).strip()[:300] or type(exc).__name__

        if code is None or code in (408, 429) or code >= 500:
            return {
                "status": "unverified",
                "message": f"Key saved, but not verified. Could not confirm with {label} ({detail}).",
                "model": None,
                "tokens": None,
            }

        return {
            "status": "rejected",
            "message": f"{label} rejected this key or model: {detail}",
            "model": None,
            "tokens": None,
        }

    usage = getattr(reply, "usage_metadata", None) or {}
    tokens = usage.get("total_tokens")
    answered_by = (
        (getattr(reply, "response_metadata", None) or {}).get("model_name") or model
    )

    cost = f" - {tokens} {'token' if tokens == 1 else 'tokens'} used" if tokens else ""

    return {
        "status": "accepted",
        "message": f"Key verified against {answered_by}{cost}. Saved.",
        "model": answered_by,
        "tokens": tokens,
    }