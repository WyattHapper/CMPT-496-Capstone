"""
agent/llm.py

The one place the agents get their Gemini model from.

Each agent used to build its own ChatGoogleGenerativeAI with the same eight
lines, so the model name lived in six files and none of them coped with
Google pushing back. make_llm() replaces those blocks and returns a model
that waits and retries instead of failing the run:

    429 Too Many Requests  per-minute limit: wait as long as Google asks
                           daily limit: stop at once with a clear message
    503 and friends        Google busy: back off and retry

Google's SDK has its own retry, but it ignores the wait Google asks for on a
429 and gives up within seconds, so it is switched off (max_retries=1) and
this module does the waiting.
"""

import asyncio
import os
import random
import re
import time

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.progress_logging import progress
from backend.token_usage import record_wait, status_code


GEMINI_MODEL = "gemini-3-flash-preview"

# Longest one AI call keeps waiting and retrying before the run fails. Long
# enough to sit out a per-minute limit several times over and most "model
# overloaded" (503) spells on the preview model, which outlasted 5 minutes in
# a free-tier run on 2026-09-23.
RETRY_BUDGET_SECONDS = 600

# Wait on a 429 when Google does not say how long.
DEFAULT_RATE_LIMIT_WAIT = 30

# Google-side hiccups: back off 2, 4, 8 ... seconds, capped.
BACKOFF_START_SECONDS = 2
BACKOFF_MAX_SECONDS = 60

# Retrying these can help. 429 is handled separately.
TRANSIENT_STATUS_CODES = {408, 500, 502, 503, 504}


class DailyLimitError(RuntimeError):
    """The API key's daily quota is used up; waiting minutes will not help."""


class RateLimitTimeoutError(RuntimeError):
    """Google kept refusing for the whole retry budget."""


def _is_daily_limit(exc):
    # Google names the exhausted quota, e.g.
    # "GenerateRequestsPerDayPerProjectPerModel-FreeTier".
    return "PerDay" in str(exc)


def _suggested_wait(exc):
    """
    Seconds Google asked us to wait, from its RetryInfo ("retryDelay": "31s").
    Falls back to DEFAULT_RATE_LIMIT_WAIT.
    """
    match = re.search(r"retry_?[dD]elay['\"]?\s*[:{]\s*['\"]?(?:seconds:\s*)?(\d+(?:\.\d+)?)", str(exc))

    if match:
        return float(match.group(1))

    return DEFAULT_RATE_LIMIT_WAIT


def _plan_retry(exc, attempt, waited):
    """
    Decide what to do after a failed call.

    Returns (seconds_to_wait, reason) to retry, or raises to give up.
    """
    # A 429 arrives as LangChain's error wrapping the SDK's ClientError; a
    # 503 as the SDK's ServerError itself. status_code() handles both.
    code = status_code(exc)

    if code == 429:
        if _is_daily_limit(exc):
            raise DailyLimitError(
                "Daily AI limit reached on this API key. Try again tomorrow, "
                "or use a key with a higher limit (e.g. Tier 1)."
            ) from exc

        # A little jitter so a batch of calls that all hit the limit together
        # does not all retry in the same instant.
        wait = _suggested_wait(exc) + random.uniform(0, 3)
        reason = "429"

    elif code in TRANSIENT_STATUS_CODES:
        wait = min(BACKOFF_START_SECONDS * (2 ** attempt), BACKOFF_MAX_SECONDS)
        wait += random.uniform(0, 1)
        reason = str(code)

    else:
        raise exc

    if waited + wait > RETRY_BUDGET_SECONDS:
        minutes = RETRY_BUDGET_SECONDS // 60

        if reason == "429":
            message = (
                f"Google kept rate-limiting this API key for over {minutes} "
                "minutes, so the run stopped. Wait a few minutes and try "
                "again, or use a key with a higher limit (e.g. Tier 1)."
            )
        else:
            # Seen on the free tier: Google is up but turns this key's
            # requests away while the model is busy; paid traffic goes first.
            message = (
                "Google's AI was overloaded and kept turning away requests "
                f"from this API key for over {minutes} minutes (common on the "
                "free tier), so the run stopped. Try again later, or use a "
                "Tier 1 key."
            )

        raise RateLimitTimeoutError(message) from exc

    return wait, reason


def _announce(reason, wait):
    if reason == "429":
        message = f"Google rate limit reached, waiting {wait:.0f} s before retrying..."
    else:
        message = f"Google's AI is busy ({reason}), waiting {wait:.0f} s before retrying..."

    progress(message)
    record_wait(reason, wait)


class CheckpointGemini(ChatGoogleGenerativeAI):
    """
    ChatGoogleGenerativeAI that waits out rate limits and busy servers.

    Retrying inside _generate/_agenerate, rather than wrapping the model, keeps
    it a chat model: the agents' with_structured_output() still works, and
    token recording sees one call per successful answer.
    """

    def _generate(self, *args, **kwargs):
        attempt, waited = 0, 0.0

        while True:
            try:
                return super()._generate(*args, **kwargs)
            except Exception as exc:
                wait, reason = _plan_retry(exc, attempt, waited)

            _announce(reason, wait)
            time.sleep(wait)
            attempt, waited = attempt + 1, waited + wait

    async def _agenerate(self, *args, **kwargs):
        attempt, waited = 0, 0.0

        while True:
            try:
                return await super()._agenerate(*args, **kwargs)
            except Exception as exc:
                wait, reason = _plan_retry(exc, attempt, waited)

            _announce(reason, wait)
            await asyncio.sleep(wait)
            attempt, waited = attempt + 1, waited + wait


def make_llm():
    """
    The Gemini model every agent uses unless a test passes its own.
    """
    load_dotenv(override=True)

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")

    return CheckpointGemini(
        model=GEMINI_MODEL,
        api_key=api_key,
        # 1 = no SDK retries (0 would mean "SDK default"); see module docstring.
        max_retries=1,
    )
