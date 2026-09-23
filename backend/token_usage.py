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
import os
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration
from langchain_core.tracers.context import register_configure_hook


USAGE_LOG_NAME = "token_usage_log.json"

# The most recent run in full: its stages, every AI call, timings and
# outcome. Rewritten each run; token_usage_log.json keeps the per-stage
# totals the calibration reads.
RUN_LOG_NAME = "last_run_log.json"


def _read_usage(response):
    """
    Pull (usage_metadata, model_name) out of a chat model response.

    Returns None when the response is not a chat generation. Either value in
    the pair can be None: some providers omit the model name or the usage.
    """

    try:
        generation = response.generations[0][0]
    except (IndexError, AttributeError):
        return None

    if not isinstance(generation, ChatGeneration):
        return None

    message = getattr(generation, "message", None)

    if not isinstance(message, AIMessage):
        return None

    usage = getattr(message, "usage_metadata", None)

    model_name = None
    try:
        model_name = message.response_metadata.get("model_name")
    except AttributeError:
        pass

    return usage, model_name


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

        read = _read_usage(response)

        if read is None:
            return

        usage, model_name = read

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

    def __init__(self, recorders, run_log=None, stage=None):
        super().__init__()
        self.recorders = recorders

        # Captured when the scope opens rather than looked up per call: the
        # agents' batches can finish calls on other threads or tasks.
        self.run_log = run_log
        self.stage = stage

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        if self.run_log:
            self.run_log.call_started(run_id)

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        if self.run_log:
            self.run_log.call_started(run_id)

    def on_llm_end(self, response, **kwargs):
        for recorder in self.recorders:
            recorder.on_llm_end(response, **kwargs)

        if self.run_log:
            self.run_log.call_ended(
                kwargs.get("run_id"), self.stage, response=response
            )

    def on_llm_error(self, error, *, run_id, **kwargs):
        # A rejected call (e.g. 429 Too Many Requests) never reaches
        # on_llm_end, so without this a failed run would show no trace of it.
        if self.run_log:
            self.run_log.call_ended(run_id, self.stage, error=error)


# ContextVar + configure hook is how langchain-core wires its own usage
# callback; registering the same way means every model call inside the scope
# picks the handler up, with no change to the agents.
_usage_var: ContextVar = ContextVar("checkpoint_usage_recorder", default=None)
register_configure_hook(_usage_var, inheritable=True)

# The recorders currently open, outermost first.
_stack_var: ContextVar = ContextVar("checkpoint_usage_stack", default=())

# The run being logged, and which of its stages is running. Set by
# track_command; None outside a command.
_run_var: ContextVar = ContextVar("checkpoint_run_log", default=None)
_stage_var: ContextVar = ContextVar("checkpoint_run_stage", default=None)


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
    usage_token = _usage_var.set(
        _Fanout(stack, _run_var.get(), _stage_var.get())
    )

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
# Run log
# ---------------------------------------------------------
# token_usage_log.json keeps one total per stage and overwrites stage by
# stage, so after a failed run it silently mixes two runs. This records one
# whole run under a run ID -- stages, every AI call, timings, outcome.
#
# Logging must never cost a run: every write is best-effort.

def _stamp(moment=None):
    return (moment or datetime.now()).isoformat(timespec="seconds")


