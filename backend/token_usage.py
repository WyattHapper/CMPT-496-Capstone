"""
backend/token_usage.py

Records what the pipeline *actually* spent, so the guesses in
token_estimate.py can be replaced with measurements.

The estimator predicts; this module observes. Run a real pipeline once with
this active, then call suggest_constants() to get calibrated values.

How it hooks in
---------------
LangChain reports per-call usage on AIMessage.usage_metadata. A callback
handler registered through a ContextVar sees every chat model call inside its
scope -- including the agents' asyncio.gather batches -- so wrapping one place
in commands.py captures all six agents without touching any agent file.

langchain-core ships get_usage_metadata_callback() which does something
similar, but it drops any call whose response_metadata lacks "model_name"
(see UsageMetadataCallbackHandler.on_llm_end). That silent discard would
undercount, so this records usage whether or not a model name is present.
"""

import json
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration
from langchain_core.tracers.context import register_configure_hook


USAGE_LOG_NAME = "token_usage_log.json"


class UsageRecorder(BaseCallbackHandler):
    """
    Accumulates token usage across every chat model call in its scope.
    """

    # Emit at most this often, so a 500-file run does not flood stdout with
    # one progress line per call.
    LIVE_INTERVAL_SECONDS = 0.5

    def __init__(self, stage: str = "unknown"):
        super().__init__()
        self.stage = stage
        self.calls = 0
        self.calls_missing_usage = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.models = set()
        self.live = False
        self._last_emit = 0.0
        self._lock = threading.Lock()

    def on_llm_end(self, response, **kwargs):

        try:
            generation = response.generations[0][0]
        except (IndexError, AttributeError):
            return

        if not isinstance(generation, ChatGeneration):
            return

        message = getattr(generation, "message", None)

        if not isinstance(message, AIMessage):
            return

        usage = getattr(message, "usage_metadata", None)

        model_name = None
        try:
            model_name = message.response_metadata.get("model_name")
        except AttributeError:
            pass

        with self._lock:

            self.calls += 1

            if model_name:
                self.models.add(model_name)

            # Deliberately not gated on model_name: a provider that omits it
            # would otherwise vanish from the totals without warning.
            if not usage:
                self.calls_missing_usage += 1
                return

            should_emit = False

            self.input_tokens += usage.get("input_tokens", 0) or 0
            self.output_tokens += usage.get("output_tokens", 0) or 0

            should_emit = (
                self.live
                and (time.monotonic() - self._last_emit)
                >= self.LIVE_INTERVAL_SECONDS
            )

            if should_emit:
                self._last_emit = time.monotonic()
                snapshot = (self.calls, self.input_tokens, self.output_tokens)

        # Printing outside the lock: stdout is shared with the progress
        # stream and holding the lock across a write invites contention
        # between the agents' concurrent batches.
        if should_emit:
            emit_live_total(*snapshot)

    def summary(self):
        return {
            "stage": self.stage,
            "calls": self.calls,
            "calls_missing_usage": self.calls_missing_usage,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "models": sorted(self.models),
            "tokens_per_call": (
                round((self.input_tokens) / self.calls, 1)
                if self.calls else 0
            ),
        }


class _Fanout(BaseCallbackHandler):
    """
    Forwards every model call to all recorders currently in scope.

    A single ContextVar holds one handler, so a nested `with record_usage(...)`
    would otherwise shadow the outer one -- the full pipeline would see only
    the calls made directly in its own scope, not those inside its stages.
    Holding a tuple of recorders and fanning out means a stage and the
    pipeline around it both count the same call.
    """

    def __init__(self, recorders):
        super().__init__()
        self.recorders = recorders

    def on_llm_end(self, response, **kwargs):
        for recorder in self.recorders:
            recorder.on_llm_end(response, **kwargs)


# ContextVar + configure hook is how langchain-core wires its own usage
# callback; registering the same way means every model call inside the scope
# picks the handler up, with no change to the agents.
_usage_var: ContextVar = ContextVar("checkpoint_usage_recorder", default=None)
register_configure_hook(_usage_var, inheritable=True)

# The recorders currently open, outermost first.
_stack_var: ContextVar = ContextVar("checkpoint_usage_stack", default=())


@contextmanager
def record_usage(stage: str = "unknown", live: bool = False):
    """
    Capture token usage for everything that runs inside this block.

    Nests: an outer scope also counts calls made inside inner scopes.

        with record_usage("full_pipeline") as total:
            with record_usage("generate_file_summaries") as stage:
                ...

    live=True streams a running total to the frontend as calls complete.
    """

    recorder = UsageRecorder(stage)

    outer = _stack_var.get()

    # Only the outermost live scope streams. Otherwise a stage and the
    # pipeline around it both emit, and the on-screen counter flips between
    # the stage's subtotal and the real total.
    recorder.live = live and not any(r.live for r in outer)

    stack = outer + (recorder,)

    stack_token = _stack_var.set(stack)
    usage_token = _usage_var.set(_Fanout(stack))

    try:
        yield recorder
    finally:
        _usage_var.reset(usage_token)
        _stack_var.reset(stack_token)


