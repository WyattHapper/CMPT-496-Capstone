"""
agent/test_harness.py

Writes, builds, repairs and runs the C# tests the test agents generate.

Every generated test used to be pasted into one UnitTest1.cs (or
IntegrationTest1.cs). A single broken test -- one cut off at Gemini's output
limit, one with a bare `Xunit` import -- stopped the whole file compiling, so


Now each test gets its own file and class (UT_12.cs / class UT_12), so a
compiler error names the test that caused it:

    clean_test()       no AI: fix imports, drop runaway or mangled answers
    write_tests()      one file per test
    check_tests()      build; send each broken test only its own errors to
                       the AI; drop what still fails after MAX_REPAIR_ROUNDS;
                       then run the rest and count passes and failures

Tests that compile but fail an assertion are kept and reported, not "fixed":
the failure may be a real bug in the codebase, and rewriting a test until it
passes would hide it.

Unit and integration tests share one test project ({codebase}.Tests), told
apart by file prefix (UT_ / IT_).
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.crawl_config import mark_generated
from agent.llm import DailyLimitError, RateLimitTimeoutError
from agent.structured_output.UTV_output import TestRepair
from backend.progress_logging import progress


# A healthy generated test is 300-4,000 characters (Stateless: median 1,143,
# largest 9,175). Longer answers are the AI not stopping: two Stateless tests
# ran to 173,208 and 281,814 characters and were cut off mid-line, and a
# CliWrap answer held 127 [Fact] methods in 40,270 characters.
MAX_TEST_CHARS = 20_000

# Gemini's own cap is ~65.5k output tokens. A single test never needs a
# fraction of that, so a runaway answer is stopped at half the cost. Leaves
# room for the model's thinking, which counts toward the limit.
MAX_TEST_OUTPUT_TOKENS = 32_768

# How many times one broken test is sent back to the AI with its errors.
MAX_REPAIR_ROUNDS = 2

MAX_CONCURRENCY = 10

# A chunk of text repeated this many times in a row is the AI stuck in a loop
# ("CompleteDefinitiveResolvedCompleteDefinitiveResolved...").
MAX_REPEATS = 20

# Files the old one-file writers produced (and `dotnet new xunit`'s template
# test). Left in place they would still be compiled.
LEGACY_TEST_FILES = ("UnitTest1.cs", "IntegrationTest1.cs")

BUILD_TIMEOUT_SECONDS = 600
TEST_TIMEOUT_SECONDS = 900

GENERATED_FILE = re.compile(r"^(UT|IT)_\w+$")

USING_LINE = re.compile(
    r"^(global\s+)?using\s+(static\s+)?[A-Za-z_][\w.]*(\s*=\s*[A-Za-z_][\w.<>, ]*)?$"
)

# dotnet build: path(line,col): error CS1002: ; expected [project.csproj]
BUILD_ERROR = re.compile(
    r"^\s*(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>\w+): "
    r"(?P<msg>.*?)(?:\s+\[[^\]]*\])?\s*$"
)

# dotnet test, minimal verbosity:
#   Failed!  - Failed:     5, Passed:    52, Skipped:     0, Total:    57
TEST_SUMMARY = re.compile(
    r"Failed:\s*(?P<failed>\d+),\s*Passed:\s*(?P<passed>\d+),\s*"
    r"Skipped:\s*(?P<skipped>\d+),\s*Total:\s*(?P<total>\d+)"
)

# dotnet test, normal verbosity (what run_tests asks for):
#   Total tests: 62
#        Passed: 57
#        Failed: 5
TEST_TOTALS = re.compile(r"^\s*(?P<label>Passed|Failed|Skipped):\s*(?P<count>\d+)\s*$", re.MULTILINE)

# dotnet test (normal verbosity):   Failed stateless.Tests.UT_12.SomeName [3 ms]
FAILED_TEST = re.compile(r"^\s*Failed\s+(?P<name>[\w.]+)(?:\([^)]*\))?\s+\[")


@dataclass
class TestCase:
    """One generated test on its way through check_tests()."""

    __test__ = False  # not a pytest test class

    name: str                 # file stem and class name, e.g. "UT_12"
    imports: list[str]
    body: str                 # the [Fact] method(s), without imports
    source: Any = None        # the agent's own object, to map results back
    errors: list[str] = field(default_factory=list)
    repairs: int = 0
    reason: str = ""          # why it was dropped


@dataclass
class TestRun:
    """What check_tests() found."""

    __test__ = False  # not a pytest test class

    kind: str                 # "Unit" or "Integration"
    generated: int = 0
    kept: list[TestCase] = field(default_factory=list)
    dropped: list[TestCase] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failed_tests: list[str] = field(default_factory=list)
    removed_stale: list[str] = field(default_factory=list)
    project_error: str = ""
    report_path: str = ""

    @property
    def repaired(self):
        return [case for case in self.kept if case.repairs]

    def summary(self):
        return {
            "generated": self.generated,
            "kept": len(self.kept),
            "repaired": [case.name for case in self.repaired],
            "dropped": [
                {"name": case.name, "reason": case.reason}
                for case in self.dropped
            ],
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "failed_tests": self.failed_tests,
            "removed_stale_files": self.removed_stale,
            "project_error": self.project_error,
            "html_report": self.report_path,
        }

    def message(self):
        """One or two sentences for the Complete screen."""
        kind = self.kind

        if self.project_error:
            return (
                f"{kind} tests were written but the test project itself did "
                f"not build, so none ran: {self.project_error}"
            )

        if not self.generated:
            return f"No {kind.lower()} tests were generated."

        kept = len(self.kept)
        parts = [f"{kind} tests: {kept} of {self.generated} kept"]

        details = []
        if self.repaired:
            details.append(f"{len(self.repaired)} repaired by the AI")
        if self.dropped:
            details.append(f"{len(self.dropped)} dropped because they did not compile")
        if details:
            parts[0] += f" ({', '.join(details)})"

        if kept:
            parts.append(f"{self.passed} passed, {self.failed} failed")

        return ". ".join(parts) + "."

    def needs_attention(self):
        return bool(
            self.project_error or self.dropped or self.failed or not self.kept
        )


# ---------------------------------------------------------------------------
# Cleaning (no AI)
# ---------------------------------------------------------------------------

def normalize_imports(imports):
    """
    Turn whatever the AI returned into `using X;` lines, deduplicated.

    Seen in real runs: "Xunit" (no using, no semicolon), "using Xunit" (no
    semicolon), and the integration agent's schema strips both on purpose.
    Paths, comments and markdown are dropped.
    """
    cleaned = set()

    for raw in imports or []:
        line = str(raw).strip().rstrip(";").strip()

        if not line:
            continue

        if not re.match(r"^(global\s+)?using\s", line):
            line = f"using {line}"

        if USING_LINE.match(line):
            cleaned.add(line + ";")

    return sorted(cleaned)


def _extract_leaked_json(body):
    """
    The AI sometimes writes its whole JSON answer inside the test field:
    ... "imports": [...], "unit_test": "[Fact]\\npublic void ..." }
    Pull the real test back out of it. Returns None if that fails.
    """
    for key in ('"unit_test"', '"integration_test"', '"test_method"'):
        start = body.rfind(key)
        if start == -1:
            continue

        quote = body.find('"', body.find(":", start + len(key)))
        if quote == -1:
            continue

        try:
            value, _ = json.JSONDecoder().raw_decode(body[quote:])
        except ValueError:
            continue

        if isinstance(value, str) and value.strip():
            return value

    return None


def _unescape_newlines(body):
    """
    Some answers arrive as one line with the line breaks written out as the
    two characters backslash-n. Only undone when the body has almost no real
    line breaks, so a "\\n" inside a genuine C# string is left alone.
    """
    if body.count("\n") >= 3 or body.count("\\n") < 3:
        return body

    try:
        return json.loads(f'"{body}"')
    except ValueError:
        return (
            body.replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
        )


def _strip_fences(body):
    body = body.strip()
    body = re.sub(r"^```[\w#+-]*\s*\n", "", body)
    body = re.sub(r"\n?```\s*$", "", body)
    return body


def _split_usings(body):
    """Move `using X;` lines the AI put at the top of the method into imports."""
    usings = []
    lines = body.split("\n")

    while lines and (
        not lines[0].strip() or re.match(r"^\s*using\s+[\w.=\s<>,]+;\s*$", lines[0])
    ):
        line = lines.pop(0).strip()
        if line:
            usings.append(line)

    return "\n".join(lines), usings


def clean_test(body, imports):
    """
    Tidy one generated test before it is written.

    Returns (body, imports, reason): reason is empty when the test is usable,
    otherwise it says why the test was rejected and body is None.
    """
    body = (body or "").strip()

    if not body:
        return None, imports, "the AI returned an empty test"

    if len(body) > MAX_TEST_CHARS:
        return None, imports, (
            f"the AI's answer was {len(body):,} characters long (a normal "
            "test is under 5,000); it kept writing instead of stopping at one test"
        )

    if re.search(r'"(unit_test|integration_test|imports)"\s*:', body):
        extracted = _extract_leaked_json(body)
        if extracted is None:
            return None, imports, "the AI mixed its JSON answer into the test code"
        body = extracted.strip()

    body = _strip_fences(_unescape_newlines(body))

    if re.search(r"(.{8,80}?)\1{%d,}" % (MAX_REPEATS - 1), body, re.DOTALL):
        return None, imports, "the AI got stuck repeating the same text"

    body, inline_usings = _split_usings(body)

    # Also matches xUnit extensions such as [SkippableFact] (used by CliWrap).
    if not re.search(r"\[\s*\w*(Fact|Theory)\b", body):
        return None, imports, "no [Fact] or [Theory] test method in the answer"

    return body, normalize_imports(list(imports or []) + inline_usings), ""


def make_cases(prefix, items, body_of, imports_of):
    """
    Clean each generated test and split them into usable and rejected.

    @param items (id, agent object) pairs; the id names the file (UT_12.cs).
    @return (cases, rejected) lists of TestCase. A rejected case keeps the
            original text, so discarded_tests.json shows what the AI wrote.
    """
    cases, rejected, used = [], [], set()

    for item_id, item in items:
        name = f"{prefix}_{item_id}"
        while name in used:
            name += "_b"
        used.add(name)

        original = body_of(item) or ""
        body, imports, reason = clean_test(original, imports_of(item))

        if reason:
            rejected.append(TestCase(
                name=name,
                imports=normalize_imports(imports_of(item)),
                body=original,
                source=item,
                reason=reason,
            ))
        else:
            cases.append(TestCase(name=name, imports=imports, body=body, source=item))

    return cases, rejected


# ---------------------------------------------------------------------------
# Test project and files
# ---------------------------------------------------------------------------

def project_dir_for(codebase_path, codebase_name):
    return os.path.join(codebase_path, f"{codebase_name}.Tests")


def namespace_for(codebase_name):
    parts = [re.sub(r"\W", "_", part) or "_" for part in codebase_name.split(".")]
    parts = [f"_{part}" if part[0].isdigit() else part for part in parts]
    return ".".join(parts) + ".Tests"


# MSBuild and NuGet read Directory.Build.props / .targets and
# Directory.Packages.props from every folder above a project, so the test
# project inherited the codebase's own build rules. CliWrap's central package
# management (NU1008) and TreatWarningsAsErrors stopped every generated test
# from building. Copies in the test folder stop that search there.
_NO_CENTRAL_PACKAGES = (
    "<Project>\n"
    "  <PropertyGroup>\n"
    "    <ManagePackageVersionsCentrally>false</ManagePackageVersionsCentrally>\n"
    "  </PropertyGroup>\n"
    "</Project>\n"
)

ISOLATION_FILES = {
    "Directory.Build.props": _NO_CENTRAL_PACKAGES,
    "Directory.Packages.props": _NO_CENTRAL_PACKAGES,
    "Directory.Build.targets": "<Project />\n",
}


def ensure_test_project(test_dir, codebase_name):
    """
    Create the xUnit project that references every project in the codebase,
    and keep it isolated from the codebase's own build settings.
    """
    if not Path(test_dir).is_dir():
        progress("Creating test project...")

        try:
            subprocess.run(
                ["dotnet", "new", "xunit", "-o", test_dir],
                capture_output=True,
                text=True,
            )

            with open(f"{test_dir}/{codebase_name}.Tests.csproj", "r+", encoding="utf-8") as file:
                lines = file.readlines()
                lines.insert(-1, '<ItemGroup>\n<ProjectReference Include="..\\**\\*.csproj" Exclude="..\\**\\*.Tests.csproj" />\n</ItemGroup>\n\n')
                file.seek(0)
                file.writelines(lines)

        except Exception as e:
            progress(f"Error creating test project: {e}")

    # Written every time, so test projects made before this existed are
    # isolated too.
    if Path(test_dir).is_dir():
        for name, content in ISOLATION_FILES.items():
            with open(os.path.join(test_dir, name), "w", encoding="utf-8") as file:
                file.write(content)

    mark_generated(test_dir)  # keep the crawlers out of our own tests


def render_test(case, namespace):
    usings = "\n".join(case.imports)
    return (
        f"{usings}\n\nnamespace {namespace};\n\n"
        f"public class {case.name}\n{{\n{case.body}\n}}\n"
    )


def write_tests(test_dir, namespace, prefix, cases):
    """
    Replace this kind's test files with one file per case.

    Only files with this prefix are removed, so writing unit tests leaves the
    integration tests alone and vice versa.
    """
    folder = Path(test_dir)

    for old in list(folder.glob(f"{prefix}_*.cs")) + [folder / name for name in LEGACY_TEST_FILES]:
        if old.exists():
            old.unlink()

    for case in cases:
        _write_case(test_dir, namespace, case)


def _write_case(test_dir, namespace, case):
    with open(os.path.join(test_dir, f"{case.name}.cs"), "w", encoding="utf-8") as file:
        file.write(render_test(case, namespace))


def _remove_case(test_dir, case):
    path = Path(test_dir) / f"{case.name}.cs"
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Build and run
# ---------------------------------------------------------------------------

def parse_build_output(output):
    """
    Split dotnet build output into errors per generated test file and errors
    that belong to nothing we wrote (the project itself, a package, the
    codebase under test).

    Returns (errors_by_file, other_errors). MSBuild prints each error twice,
    so both are deduplicated.
    """
    errors_by_file = {}
    other_errors = []

    for line in output.splitlines():
        if ": error " not in line:
            continue

        match = BUILD_ERROR.match(line)

        if match and GENERATED_FILE.match(Path(match["file"]).stem):
            stem = Path(match["file"]).stem
            text = f"line {match['line']}: {match['code']}: {match['msg']}"
            if text not in errors_by_file.setdefault(stem, []):
                errors_by_file[stem].append(text)
            continue

        text = re.sub(r"\s+\[[^\]]*\]\s*$", "", line.strip())
        if text not in other_errors:
            other_errors.append(text)

    return errors_by_file, other_errors


def build(test_dir):
    """Returns (errors_by_file, other_errors)."""
    try:
        result = subprocess.run(
            ["dotnet", "build", test_dir, "-nologo"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=BUILD_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return {}, ["dotnet was not found. Install the .NET SDK to build the tests."]
    except subprocess.TimeoutExpired:
        return {}, [f"dotnet build took longer than {BUILD_TIMEOUT_SECONDS} s."]

    errors_by_file, other_errors = parse_build_output(result.stdout + "\n" + result.stderr)

    if result.returncode != 0 and not errors_by_file and not other_errors:
        tail = (result.stdout or result.stderr).strip().splitlines()[-3:]
        other_errors = [" ".join(tail) or "dotnet build failed without an error message."]

    return errors_by_file, other_errors


def parse_test_output(output):
    """Returns (passed, failed, skipped, failed_test_names)."""
    passed = failed = skipped = 0

    for match in TEST_SUMMARY.finditer(output):
        passed += int(match["passed"])
        failed += int(match["failed"])
        skipped += int(match["skipped"])

    if not (passed or failed or skipped) and "Total tests:" in output:
        totals = {"Passed": 0, "Failed": 0, "Skipped": 0}
        for match in TEST_TOTALS.finditer(output.split("Total tests:", 1)[1]):
            totals[match["label"]] += int(match["count"])
        passed, failed, skipped = totals["Passed"], totals["Failed"], totals["Skipped"]

    failed_tests = []
    for line in output.splitlines():
        match = FAILED_TEST.match(line)
        if match and match["name"] not in failed_tests:
            failed_tests.append(match["name"])

    return passed, failed, skipped, failed_tests


def run_tests(test_dir, namespace, prefix, results_dir, report_name):
    """
    Run this kind's tests only (the project also holds the other kind) and
    write an HTML report. Returns (passed, failed, skipped, failed_names,
    report_path).
    """
    os.makedirs(results_dir, exist_ok=True)

    report_path = os.path.join(results_dir, report_name)
    if os.path.exists(report_path):
        os.remove(report_path)

    # dotnet test also leaves GUID-named attachment folders wherever its
    # results go; run it in a scratch folder and keep only the report, so the
    # "View unit tests" list stays readable.
    scratch = tempfile.mkdtemp(prefix="checkpoint_tests_")

    try:
        result = subprocess.run(
            [
                "dotnet", "test", test_dir,
                "--no-build",
                "--filter", f"FullyQualifiedName~{namespace}.{prefix}_",
                "--logger", f"html;LogFileName={report_name}",
                "--logger", "console;verbosity=normal",
                "--results-directory", scratch,
                # A test that never finishes is killed instead of hanging the run.
                "--blame-hang-timeout", "60s",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT_SECONDS,
        )
        output = result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired as e:
        output = str(e.stdout or "")
        progress(f"Tests were still running after {TEST_TIMEOUT_SECONDS} s and were stopped.")
    except FileNotFoundError:
        output = ""
        progress("dotnet was not found, so the tests could not be run.")

    scratch_report = os.path.join(scratch, report_name)
    if os.path.exists(scratch_report):
        shutil.move(scratch_report, report_path)
    shutil.rmtree(scratch, ignore_errors=True)

    passed, failed, skipped, failed_tests = parse_test_output(output)

    return (
        passed,
        failed,
        skipped,
        failed_tests,
        report_path if os.path.exists(report_path) else "",
    )


# ---------------------------------------------------------------------------
# Repair (AI)
# ---------------------------------------------------------------------------

def make_fixer(llm, context_for=None):
    """
    Build the async function that asks the AI to fix one broken test.

    The AI gets that test's file and only that test's compiler errors, plus
    code from the codebase when context_for(case) supplies it -- most broken
    tests call a constructor or member that does not exist or is not public,
    and the AI cannot fix that without seeing the real API.

    Returns None when the AI gives up or the call fails, so the test is
    dropped. Running out of daily quota stops the step instead.
    """
    structured_llm = llm.with_structured_output(TestRepair)

    async def fix(case, namespace):
        context = context_for(case) if context_for else ""
        numbered = "\n".join(
            f"{number:4d}  {line}"
            for number, line in enumerate(render_test(case, namespace).split("\n"), 1)
        )

        system_message = (
            "You are a senior C# engineer fixing a generated xUnit test that "
            "does not compile. Fix only what the compiler errors point at."
        )

        prompt = f"""
