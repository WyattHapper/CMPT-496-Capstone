"""
backend/token_estimate.py

Estimates Gemini token usage for the analysis pipeline *before* it runs.

Nothing in here calls an LLM. It walks the codebase, measures how much text
each stage would send, and reports a per-stage breakdown.

Accuracy is deliberately labelled rather than assumed. Every stage carries a
confidence:

    exact      - fully computable now (file count x known prompt + file text)
    range      - call count is bounded but the LLM decides where in the range
    projected  - depends on an assumption constant below
    unknown    - depends on artifacts a previous stage has not produced yet

Counting uses tiktoken (OpenAI's tokenizer) as a stand-in for Gemini's, which
is close enough for planning but not exact. Rather than tokenize every file --
slow on large trees -- it tokenizes a sample and extrapolates by character
ratio, per file extension.
"""

import os
import json
import random
from pathlib import Path

import tiktoken


# ---------------------------------------------------------
# Crawl rules
# ---------------------------------------------------------
# Imported, not copied: the estimate has to use exactly the rules the
# crawlers use or it quietly predicts the wrong thing.

from agent.crawl_config import ACCEPTABLE_EXTENSIONS, IGNORED_DIRS  # noqa: E402


# ---------------------------------------------------------
# Assumptions
# ---------------------------------------------------------
# Everything uncertain is collected here so it is visible and tunable rather
# than scattered through the code. Calibrate these against a real run.

# Measured from the prompt template in agent/file_summary_agent.py
# (_summarize_one, the block from "### Tasks" to "File path:").
FILE_SUMMARY_PROMPT_TOKENS = 993

# Per directory, directory_agent runs: context_analyser + summarizer +
# judgement + business_rules_extractor. The context-retrieval loop and up to
# 2 refinement rounds push the upper end higher.
# CALIBRATED 2026-09-20 (ConsoleTables): 17 calls over 5 directories = 3.4
# per directory, below the theoretical minimum of 4 -- the root directory
# takes a different path through the graph, so not every directory pays for
# every node.
DIRECTORY_CALLS_MIN = 3
DIRECTORY_CALLS_MAX = 8

# All four per-call figures below are MEASURED, from a full pipeline run on
# ConsoleTables (2026-09-20). Re-derive them any time with the "Show Token
# Calibration" button, which reads backend/token_usage.py's log.
# Caveat: one run, on a 4-file codebase. Treat as far better than the
# original guesses but not yet well-generalised.
DIRECTORY_TOKENS_PER_CALL = 6639

# Business rule validation: one condense call per directory group plus one
# validation call per rule.
BR_TOKENS_PER_CALL = 5323

# One generation call per validated rule / per workflow.
UNIT_TEST_TOKENS_PER_CALL = 6130
INTEGRATION_TEST_TOKENS_PER_CALL = 13288

# Output tokens are unknowable up front.
# CALIBRATED: the measured run came out at 36% of input, well above the
# 10-25% originally assumed -- unit test generation alone produced 65,290
# output tokens against 85,824 input. Structured generation is not the small
# tail the first guess treated it as.
OUTPUT_RATIO_LOW = 0.25
OUTPUT_RATIO_HIGH = 0.45

# tiktoken's cl100k_base splits text more coarsely than Gemini does.
# MEASURED: file summaries estimated 10,015 tokens, actually cost 11,546 --
# tiktoken undercounts by 15.3% on this codebase. Applied to the file summary
# stage, the only stage counted by tokenizing real text.
TOKENIZER_CORRECTION = 1.153

# How many files to actually tokenize when calibrating.
CALIBRATION_SAMPLE = 24

# MEASURED: 14 unit tests generated from 22 extracted rules.
UNIT_TEST_SURVIVAL = 0.64

# Fallback when a sample cannot be taken.
DEFAULT_CHARS_PER_TOKEN = 4.0


_ENCODER = None


def _encoder():
    """Load the tokenizer once and reuse it."""
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def count_tokens(text: str) -> int:
    """
    Token count for a piece of text.

    disallowed_special=() matters: without it tiktoken raises on any source
    file that happens to contain a literal like <|endoftext|>.
    """
    return len(_encoder().encode(text, disallowed_special=()))


