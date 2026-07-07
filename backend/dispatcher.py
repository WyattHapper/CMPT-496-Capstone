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

        self.routes = {
            # Database commands
            "build_database":
                self.commands.build_database,

            "build_summary_database":
                self.commands.build_summary_database,


            # Summary generation commands
            "generate_file_summaries":
                self.commands.generate_file_summaries,

            "generate_directory_summaries":
                self.commands.generate_directory_summaries,


            # Rule / testing commands
            "validate_business_rules":
                self.commands.validate_business_rules,

            "generate_unit_tests":
                self.commands.generate_unit_tests,


            # UML commands
            "generate_uml":
                self.commands.generate_uml,

            "generate_all_uml":
                self.commands.generate_all_uml,


            # Configuration
            "set_api_key":
                self.commands.set_api_key,


            # Pipeline
            "full_pipeline":
                self.commands.full_pipeline,
        }


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
            return {
                "success": False,
                "error": (
                    f"Unknown command: {command}"
                )
            }


        handler = self.routes[command]

        return handler(**kwargs)