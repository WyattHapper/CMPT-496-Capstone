
"""
@file agent/testing/runners/pytest_runner.py
@brief Writes and executes generated Python tests using pytest.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class PytestRunner:
    """Creates and runs generated tests with pytest."""

    def run(self, state):
        """
        @brief Writes generated Python tests and executes them with pytest.

        @param state The current UTGraphState containing generated tests,
                     codebase paths, and output configuration.
        @return The updated state with the pytest execution result.
        """
        codebase_path = Path(state["codebase_path"]).resolve()
        codebase_name = state.get("codebase_name", codebase_path.name)

        output_directory = Path(
            state.get("output_directory", "./agent/UT_agent_output")
        ).resolve() / codebase_name

        test_directory = codebase_path / "tests"
        test_file = test_directory / "test_generated.py"

        test_directory.mkdir(parents=True, exist_ok=True)
        output_directory.mkdir(parents=True, exist_ok=True)

        unit_tests = state.get("unit_tests", [])

        if not unit_tests:
            state["test_result"] = {
                "status": "no_tests",
                "returncode": None,
                "stdout": "",
                "stderr": "No generated tests were provided.",
            }
            return state

        test_source = self._build_test_source(unit_tests)
        test_file.write_text(test_source, encoding="utf-8")

        python_executable = self._find_python(codebase_path)

        report_path = output_directory / "pytest-results.xml"
        log_path = output_directory / "pytest.log"

        command = [
            python_executable,
            "-m",
            "pytest",
            str(test_file),
            "-v",
            f"--junitxml={report_path}",
        ]

        logger.info("Running pytest: %s", " ".join(command))

        try:
            result = subprocess.run(
                command,
                cwd=codebase_path,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )

            log_path.write_text(
                "=== STDOUT ===\n"
                + result.stdout
                + "\n=== STDERR ===\n"
                + result.stderr,
                encoding="utf-8",
            )

            state["test_result"] = {
                "status": (
                    "passed" if result.returncode == 0 else "failed"
                ),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "report_path": str(report_path),
                "log_path": str(log_path),
                "test_file": str(test_file),
            }

        except subprocess.TimeoutExpired as exc:
            stdout = self._decode_output(exc.stdout)
            stderr = self._decode_output(exc.stderr)

            state["test_result"] = {
                "status": "timeout",
                "returncode": None,
                "stdout": stdout,
                "stderr": stderr or "Pytest timed out after 600 seconds.",
                "test_file": str(test_file),
            }

        except OSError as exc:
            logger.exception("Could not execute pytest")

            state["test_result"] = {
                "status": "error",
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
                "test_file": str(test_file),
            }

        return state

    @staticmethod
    def _find_python(codebase_path: Path) -> str:
        """Prefer a Python interpreter inside the target codebase."""
        candidates = [
            codebase_path / ".venv" / "bin" / "python",
            codebase_path / "venv" / "bin" / "python",
            codebase_path / ".venv" / "Scripts" / "python.exe",
            codebase_path / "venv" / "Scripts" / "python.exe",
        ]

        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

        return sys.executable

    @staticmethod
    def _build_test_source(unit_tests) -> str:
        """Combine generated imports and test bodies into one test module."""
        imports = []
        test_bodies = []

        for test in unit_tests:
            if isinstance(test, dict):
                test_imports = test.get("imports", [])
                test_body = test.get("unit_test", "")
            else:
                test_imports = getattr(test, "imports", [])
                test_body = getattr(test, "unit_test", "")

            if isinstance(test_imports, str):
                test_imports = [test_imports]

            for item in test_imports or []:
                item = str(item).strip()
                if item and item not in imports:
                    imports.append(item)

            if test_body and str(test_body).strip():
                test_bodies.append(str(test_body).strip())

        sections = []

        if imports:
            sections.append("\n".join(imports))

        if test_bodies:
            sections.append("\n\n".join(test_bodies))

        if not sections:
            return (
                '"""Generated test file: no executable test bodies found."""\n'
            )

        return "\n\n\n".join(sections) + "\n"

    @staticmethod
    def _decode_output(output) -> str:
        """Normalize timeout output across Python versions."""
        if output is None:
            return ""
        if isinstance(output, bytes):
            return output.decode("utf-8", errors="replace")
        return str(output)