# ---------------------------------------------------------
# Scanning
# ---------------------------------------------------------

def scan_files(codebase: str, apply_exclusions: bool):
    """
    Collect source files and their sizes without reading contents.

    apply_exclusions=False reproduces what file_summary_agent's crawler does
    today; True reproduces what it would do with directory_agent's skip list.

    Returns a list of (path, char_estimate) tuples.
    """

    found = []

    for root, dirs, filenames in os.walk(codebase):

        if apply_exclusions:
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for name in filenames:

            if Path(name).suffix.lower() not in ACCEPTABLE_EXTENSIONS:
                continue

            full = os.path.join(root, name)

            try:
                size = os.path.getsize(full)
            except OSError:
                continue

            found.append((full, size))

    return found


def count_directories(codebase: str) -> int:
    """
    Count directories the way directory_agent does, including the root.
    """

    total = 1

    for _, dirs, _files in os.walk(codebase):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        total += len(dirs)

    return total


# ---------------------------------------------------------
# Calibration
# ---------------------------------------------------------

def calibrate(files, sample_size: int = CALIBRATION_SAMPLE):
    """
    Work out a chars-per-token ratio per extension from a sample.

    Tokenizing every file is too slow to sit behind a button, and a flat
    chars/4 rule is wrong often enough to matter -- C# measured 5.17 on
    ConsoleTables, so chars/4 would have overshot by nearly 30%.

    Returns (ratios_by_extension, default_ratio, number_of_files_sampled).
    """

    by_ext = {}
    for path, size in files:
        by_ext.setdefault(Path(path).suffix.lower(), []).append((path, size))

    rng = random.Random(0)  # fixed seed: same codebase gives the same estimate

    ratios = {}
    sampled_total = 0

    # Spread the sample across extensions so one big language cannot skew it.
    per_ext = max(1, sample_size // max(len(by_ext), 1))

    total_chars = 0
    total_tokens = 0

    for ext, entries in by_ext.items():

        picks = rng.sample(entries, min(per_ext, len(entries)))

        ext_chars = 0
        ext_tokens = 0

        for path, _size in picks:
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            ext_chars += len(text)
            ext_tokens += count_tokens(text)
            sampled_total += 1

        if ext_tokens > 0:
            ratios[ext] = ext_chars / ext_tokens
            total_chars += ext_chars
            total_tokens += ext_tokens

    default_ratio = (
        total_chars / total_tokens
        if total_tokens > 0
        else DEFAULT_CHARS_PER_TOKEN
    )

    return ratios, default_ratio, sampled_total


def estimate_content_tokens(files, ratios, default_ratio) -> int:
    """
    Extrapolate total content tokens from file sizes and sampled ratios.
    """

    total = 0

    for path, size in files:
        ratio = ratios.get(Path(path).suffix.lower(), default_ratio)
        total += int(size / ratio) if ratio > 0 else 0

    return total


# ---------------------------------------------------------
# Artifact inspection
# ---------------------------------------------------------

def count_existing_rules(app_dir: Path, codebase_name: str):
    """
    Count business rules already extracted by a previous run.

    Returns (rule_count, source_file_count) or (None, None) when the pipeline
    has not produced them yet -- which is what makes the later stages
    unknowable rather than merely uncertain.
    """

    rules_path = (
        app_dir
        / "agent"
        / "file_summary_agent_output"
        / codebase_name
        / "business_rules"
        / "business_rules.json"
    )

    if not rules_path.exists():
        return None, None

    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None

    return sum(len(v) for v in data.values()), len(data)


# ---------------------------------------------------------
# Main entry point
# ---------------------------------------------------------

def estimate_pipeline(codebase: str, app_dir: Path = None):
    """
    Estimate token usage for a full pipeline run over `codebase`.
    """

    # resolve() so that a relative path like "." still yields a real name
    codebase_path = Path(codebase).resolve()

    if not codebase_path.exists():
        return {
            "success": False,
            "error": f"Codebase does not exist: {codebase}",
        }

    if app_dir is None:
        app_dir = Path(__file__).resolve().parent.parent

    codebase_name = codebase_path.name

    # --- scan both ways so the cost of unfiltered folders is visible -------

    files_raw = scan_files(codebase, apply_exclusions=False)
    files_clean = scan_files(codebase, apply_exclusions=True)

    ratios, default_ratio, sampled = calibrate(files_clean or files_raw)

    content_raw = estimate_content_tokens(files_raw, ratios, default_ratio)
    content_clean = estimate_content_tokens(files_clean, ratios, default_ratio)

    n_raw = len(files_raw)
    n_clean = len(files_clean)

    # --- stage 1: file summaries (exact) ----------------------------------

    stage_file_raw = int(
        (content_raw + FILE_SUMMARY_PROMPT_TOKENS * n_raw)
        * TOKENIZER_CORRECTION
    )
    stage_file_clean = int(
        (content_clean + FILE_SUMMARY_PROMPT_TOKENS * n_clean)
        * TOKENIZER_CORRECTION
    )

    stages = [
        {
            "stage": "build_database",
            "uses_ai": False,
            "confidence": "exact",
            "calls": 0,
            "input_tokens": 0,
            "note": "Embeddings run locally (all-MiniLM-L6-v2). No API cost.",
        },
        {
            "stage": "generate_file_summaries",
            "uses_ai": True,
            "confidence": "exact",
            "calls": n_clean,
            "input_tokens": stage_file_clean,
            "note": (
                f"One call per file. {FILE_SUMMARY_PROMPT_TOKENS} tokens of "
                f"fixed prompt x {n_clean} files = "
                f"{FILE_SUMMARY_PROMPT_TOKENS * n_clean:,} tokens before any "
                f"file content."
            ),
        },
        {
            "stage": "build_summary_database",
            "uses_ai": False,
            "confidence": "exact",
            "calls": 0,
            "input_tokens": 0,
            "note": "Local embeddings. No API cost.",
        },
    ]

    # --- stage 2: directory summaries (range) -----------------------------

    n_dirs = count_directories(codebase)

    dir_calls_min = n_dirs * DIRECTORY_CALLS_MIN
    dir_calls_max = n_dirs * DIRECTORY_CALLS_MAX

    stages.append({
        "stage": "generate_directory_summaries",
        "uses_ai": True,
        "confidence": "range",
        "calls": dir_calls_min,
        "calls_max": dir_calls_max,
        "input_tokens": dir_calls_min * DIRECTORY_TOKENS_PER_CALL,
        "input_tokens_max": dir_calls_max * DIRECTORY_TOKENS_PER_CALL,
        "note": (
            f"{n_dirs} directories x {DIRECTORY_CALLS_MIN}-"
            f"{DIRECTORY_CALLS_MAX} calls. The spread is the context "
            f"retrieval loop and up to 2 refinement rounds; the LLM decides "
            f"where in the range this lands."
        ),
    })

    # --- stages 3-5: depend on rules discovered earlier --------------------

    rule_count, rule_files = count_existing_rules(app_dir, codebase_name)

    if rule_count is None:
        for name in (
            "validate_business_rules",
            "generate_unit_tests",
            "generate_integration_tests",
        ):
            stages.append({
                "stage": name,
                "uses_ai": True,
                "confidence": "unknown",
                "calls": None,
                "input_tokens": None,
                "note": (
                    "Scales with business rules, which do not exist until "
                    "file summaries have run. Run this estimate again "
                    "afterwards for a real number."
                ),
            })
    else:
        br_calls = rule_count + rule_files
        stages.append({
            "stage": "validate_business_rules",
            "uses_ai": True,
            "confidence": "projected",
            "calls": br_calls,
            "input_tokens": br_calls * BR_TOKENS_PER_CALL,
            "note": (
                f"{rule_count} rules across {rule_files} files, from the "
                f"last run."
            ),
        })
        # MEASURED: 22 extracted rules produced only 14 unit test calls --
        # validation discards roughly a third. Reported as a range rather
        # than pretending the survival rate is known.
        ut_calls_low = max(1, int(rule_count * UNIT_TEST_SURVIVAL))
        stages.append({
            "stage": "generate_unit_tests",
            "uses_ai": True,
            "confidence": "projected",
            "calls": ut_calls_low,
            "calls_max": rule_count,
            "input_tokens": ut_calls_low * UNIT_TEST_TOKENS_PER_CALL,
            "input_tokens_max": rule_count * UNIT_TEST_TOKENS_PER_CALL,
            "note": (
                f"One call per rule that survives validation. Measured "
                f"survival was {int(UNIT_TEST_SURVIVAL * 100)}%; the upper "
                f"bound assumes all {rule_count} survive."
            ),
        })
        workflows = max(1, rule_files)
        stages.append({
            "stage": "generate_integration_tests",
            "uses_ai": True,
            "confidence": "projected",
            "calls": workflows + 1,
            "input_tokens": (workflows + 1) * INTEGRATION_TEST_TOKENS_PER_CALL,
            "note": (
                "One grouping call plus one per workflow. Workflow count is "
                "chosen by the LLM; approximated by source file count."
            ),
        })

    stages.append({
        "stage": "generate_all_uml",
        "uses_ai": False,
        "confidence": "exact",
        "calls": 0,
        "input_tokens": 0,
        "note": "Renders existing PlantUML via plantuml.jar. No API cost.",
    })

    # --- totals ------------------------------------------------------------

    known = [s for s in stages if s["input_tokens"] is not None]

    total_low = sum(s["input_tokens"] for s in known)
    total_high = sum(
        s.get("input_tokens_max", s["input_tokens"]) for s in known
    )

    has_unknown = any(s["confidence"] == "unknown" for s in stages)

    excluded_files = n_raw - n_clean
    excluded_tokens = stage_file_raw - stage_file_clean

    return {
        "success": True,
        "codebase": str(codebase_path),
        "codebase_name": codebase_name,

        "files_scanned": n_raw,
        "files_after_exclusions": n_clean,
        "directories": n_dirs,

        "excluded_files": excluded_files,
        "excluded_tokens": excluded_tokens,
        "excluded_percent": (
            round(100 * excluded_tokens / stage_file_raw, 1)
            if stage_file_raw else 0.0
        ),

        "calibration": {
            "files_sampled": sampled,
            "chars_per_token": round(default_ratio, 2),
            "by_extension": {k: round(v, 2) for k, v in sorted(ratios.items())},
        },

        "stages": stages,

        "total_input_low": total_low,
        "total_input_high": total_high,
        "total_output_low": int(total_low * OUTPUT_RATIO_LOW),
        "total_output_high": int(total_high * OUTPUT_RATIO_HIGH),
        "incomplete": has_unknown,

        "message": format_report(
            codebase_name, n_raw, n_clean, n_dirs,
            excluded_files, excluded_tokens,
            stages, total_low, total_high, has_unknown,
        ),
    }


def format_report(
    codebase_name, n_raw, n_clean, n_dirs,
    excluded_files, excluded_tokens,
    stages, total_low, total_high, has_unknown,
):
    """
    Render the estimate as plain text for the existing output box.
    """

    lines = []
    lines.append(f"Token estimate for: {codebase_name}")
    lines.append("")
    lines.append(f"  Source files : {n_clean}")
    lines.append(f"  Directories  : {n_dirs}")

    if excluded_files > 0:
        lines.append("")
        lines.append(
            f"  Skipping {excluded_files} file(s) in generated or vendored "
            f"folders"
        )
        lines.append(
            f"  (node_modules / .venv / bin / obj), saving "
            f"{excluded_tokens:,} tokens."
        )

    lines.append("")
    lines.append("  Per stage (input tokens):")

    for s in stages:

        if not s["uses_ai"]:
            lines.append(f"    {s['stage']:<32} free (no AI)")
            continue

        if s["input_tokens"] is None:
            lines.append(f"    {s['stage']:<32} needs a prior run")
            continue

        if "input_tokens_max" in s:
            lines.append(
                f"    {s['stage']:<32} "
                f"{s['input_tokens']:,} - {s['input_tokens_max']:,}"
            )
        else:
            lines.append(f"    {s['stage']:<32} {s['input_tokens']:,}")

    lines.append("")

    if total_low == total_high:
        lines.append(f"  Estimated input tokens : {total_low:,}")
    else:
        lines.append(
            f"  Estimated input tokens : {total_low:,} - {total_high:,}"
        )

    if has_unknown:
        lines.append(
            "  (excludes stages that need a prior run - real total is higher)"
        )

    return "\n".join(lines)
