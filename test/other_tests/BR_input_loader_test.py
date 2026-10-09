"""
@file BR_input_loader_test.py
@brief Tests for agent/BR_input_loader.py using temporary JSON fixtures.
@details No AI calls or vector stores are used.
"""

import sys
import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
import pytest
from agent.BR_input_loader import (
    load_rule_candidates,
    default_rule_input_paths,
    RuleInputError,
)

CODEBASE = "MyCodebase"


@pytest.fixture
def root(tmp_path):
    path = tmp_path / CODEBASE
    (path / "src").mkdir(parents=True)
    return path


@pytest.fixture
def app_dir(tmp_path):
    # Empty app dir so default inputs are missing unless a test creates them.
    path = tmp_path / "app"
    path.mkdir()
    return path


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def win(path):
    """Absolute path in Windows separator form."""
    return str(path).replace("/", "\\")


def file_rule(text, source_file=None):
    return {"rule": text, "source_file": source_file}


def dir_entry(directory_path, observed=(), inferred=()):
    return {
        "directory_name": Path(directory_path).name or "root",
        "directory_path": directory_path,
        "observed_rules": list(observed),
        "inferred_rules": list(inferred),
    }


def load(root, app_dir, file_data=None, dir_data=None):
    tmp = app_dir.parent / "inputs"
    file_path = write_json(tmp / "file.json", file_data) if file_data is not None else None
    dir_path = write_json(tmp / "dir.json", dir_data) if dir_data is not None else None
    return load_rule_candidates(root, file_path, dir_path, app_dir=app_dir)


# ---------------------------------------------------------
# Input combinations and provenance
# ---------------------------------------------------------

def test_file_only(root, app_dir):
    key = win(root / "src" / "Order.cs")
    result = load(root, app_dir, file_data={key: [file_rule("Orders need a customer.", key)]})

    assert len(result.candidates) == 1
    c = result.candidates[0]
    assert c.rule == "Orders need a customer."
    assert c.origin == "file"
    assert c.source_directory == "src"
    assert c.source_file_paths == ["src/Order.cs"]
    assert set(result.missing_inputs) == {"directory"}


def test_directory_only(root, app_dir):
    result = load(root, app_dir, dir_data={
        win(root / "src"): dir_entry("src", observed=["Obs rule."], inferred=["Inference: Inf rule."]),
    })

    assert [(c.rule, c.origin) for c in result.candidates] == [
        ("Obs rule.", "directory_observed"),
        ("Inference: Inf rule.", "directory_inferred"),
    ]
    for c in result.candidates:
        assert c.source_directory == "src"
        assert c.source_file_paths == []
    assert set(result.missing_inputs) == {"file"}


def test_combined_inputs_keep_origins_and_order(root, app_dir):
    result = load(
        root, app_dir,
        file_data={win(root / "src" / "A.cs"): [file_rule("File rule.")]},
        dir_data={win(root / "src"): dir_entry("src", observed=["Obs."], inferred=["Inference: Inf."])},
    )

    assert [c.origin for c in result.candidates] == ["file", "directory_observed", "directory_inferred"]
    assert result.missing_inputs == {}


def test_root_folder_rules(root, app_dir):
    result = load(
        root, app_dir,
        file_data={win(root / "Program.cs"): [file_rule("Root file rule.")]},
        dir_data={win(root): dir_entry(".", observed=["Root dir rule."])},
    )

    file_c, dir_c = result.candidates
    assert file_c.source_directory == "."
    assert file_c.source_file_paths == ["Program.cs"]
    assert dir_c.source_directory == "."
    assert dir_c.source_file_paths == []


def test_nested_directory_and_key_fallback(root, app_dir):
    # directory_path missing: fall back to the (foreign-machine) key.
    entry = dir_entry("unused", observed=["Nested rule."])
    del entry["directory_path"]
    result = load(root, app_dir, dir_data={
        f"E:\\Elsewhere\\{CODEBASE}\\src\\Models": entry,
    })

    assert result.candidates[0].source_directory == "src/Models"


def test_differing_source_file_is_kept(root, app_dir):
    key = win(root / "src" / "A.cs")
    result = load(root, app_dir, file_data={
        key: [file_rule("Rule.", win(root / "src" / "B.cs"))],
    })

    assert result.candidates[0].source_file_paths == ["src/A.cs", "src/B.cs"]


def test_duplicates_remain_separate(root, app_dir):
    result = load(
        root, app_dir,
        file_data={
            win(root / "src" / "A.cs"): [file_rule("Same rule."), file_rule("Same rule.")],
            win(root / "src" / "B.cs"): [file_rule("Same rule.")],
        },
        dir_data={win(root / "src"): dir_entry("src", observed=["Same rule.", "Same rule."], inferred=["Same rule."])},
    )

    assert len(result.candidates) == 6
    assert all(c.rule == "Same rule." for c in result.candidates)
    assert [c.source_file_paths for c in result.candidates[:3]] == [["src/A.cs"], ["src/A.cs"], ["src/B.cs"]]


# ---------------------------------------------------------
# Path normalization
# ---------------------------------------------------------

