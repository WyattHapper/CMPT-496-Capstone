"""
@file BR_input_loader.py
@brief Loads file-level (G1) and directory-level (G2) business rules into one common format.
@details Reads the business_rules.json files written by FileSummaryAgent and
DirectoryAgent, validates them against their existing output models, normalizes
paths against the codebase root, and returns a flat list of RuleCandidate objects.
Rules are not validated, condensed, or deduplicated here.
"""

import json
import logging
import os
import posixpath
import re
from pathlib import Path
from typing import NamedTuple

from pydantic import ValidationError

from agent.structured_output.BR_output import RuleCandidate
from agent.structured_output.directory_output import BusinessRulesOutput
from agent.structured_output.file_summary_output import BusinessRule

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent

_DRIVE_RE = re.compile(r"^[A-Za-z]:/")


class RuleInputError(ValueError):
    """
    @brief Raised when a business rule input file is malformed or does not match its schema.
    """


class RuleInputs(NamedTuple):
    """
    @brief Result of load_rule_candidates().
    @var candidates All loaded rule candidates, file-level first, in input order.
    @var missing_inputs Optional default inputs that were not found, keyed by "file" or "directory".
    """
    candidates: list[RuleCandidate]
    missing_inputs: dict[str, Path]


def default_rule_input_paths(codebase_name: str, app_dir: Path = APP_DIR) -> dict[str, Path]:
    """
    @brief Returns the default business_rules.json locations written by G1 and G2.
    @param codebase_name Name of the codebase (the root folder name).
    @param app_dir Application directory containing the agent output folders.
    @return Dict with "file" and "directory" input paths.
    """
    app_dir = Path(app_dir)
    return {
        "file": app_dir / "agent" / "file_summary_agent_output" / codebase_name / "business_rules" / "business_rules.json",
        "directory": app_dir / "agent" / "directory_agent_output" / codebase_name / "business_rules" / "business_rules.json",
    }


def load_rule_candidates(
    codebase_root,
    file_rules_path=None,
    directory_rules_path=None,
    app_dir: Path = APP_DIR,
) -> RuleInputs:
    """
    @brief Loads file-level and directory-level business rules as RuleCandidate objects.

    @details
    A path passed explicitly must exist. A path left as None falls back to the
    default output location and is optional: if only one default exists it is
    loaded and the other is reported in missing_inputs. If no input exists at
    all, FileNotFoundError is raised.

    @param codebase_root The selected codebase root directory.
    @param file_rules_path File-level rules JSON (path -> list of BusinessRule dicts).
    @param directory_rules_path Directory-level rules JSON (path -> BusinessRulesOutput dict).
    @param app_dir Application directory used to resolve default input paths.
    @return RuleInputs with the candidates and any missing optional inputs.
    @raises FileNotFoundError If an explicit input is missing, or no input exists.
    @raises RuleInputError If an input contains malformed JSON or invalid entries.
    """
    root = _normalize_root(codebase_root)
    defaults = default_rule_input_paths(Path(root["abs"]).name, app_dir)
    requested = {"file": file_rules_path, "directory": directory_rules_path}

    found: dict[str, Path] = {}
    missing: dict[str, Path] = {}
    for kind, explicit in requested.items():
        path = Path(explicit) if explicit is not None else defaults[kind]
        if path.is_file():
            found[kind] = path
        elif explicit is not None:
            raise FileNotFoundError(f"{kind.capitalize()}-level business rules not found: {path}")
        else:
            missing[kind] = path

    if not found:
        raise FileNotFoundError(
            "No business rule inputs found. Expected at least one of: "
            + ", ".join(f"{kind}-level rules at {path}" for kind, path in missing.items())
        )

    for kind, path in missing.items():
        logger.warning(f"{kind.capitalize()}-level business rules not found, continuing without them: {path}")

    candidates: list[RuleCandidate] = []
    if "file" in found:
        candidates.extend(_load_file_rules(found["file"], root))
    if "directory" in found:
        candidates.extend(_load_directory_rules(found["directory"], root))

    return RuleInputs(candidates=candidates, missing_inputs=missing)


def _load_file_rules(path: Path, root: dict) -> list[RuleCandidate]:
    """
    @brief Converts file-level output ({file_path: [BusinessRule, ...]}) into candidates.
    """
    raw = _read_json_object(path)
    candidates = []
    for file_key, rules in raw.items():
        if not isinstance(rules, list):
            raise RuleInputError(f"{path}: entry {file_key!r} must be a list of rules, got {type(rules).__name__}.")

        rel_file = normalize_rule_path(file_key, root)
        source_dir = posixpath.dirname(rel_file) or "."

        for index, item in enumerate(rules):
            location = f"{path}: entry {file_key!r}, rule #{index}"
            if not isinstance(item, dict):
                raise RuleInputError(f"{location}: expected an object with a 'rule' field, got {type(item).__name__}.")
            try:
                rule = BusinessRule.model_validate(item)
            except ValidationError as e:
                raise RuleInputError(f"{location}: {_describe(e)}") from e
            _require_text(rule.rule, location)

            source_files = [rel_file]
            if rule.source_file:
                rel_source = normalize_rule_path(rule.source_file, root)
                if rel_source not in source_files:
                    source_files.append(rel_source)

            candidates.append(RuleCandidate(
                rule=rule.rule,
                source_directory=source_dir,
                source_file_paths=source_files,
                origin="file",
            ))
    return candidates