class RunLog:
    """
    Everything one run did, saved to last_run_log.json as it goes.
    """

    def __init__(self, app_dir, codebase_name, command):
        now = datetime.now()

        self.path = Path(app_dir) / RUN_LOG_NAME
        self.run_id = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.codebase = codebase_name
        self.command = command
        self.started_at = _stamp(now)
        self.finished_at = None
        self.elapsed_seconds = None
        self.status = "running"
        self.error = None

        self.stages = []
        self.calls = []

        self._t0 = time.perf_counter()
        self._stage_t0 = {}
        self._open_calls = {}
        self._lock = threading.Lock()

    # --- stages -------------------------------------------

    def start_stage(self, name):
        entry = {
            "stage": name,
            "status": "running",
            "error": None,
            "started_at": _stamp(),
            "elapsed_seconds": None,
        }

        with self._lock:
            self.stages.append(entry)
            self._stage_t0[id(entry)] = time.perf_counter()

        return entry

    def finish_stage(self, entry, status, error):
        with self._lock:
            t0 = self._stage_t0.pop(id(entry), self._t0)
            entry["status"] = status
            entry["error"] = error
            entry["elapsed_seconds"] = round(time.perf_counter() - t0, 2)

    def finish(self, status, error):
        with self._lock:
            self.status = status
            self.error = error
            self.finished_at = _stamp()
            self.elapsed_seconds = round(time.perf_counter() - self._t0, 2)

    # --- AI calls -----------------------------------------

    def call_started(self, call_id):
        with self._lock:
            self._open_calls[call_id] = (datetime.now(), time.perf_counter())

    def call_ended(self, call_id, stage, response=None, error=None):
        with self._lock:
            started = self._open_calls.pop(call_id, None)

        record = {
            "stage": stage or self.command,
            "started_at": _stamp(started[0]) if started else None,
            "duration_seconds": (
                round(time.perf_counter() - started[1], 2) if started else None
            ),
            "status": "failed" if error is not None else "success",
            "model": None,
            "input_tokens": None,
            "output_tokens": None,
        }

        if error is not None:
            record["error"] = str(error)
        else:
            read = _read_usage(response)

            if read is not None:
                usage, model_name = read
                record["model"] = model_name

                if usage:
                    record["input_tokens"] = usage.get("input_tokens", 0) or 0
                    record["output_tokens"] = usage.get("output_tokens", 0) or 0

        with self._lock:
            self.calls.append(record)

    # --- output -------------------------------------------

    def _worth_saving(self):
        # Only runs that used the AI, plus the full pipeline even if it
        # failed before its first call. Otherwise a token estimate or a UML
        # export afterwards would overwrite the run you want to look at.
        return bool(self.calls) or self.command == "full_pipeline"

    def to_dict(self):
        with self._lock:
            calls = [dict(c) for c in self.calls]
            stages = [dict(s) for s in self.stages]
            header = {
                "run_id": self.run_id,
                "codebase": self.codebase,
                "command": self.command,
                "status": self.status,
                "error": self.error,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "elapsed_seconds": self.elapsed_seconds,
            }

        def totals(subset):
            input_tokens = sum(c["input_tokens"] or 0 for c in subset)
            output_tokens = sum(c["output_tokens"] or 0 for c in subset)
            return {
                "calls": len(subset),
                "failed_calls": sum(c["status"] == "failed" for c in subset),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            }

        for stage in stages:
            stage.update(totals([c for c in calls if c["stage"] == stage["stage"]]))

        return {
            **header,
            "totals": totals(calls),
            "stages": stages,
            "calls": calls,
        }

    def save(self):
        try:
            if not self._worth_saving():
                return

            # Write then swap, so a crash mid-write never leaves half a file.
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except Exception:
            pass


class _Outcome:
    """How a tracked command ended; _run_command marks failures on it."""

    def __init__(self):
        self.status = "success"
        self.error = None

    def fail(self, exc):
        self.status = "failed"
        self.error = str(exc)


@contextmanager
def track_command(app_dir, codebase_name, command):
    """
    Time a command for last_run_log.json.

    The outermost command is the run. Commands it calls directly are its
    stages -- for the full pipeline, the steps shown on the Complete screen.
    Anything nested deeper counts toward the stage it runs in.
    """

    outcome = _Outcome()
    run = _run_var.get()

    if run is None:
        run = RunLog(app_dir, codebase_name, command)
        token = _run_var.set(run)
        try:
            yield outcome
        except BaseException as exc:
            outcome.fail(exc)
            raise
        finally:
            _run_var.reset(token)
            run.finish(outcome.status, outcome.error)
            run.save()

    elif _stage_var.get() is None:
        entry = run.start_stage(command)
        token = _stage_var.set(command)
        try:
            yield outcome
        except BaseException as exc:
            outcome.fail(exc)
            raise
        finally:
            _stage_var.reset(token)
            run.finish_stage(entry, outcome.status, outcome.error)
            # Saved per stage so a run that dies mid-way still leaves a
            # record of how far it got.
            run.save()

    else:
        yield outcome


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
