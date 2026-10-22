"""
@file agent/testing/runners/base_runner.py
@brief Defines shared functionlity for all of the other runners 
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class base_runner(ABC):

    """
    @brief The base runner class
    
    @details holds all of the shared functionality that all of the runners need to use
    """

    @abstractmethod
    def run(self, state):

        pass

    @staticmethod
    def _prepare_directory(directory):
        directory.mkdir(parents = True, exist_ok=True)

        return directory
    
    def _execute_command(self, command: list[str], cwd: Path, log_path:Path, report_path: Path | None = None, timeout: int = 600):
        """"
        @brief runs a test command and gets its output

        @param command The command and arguments to execute.
        @param cwd The working directory for the command.
        @param log_path The path where execution logs are written.
        @param report_path Optional path to the generated test report.
        @param test_file Optional path to the generated test file.
        @param timeout Maximum execution time in seconds.
        @return A dictionary containing execution status, output, and paths.

        """

   

    @staticmethod
    def _decode_output(output) -> str:
        """Normalize timeout output across Python versions."""
        if output is None:
            return ""
        if isinstance(output, bytes):
            return output.decode("utf-8", errors="replace")
        return str(output)