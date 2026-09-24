"""
backend/dispatcher.py

Central command router for the Codebase Analysis backend.

The frontend sends a command name and arguments.
The dispatcher routes the request to the correct
method in Commands.
"""

import json
import os
from datetime import datetime

from backend.commands import Commands


# Saved so the Insights "Errors" view still has them after the app restarts.
ERROR_LOG_NAME = "error_log.json"


class CommandDispatcher:
    """
    Routes frontend requests to backend commands.
    """

    def __init__(self):
        self.commands = Commands()

        # Backend errors since the last full pipeline started, each with its
        # time, command and error code (429, 503, ...). Kept on disk.
        self.error_log = self._load_errors()

        self.routes = {


            # Database
            "build_database": self.commands.build_database,
            "build_summary_database": self.commands.build_summary_database,

            # File summaries
            "file_summary":self.commands.generate_file_summaries,

            "generate_file_summaries": self.commands.generate_file_summaries,

            # Directory summaries
            "directory_summary": self.commands.generate_directory_summaries,

            "generate_directory_summaries": self.commands.generate_directory_summaries,

            # Business rules / tests
            "validate_business_rules": self.commands.validate_business_rules,
            "generate_unit_tests": self.commands.generate_unit_tests,
            "validate_unit_tests": self.commands.validate_unit_tests,
            "generate_integration_tests": self.commands.generate_integration_tests,

            # UML
            "generate_uml": self.commands.generate_uml,
            "generate_all_uml": self.commands.generate_all_uml,

            # API
            "set_api_key": self.commands.set_api_key,
            
            # Pipeline
            "full_pipeline": self.commands.full_pipeline,

            # Estimation
            "estimate_tokens": self.commands.estimate_tokens,
            "token_calibration": self.commands.token_calibration,

            # Usage
            "get_run_usage": self.commands.get_run_usage,

            # Error log
            "get_errors": self.get_errors,

        }

    def get_errors(self):
        """
        Return every recorded backend error.
        """
        return {
            "success": True,
            "errors": self.error_log
        }

    def clear_errors(self):
        """
        Clear the error log.
        """
        self.error_log.clear()
        self._save_errors()

    def _error_log_path(self):
        return self.commands.app_dir / ERROR_LOG_NAME

    def _load_errors(self):
        try:
            data = json.loads(self._error_log_path().read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save_errors(self):
        # Best-effort: failing to save an error must not become an error.
        try:
            path = self._error_log_path()
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(self.error_log, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            pass

    def _record_error(self, command, message, code=None):
        self.error_log.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "command": command,
            "code": code,
            "message": message,
        })
        self._save_errors()

    def dispatch(self, command: str, **kwargs):
        """
        Execute a backend command.

        Example:

            dispatcher.dispatch(
                "build_database",
                codebase="C:/project"
            )
        """

        if command not in self.routes:
            error = f"Unknown command: {command}"
            self._record_error(command, error)

            return {
                "success": False,
                "error": error,
                "command": command
            }

        # Optional: clear old errors when running the full pipeline
        if command == "full_pipeline":
            self.clear_errors()

        # Tell Commands which codebase measured usage belongs to.
        if "codebase" in kwargs and kwargs["codebase"]:
            from pathlib import Path
            self.commands.current_codebase_name = Path(
                kwargs["codebase"]
            ).name

        handler = self.routes[command]

        try:

            result = handler(**kwargs)

            # Some commands return {"success": False}
            if (
                isinstance(result, dict)
                and result.get("success") is False
            ):
                self._record_error(
                    command,
                    result.get("error", "Unknown error"),
                    result.get("error_code"),
                )

            return result

        except Exception as e:

            error = f"[{command}] {str(e)}"

            self._record_error(command, str(e))

            return {
                "success": False,
                "error": error,
                "command": command
            }