def emit_live_total(calls, input_tokens, output_tokens):
    """
    Stream a running total to the frontend.

    Its own message type, so the renderer can update a counter without it
    being mistaken for a progress step.
    """
    print(
        json.dumps({
            "type": "token_usage",
            "calls": calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }),
        flush=True,
    )


def emit_stage_total(summary):
    """
    Announce one finished stage's usage, so the frontend can build up a
    per-stage breakdown while the pipeline is still running.
    """
    print(
        json.dumps({
            "type": "token_usage_stage",
            "stage": summary["stage"],
            "calls": summary["calls"],
            "input_tokens": summary["input_tokens"],
            "output_tokens": summary["output_tokens"],
        }),
        flush=True,
    )


# ---------------------------------------------------------
# Persistence
# ---------------------------------------------------------

def log_path(app_dir: Path) -> Path:
    return Path(app_dir) / USAGE_LOG_NAME


def load_log(app_dir: Path) -> dict:
    path = log_path(app_dir)

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def record_to_log(app_dir: Path, codebase_name: str, summary: dict):
    """
    Append one stage's measured usage to the log.

    Stages with no LLM calls are skipped -- they would only add noise.
    """

    if summary.get("calls", 0) == 0:
        return

    data = load_log(app_dir)

    per_codebase = data.setdefault(codebase_name, {})

    entry = dict(summary)
    entry["recorded_at"] = datetime.now().isoformat(timespec="seconds")

    per_codebase[summary["stage"]] = entry

    try:
        log_path(app_dir).write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


# ---------------------------------------------------------
# Calibration
# ---------------------------------------------------------

# Which estimator constant each stage's measurement should feed.
STAGE_TO_CONSTANT = {
    "generate_directory_summaries": "DIRECTORY_TOKENS_PER_CALL",
    "validate_business_rules": "BR_TOKENS_PER_CALL",
    "generate_unit_tests": "UNIT_TEST_TOKENS_PER_CALL",
    "generate_integration_tests": "INTEGRATION_TEST_TOKENS_PER_CALL",
}


def suggest_constants(app_dir: Path, codebase_name: str = None):
    """
    Turn recorded runs into replacement values for token_estimate.py.

    Returns a dict of constant name -> measured average input tokens per call,
    plus the evidence each figure rests on.
    """

    data = load_log(app_dir)

    if not data:
        return {
            "success": False,
            "error": (
                "No usage recorded yet. Run the pipeline once, then ask for "
                "calibration again."
            ),
        }

    if codebase_name:
        sources = {codebase_name: data.get(codebase_name, {})}
    else:
        sources = data

    suggestions = {}
    evidence = []

    for cb_name, stages in sources.items():

        for stage, entry in stages.items():

            constant = STAGE_TO_CONSTANT.get(stage)

            if not constant or not entry.get("calls"):
                continue

            per_call = entry["input_tokens"] / entry["calls"]

            # Average across codebases when more than one has been run.
            prior = suggestions.get(constant)
            suggestions[constant] = (
                round((prior + per_call) / 2)
                if prior
                else round(per_call)
            )

            evidence.append({
                "codebase": cb_name,
                "stage": stage,
                "constant": constant,
                "calls": entry["calls"],
                "input_tokens": entry["input_tokens"],
                "tokens_per_call": round(per_call),
                "missing_usage": entry.get("calls_missing_usage", 0),
            })

    # The file summary prompt is measured directly, not averaged.
    file_stage = None
    for cb_name, stages in sources.items():
        if "generate_file_summaries" in stages:
            file_stage = stages["generate_file_summaries"]
            break

    return {
        "success": True,
        "suggestions": suggestions,
        "evidence": evidence,
        "file_summary_actual": file_stage,
        "message": format_calibration(suggestions, evidence, file_stage),
    }


def format_calibration(suggestions, evidence, file_stage):

    lines = []
    lines.append("Calibration from recorded runs")
    lines.append("")

    if not evidence:
        lines.append("  No stages with recorded LLM calls yet.")
        return "\n".join(lines)

    lines.append("  Measured:")
    for e in evidence:
        lines.append(
            f"    {e['stage']:<32} {e['calls']:>5} calls  "
            f"{e['tokens_per_call']:>8,} tok/call"
        )
        if e["missing_usage"]:
            lines.append(
                f"      ({e['missing_usage']} calls reported no usage "
                f"metadata and are excluded)"
            )

    if file_stage:
        lines.append("")
        lines.append(
            f"    generate_file_summaries: {file_stage['calls']} calls, "
            f"{file_stage['input_tokens']:,} input tokens"
        )

    lines.append("")
    lines.append("  Replace in backend/token_estimate.py:")
    for name, value in sorted(suggestions.items()):
        lines.append(f"    {name} = {value}")

    return "\n".join(lines)