def _load_directory_rules(path: Path, root: dict) -> list[RuleCandidate]:
    """
    @brief Converts directory-level output ({dir_path: BusinessRulesOutput}) into candidates.
    @details Source files are unknown for directory rules, so source_file_paths stays empty.
    """
    raw = _read_json_object(path)
    candidates = []
    for dir_key, entry in raw.items():
        location = f"{path}: entry {dir_key!r}"
        if not isinstance(entry, dict):
            raise RuleInputError(f"{location}: expected an object with observed_rules/inferred_rules, got {type(entry).__name__}.")
        try:
            output = BusinessRulesOutput.model_validate(entry)
        except ValidationError as e:
            raise RuleInputError(f"{location}: {_describe(e)}") from e

        # directory_path is written root-relative by DirectoryAgent; the key is
        # the absolute path on the machine that generated the output.
        source_dir = normalize_rule_path(output.directory_path or dir_key, root)

        for field, origin in (("observed_rules", "directory_observed"), ("inferred_rules", "directory_inferred")):
            for index, text in enumerate(getattr(output, field)):
                _require_text(text, f"{location}, {field}[{index}]")
                candidates.append(RuleCandidate(
                    rule=text,
                    source_directory=source_dir,
                    source_file_paths=[],
                    origin=origin,
                ))
    return candidates


def normalize_rule_path(path_value: str, root: dict) -> str:
    """
    @brief Normalizes a rule path to a POSIX path relative to the codebase root.

    @details
    Handles Windows separators, absolute paths under the root, absolute paths
    from another machine that contain the codebase folder name, paths relative
    to the working directory that include the root, and paths prefixed with the
    codebase name. Returns "." for the root itself. An absolute path that cannot
    be related to the root is returned unchanged (normalized to POSIX).

    @param path_value The raw path from the input JSON.
    @param root Normalized root info from _normalize_root().
    @return The normalized path.
    """
    path = posixpath.normpath(str(path_value).strip().replace("\\", "/"))
    name = root["name"]

    if _is_abs(path):
        rel = _strip_prefix(path, root["abs"])
        if rel is None:
            # Generated on another machine/location: cut after the codebase folder.
            parts = path.split("/")
            ignore_case = bool(_DRIVE_RE.match(path))
            for i, part in enumerate(parts[1:], start=1):
                if _same(part, name, ignore_case):
                    rel = "/".join(parts[i + 1:])
                    break
        return (rel or ".") if rel is not None else path

    if path == ".":
        return "."
    if root["rel"]:
        rel = _strip_prefix(path, root["rel"])
        if rel is not None:
            return rel or "."
    head, _, rest = path.partition("/")
    if head == name and not (Path(root["abs"]) / path).exists():
        return rest or "."
    return path


def _normalize_root(codebase_root) -> dict:
    """
    @brief Precomputes the root forms used by normalize_rule_path().
    @return Dict with "abs" (absolute POSIX root), "rel" (the root as given, if relative), and "name".
    """
    given = posixpath.normpath(str(codebase_root).strip().replace("\\", "/"))
    abs_root = posixpath.normpath(os.path.abspath(str(codebase_root)).replace("\\", "/"))
    return {
        "abs": abs_root,
        "rel": None if _is_abs(given) or given == "." else given,
        "name": posixpath.basename(abs_root),
    }


def _is_abs(path: str) -> bool:
    return path.startswith("/") or bool(_DRIVE_RE.match(path))


def _same(a: str, b: str, ignore_case: bool) -> bool:
    return a.casefold() == b.casefold() if ignore_case else a == b


def _strip_prefix(path: str, prefix: str) -> str | None:
    """
    @brief Returns path relative to prefix ("" if equal), or None if path is not under prefix.
    @details Comparison ignores case for Windows drive paths.
    """
    ignore_case = bool(_DRIVE_RE.match(path) or _DRIVE_RE.match(prefix))
    if _same(path, prefix, ignore_case):
        return ""
    head = prefix.rstrip("/") + "/"
    if _same(path[:len(head)], head, ignore_case):
        return path[len(head):]
    return None


def _read_json_object(path: Path) -> dict:
    """
    @brief Reads a JSON file whose top level must be an object.
    @raises RuleInputError On malformed JSON or a non-object top level.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise RuleInputError(f"{path}: malformed JSON at line {e.lineno}, column {e.colno}: {e.msg}.") from e
    if not isinstance(data, dict):
        raise RuleInputError(f"{path}: expected a JSON object at the top level, got {type(data).__name__}.")
    return data


def _require_text(text: str, location: str) -> None:
    if not text.strip():
        raise RuleInputError(f"{location}: rule text is empty.")


def _describe(error: ValidationError) -> str:
    """
    @brief Summarizes a pydantic ValidationError as 'field: message; ...'.
    """
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or 'value'}: {err['msg']}"
        for err in error.errors()
    )