@pytest.mark.parametrize("key_factory", [
    lambda root: win(root / "src" / "Order.cs"),                  # Windows absolute under root
    lambda root: str(root / "src" / "Order.cs"),                  # native absolute under root
    lambda root: (root / "src" / "Order.cs").as_posix(),          # forward-slash absolute
    lambda root: f"C:\\Other\\Machine\\{CODEBASE}\\src\\Order.cs",  # generated elsewhere
    lambda root: "src\\Order.cs",                                 # root-relative, Windows
    lambda root: "./src/Order.cs",                                # root-relative, dotted
    lambda root: f"{CODEBASE}/src/Order.cs",                      # codebase-prefixed
    lambda root: f"{CODEBASE}\\src\\Order.cs",                    # codebase-prefixed, Windows
])
def test_supported_path_formats(root, app_dir, key_factory):
    result = load(root, app_dir, file_data={key_factory(root): [file_rule("Rule.")]})

    c = result.candidates[0]
    assert c.source_directory == "src"
    assert c.source_file_paths == ["src/Order.cs"]


def test_relative_root_and_cwd_relative_keys(tmp_path, app_dir, monkeypatch):
    nested = tmp_path / "targetCodebases" / CODEBASE
    nested.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    result = load(f"./targetCodebases/{CODEBASE}", app_dir, file_data={
        f"targetCodebases\\{CODEBASE}\\src\\Order.cs": [file_rule("Rule.")],
    })

    assert result.candidates[0].source_file_paths == ["src/Order.cs"]


def test_subfolder_named_like_codebase_is_not_stripped(root, app_dir):
    (root / CODEBASE).mkdir()
    result = load(root, app_dir, dir_data={
        win(root / CODEBASE): dir_entry(CODEBASE, observed=["Rule."]),
    })

    assert result.candidates[0].source_directory == CODEBASE


# ---------------------------------------------------------
# Missing and empty inputs
# ---------------------------------------------------------

def test_default_inputs_one_present(root, app_dir):
    defaults = default_rule_input_paths(CODEBASE, app_dir)
    write_json(defaults["directory"], {win(root): dir_entry(".", observed=["Rule."])})

    result = load_rule_candidates(root, app_dir=app_dir)

    assert len(result.candidates) == 1
    assert result.missing_inputs == {"file": defaults["file"]}


def test_default_inputs_both_present(root, app_dir):
    defaults = default_rule_input_paths(CODEBASE, app_dir)
    write_json(defaults["file"], {win(root / "A.cs"): [file_rule("F.")]})
    write_json(defaults["directory"], {win(root): dir_entry(".", observed=["D."])})

    result = load_rule_candidates(root, app_dir=app_dir)

    assert [c.origin for c in result.candidates] == ["file", "directory_observed"]
    assert result.missing_inputs == {}


def test_both_inputs_missing_raises(root, app_dir):
    with pytest.raises(FileNotFoundError, match="No business rule inputs found"):
        load_rule_candidates(root, app_dir=app_dir)


def test_explicit_missing_input_raises(root, app_dir):
    with pytest.raises(FileNotFoundError, match="File-level business rules not found"):
        load_rule_candidates(root, file_rules_path=app_dir / "nope.json", app_dir=app_dir)


@pytest.mark.parametrize("file_data, dir_data", [
    ({}, {}),
    ({"src/A.cs": []}, {"src": dir_entry("src")}),
])
def test_valid_empty_outputs(root, app_dir, file_data, dir_data):
    result = load(root, app_dir, file_data=file_data, dir_data=dir_data)

    assert result.candidates == []
    assert result.missing_inputs == {}


# ---------------------------------------------------------
# Malformed JSON and invalid schemas
# ---------------------------------------------------------

def test_malformed_json(root, app_dir):
    bad = app_dir / "bad.json"
    bad.write_text('{"src/A.cs": [', encoding="utf-8")

    with pytest.raises(RuleInputError, match=r"bad\.json: malformed JSON at line 1"):
        load_rule_candidates(root, file_rules_path=bad, app_dir=app_dir)


@pytest.mark.parametrize("file_data, expected", [
    ([], "expected a JSON object at the top level"),
    ({"src/A.cs": "not a list"}, r"entry 'src/A.cs' must be a list"),
    ({"src/A.cs": ["plain string"]}, r"entry 'src/A.cs', rule #0: expected an object"),
    ({"src/A.cs": [{"source_file": None}]}, r"entry 'src/A.cs', rule #0: rule: Field required"),
    ({"src/A.cs": [file_rule("ok"), {"rule": "x", "extra": 1}]}, r"rule #1: extra: Extra inputs"),
    ({"src/A.cs": [file_rule("   ")]}, r"rule #0: rule text is empty"),
])
def test_invalid_file_schema(root, app_dir, file_data, expected):
    with pytest.raises(RuleInputError, match=r"file\.json: .*" + expected):
        load(root, app_dir, file_data=file_data)


@pytest.mark.parametrize("dir_data, expected", [
    ({"src": ["not", "an", "object"]}, r"entry 'src': expected an object"),
    ({"src": {**dir_entry("src"), "observed_rules": "oops"}}, r"entry 'src': observed_rules: Input should be a valid list"),
    ({"src": {**dir_entry("src"), "inferred_rules": [3]}}, r"entry 'src': inferred_rules\.0: Input should be a valid string"),
    ({"src": dir_entry("src", observed=[""])}, r"entry 'src', observed_rules\[0\]: rule text is empty"),
])
def test_invalid_directory_schema(root, app_dir, dir_data, expected):
    with pytest.raises(RuleInputError, match=r"dir\.json: .*" + expected):
        load(root, app_dir, dir_data=dir_data)
