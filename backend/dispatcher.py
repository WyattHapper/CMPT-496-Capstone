"""
backend/dispatcher.py

Central command router for the Codebase Analysis backend.

The frontend sends a command name and arguments.
The dispatcher routes the request to the correct
method in Commands.
"""

from backend.commands import Commands


class CommandDispatcher:
    """
    Routes frontend requests to backend commands.
    """

    def __init__(self):
        self.commands = Commands()

        # Store all backend errors for this session
        self.error_log = []

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

            # UML
            "generate_uml": self.commands.generate_uml,
            "generate_all_uml": self.commands.generate_all_uml,

            # API
            "set_api_key": self.commands.set_api_key,
            
            # Pipeline
            "full_pipeline": self.commands.full_pipeline,

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
            self.error_log.append(error)

            return {
                "success": False,
                "error": error,
                "command": command
            }

        # Optional: clear old errors when running the full pipeline
        if command == "full_pipeline":
            self.clear_errors()

        handler = self.routes[command]

        try:

            result = handler(**kwargs)

            # Some commands return {"success": False}
            if (
                isinstance(result, dict)
                and result.get("success") is False
            ):
                self.error_log.append(
                    f"[{command}] {result.get('error', 'Unknown error')}"
                )

            return result

        except Exception as e:

            error = f"[{command}] {str(e)}"

            self.error_log.append(error)

            return {
                "success": False,
                "error": error,
                "command": command
            }