#### TEST FILE ({case.name}.cs, with line numbers)
{numbered}

#### COMPILER ERRORS FOR THIS FILE
{chr(10).join(case.errors)}

#### CODE FROM THE CODEBASE UNDER TEST
{context or "NO CONTEXT PROVIDED"}

#### TASK
Return a corrected version of the test method(s) that compiles.

#### RULES
- `test_method`: only the method(s) inside the class, including the [Fact] or
  [Theory] attribute. No class, namespace or using lines.
- `imports`: every using directive the method needs, one per entry, written as
  `using X;`.
- Use only public types and members. Anything internal or private cannot be
  used from the test project, even if it appears in the code above.
- Use only constructors, methods and properties that exist in the code above
  or in .NET / xUnit. Do not invent helpers.
- Only xUnit is installed in the test project. Other test packages -- Moq,
  FluentAssertions, Xunit.SkippableFact ([SkippableFact], Skip.If) and so on
  -- are not, even if the codebase's own tests use them. Rewrite such code
  with plain xUnit ([Fact], Assert.*).
- Keep the test's purpose and assertions. Do not weaken an assertion just to
  make it compile.
- If the test cannot be fixed with the public API, return an empty
  `test_method`.
"""

        messages = [("system", system_message), ("user", prompt)]

        try:
            output = await structured_llm.ainvoke(messages)
        except (DailyLimitError, RateLimitTimeoutError):
            raise
        except Exception as e:
            progress(f"AI repair call failed for {case.name}: {e}")
            return None

        if output is None or not (output.test_method or "").strip():
            return None

        return output.imports or [], output.test_method

    return fix


def _repair(fix, cases, namespace, loop):
    """
    Run the repair calls on the agent's own event loop. Gemini's async client
    is tied to the loop it was first used on, and the agent already used it
    to generate the tests; a call from a fresh loop hung for minutes in a test
    on 2026-09-24. loop=None (no agent loop) runs on a temporary one.
    """
    async def run_batch():
        sem = asyncio.Semaphore(MAX_CONCURRENCY)

        async def guarded(case):
            async with sem:
                return await fix(case, namespace)

        return await asyncio.gather(*(guarded(case) for case in cases))

    if loop is not None:
        return loop.run_until_complete(run_batch())

    temporary = asyncio.new_event_loop()
    try:
        return temporary.run_until_complete(run_batch())
    finally:
        temporary.close()


def _first_error(case):
    return case.errors[0] if case.errors else "unknown compiler error"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def check_tests(
    kind,
    prefix,
    cases,
    rejected,
    codebase_path,
    codebase_name,
    results_dir,
    fix=None,
    loop=None,
    max_rounds=MAX_REPAIR_ROUNDS,
):
    """
    Write, build, repair and run one kind of generated test.

    @param kind "Unit" or "Integration", for messages.
    @param prefix "UT" or "IT": file prefix and class-name prefix.
    @param cases TestCases that passed clean_test().
    @param rejected TestCases clean_test() already turned down (reason set).
    @param results_dir Where the HTML report is written.
    @param fix Async repair function from make_fixer(), or None for no AI.
    @param loop The agent's event loop, which its model was already used on.
    @return TestRun
    """
    run = TestRun(kind=kind, generated=len(cases) + len(rejected))
    run.dropped.extend(rejected)

    test_dir = project_dir_for(codebase_path, codebase_name)
    namespace = namespace_for(codebase_name)

    ensure_test_project(test_dir, codebase_name)

    progress(f"Writing {len(cases)} {kind.lower()} tests, one file each...")
    write_tests(test_dir, namespace, prefix, cases)

    live = list(cases)

    while True:
        progress(f"Building {kind.lower()} tests...")
        errors_by_file, other_errors = build(test_dir)

        # A generated file of the other kind (or left over from an older run)
        # that no longer compiles would block this build. It is generated,
        # so remove it and say so.
        live_names = {case.name for case in live}
        stale = [name for name in errors_by_file if name not in live_names]
        for name in stale:
            (Path(test_dir) / f"{name}.cs").unlink(missing_ok=True)
            run.removed_stale.append(f"{name}.cs")
        if stale:
            progress(f"Removed {len(stale)} old generated test file(s) that no longer compile.")
            continue

        if other_errors:
            run.project_error = other_errors[0]
            run.kept = live
            progress(f"Test project did not build: {run.project_error}")
            return run

        broken = [case for case in live if case.name in errors_by_file]

        if not broken:
            break

        for case in broken:
            case.errors = errors_by_file[case.name]

        # The compiler reports errors in layers (a bad `using` hides the
        # errors in method bodies), so a test can first show up broken after
        # others were already repaired. Each test therefore gets its own
        # max_rounds tries rather than sharing a count across the run: on
        # Stateless a shared count left 4 tests dropped with no try at all.
        if fix is not None:
            exhausted = [case for case in broken if case.repairs >= max_rounds]
            broken = [case for case in broken if case.repairs < max_rounds]
        else:
            exhausted, broken = broken, []

        for case in exhausted:
            if fix is not None:
                case.reason = (
                    f"still does not compile after {case.repairs} AI "
                    f"repair(s) ({_first_error(case)})"
                )
            else:
                case.reason = f"does not compile ({_first_error(case)})"
            _drop(run, live, test_dir, case)

        if broken:
            progress(
                f"{len(broken)} {kind.lower()} test(s) do not compile; asking the AI "
                f"to fix them..."
            )

            for case, answer in zip(broken, _repair(fix, broken, namespace, loop)):
                if answer is None:
                    case.reason = f"does not compile and the AI could not fix it ({_first_error(case)})"
                    _drop(run, live, test_dir, case)
                    continue

                new_imports, new_body = answer
                body, imports, reason = clean_test(new_body, new_imports)

                if reason:
                    case.reason = f"the AI's repair was unusable: {reason}"
                    _drop(run, live, test_dir, case)
                    continue

                case.body, case.imports = body, imports
                case.repairs += 1
                _write_case(test_dir, namespace, case)

    run.kept = live

    if live:
        progress(f"Running {len(live)} {kind.lower()} tests...")
        (
            run.passed,
            run.failed,
            run.skipped,
            run.failed_tests,
            run.report_path,
        ) = run_tests(
            test_dir,
            namespace,
            prefix,
            results_dir,
            f"{kind.lower()}_test_report.html",
        )

    return run


def _drop(run, live, test_dir, case):
    live.remove(case)
    run.dropped.append(case)
    _remove_case(test_dir, case)


def write_results(run, output_dir, to_json):
    """
    Save the outcome next to the other outputs of this agent:
        validated_tests.json   tests that compiled (as finally written)
        discarded_tests.json   tests that were dropped, with the reason
        test_report.json       counts, failures and the reasons in one place

    @param to_json Turns a TestCase into the agent's own JSON shape.
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "validated_tests.json"), "w", encoding="utf-8") as file:
        json.dump([to_json(case) for case in run.kept], file, indent=2)

    with open(os.path.join(output_dir, "discarded_tests.json"), "w", encoding="utf-8") as file:
        json.dump(
            [dict(to_json(case), reason=case.reason) for case in run.dropped],
            file,
            indent=2,
        )

    with open(os.path.join(output_dir, "test_report.json"), "w", encoding="utf-8") as file:
        json.dump(dict(run.summary(), message=run.message()), file, indent=2)
