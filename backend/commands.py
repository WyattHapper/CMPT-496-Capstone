"""
backend/commands.py

Backend command implementations for the Codebase Analysis project.

Each public method represents a command that can be dispatched from
dispatcher.py and called by the frontend.
"""

import logging
import sys
sys.stdout.reconfigure(
    encoding='utf-8',
    line_buffering=True
)
import os
import subprocess
from xml.parsers.expat import errors
import chromadb
import json
import time
from pathlib import Path

# ---------------------------------------------------------
# Logging Configuration 
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# IMPORTS FROM AGENT
# ---------------------------------------------------------

from agent.BR_agent import BRAgent
from agent.UT_agent import UTAgent
from agent.directory_agent import DirectoryAgent
from agent.file_summary_agent import FileSummaryAgent
from agent.structured_output.file_summary_output import BusinessRule
from agent.structured_output.UT_output import ValidatedRule

from src.build_database import build_database
from src.build_database_JSON import build_database as build_summary_database

from utils.uml_json_to_pdf import main as uml_main


# ---------------------------------------------------------
# Application directory
# ---------------------------------------------------------

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent


class Commands:
    """
    Implements every backend command that can be requested
    by the frontend.
    """

    def __init__(self):
        self.app_dir = APP_DIR

    # -----------------------------------------------------
    # Internal helper
    # -----------------------------------------------------

    def send_progress(self, message: str):
        """
        Send a progress update to the Electron frontend.
        """

        print(
            json.dumps(
                {
                    "type": "progress",
                    "stage": message,
                }
            ),
            flush=True,
        )

    
    def _run_command(self, command_name: str, func, *args, **kwargs):
        """
        Executes a command while timing it and returning a
        consistent response object.

        Every public command should call this helper instead
        of duplicating try/except logic.
        """

        start = time.perf_counter()

        try:
            result = func(*args, **kwargs)

            elapsed = time.perf_counter() - start

            return {
                "success": True,
                "command": command_name,
                "elapsed": round(elapsed, 2),
                "result": result,
            }

        except Exception as exc:

            elapsed = time.perf_counter() - start

            return {
                "success": False,
                "command": command_name,
                "elapsed": round(elapsed, 2),
                "error": str(exc),
            }
        
    def _require_success(self, result):
        """
        Stops pipeline execution if a command fails.
        """

        if not result["success"]:
            raise RuntimeError(
                result.get(
                    "error",
                    "Unknown command failure"
                )
            )

        return result

    # -----------------------------------------------------
    # Database Commands
    # -----------------------------------------------------

    def build_database(self, codebase: str):
        """
        Build the source code vector database.
        """

        def task():
            self.send_progress("Building source code database...")
            return build_database(codebase)

        return self._run_command(
            "build_database",
            task,
        )

    def build_summary_database(self, codebase: str):
        """
        Build the summary vector database.
        """

        codebase_name = Path(codebase).name

        def task():
            self.send_progress("Building summary database...")
            return build_summary_database(codebase_name)

        return self._run_command(
            "build_summary_database",
            task,
        )

    def generate_file_summaries(self, codebase: str):
        """
        Generate file-level summaries.
        """

        def task():
            self.send_progress("Generating file summaries...")
            return FileSummaryAgent().run(codebase)

        return self._run_command(
            "generate_file_summaries",
            task,
        )
    
    # -----------------------------------------------------
    # Summary / Agent Commands
    # -----------------------------------------------------

    def generate_directory_summaries(self, codebase: str):
        """
        Generate directory-level summaries.

        Refactor of old:
            run_directory()
        """

        def task():
            self.send_progress("Generating directory summaries...")
            return DirectoryAgent().run(codebase)

        return self._run_command(
            "generate_directory_summaries",
            task,
        )


    def validate_business_rules(
        self,
        codebase: str,
        rules_path: str = None
    ):
        """
        Validate generated business rules.

        Refactor of old:
            run_br()
        """

        codebase_path = Path(codebase)
        codebase_name = codebase_path.name

        if rules_path is None:
            rules_path = (
                self.app_dir
                / "agent"
                / "file_summary_agent_output"
                / codebase_name
                / "business_rules"
                / "business_rules.json"
            )

        rules_path = Path(rules_path)

        def task():

            self.send_progress("Validating business rules...")

            if not rules_path.exists():
                raise FileNotFoundError(
                    f"Business rules not found: {rules_path}"
                )

            with open(
                rules_path,
                "r",
                encoding="utf-8"
            ) as file:

                raw_rules = json.load(file)


            input_rules = {
                path: [
                    BusinessRule(**rule)
                    for rule in rules
                ]
                for path, rules in raw_rules.items()
            }


            BRAgent().run(
                input_rules,
                codebase_name
            )


        return self._run_command(
            "validate_business_rules",
            task,
        )


    def generate_unit_tests(
        self,
        codebase: str,
        selected_rules: list,
        validated_rules_path: str = None,
    ):
        """
        Generate unit tests from validated rules.

        Refactor of old:
            run_ut()
        """

        codebase_path = Path(codebase)
        codebase_name = codebase_path.name


        if validated_rules_path is None:
            validated_rules_path = (
                self.app_dir
                / "agent"
                / "BR_agent_output"
                / codebase_name
                / "validated_rules.json"
            )


        validated_rules_path = Path(validated_rules_path)


        def task():

            self.send_progress("Generating unit tests...")

            if not validated_rules_path.exists():
                raise FileNotFoundError(
                    f"Validated rules not found: {validated_rules_path}"
                )


            with open(
                validated_rules_path,
                "r",
                encoding="utf-8"
            ) as file:

                raw_rules = json.load(file)

            if selected_rules == []:
                input_rules = [
                    ValidatedRule.model_validate(rule)
                    for rule in raw_rules
                ]

            else:
                input_rules = []
                for rule in raw_rules:
                    if rule["id"] in selected_rules:
                        input_rules.append(ValidatedRule.model_validate(rule))

            UTAgent().run(
                input_rules,
                codebase_name,
                str(codebase_path)
            )


        return self._run_command(
            "generate_unit_tests",
            task,
        )
    

    # -----------------------------------------------------
    # UML Commands
    # -----------------------------------------------------

    def generate_uml(self, summary_path: str):
        """
        Generate a UML PDF from a single JSON summary file.

        Refactor of the old inner function:
            run_uml()
        """

        summary_path = str(summary_path)

        def task():

            self.send_progress("Generating UML diagrams...")

            old_argv = sys.argv

            jar_path = self.app_dir / "plantuml.jar"

            if not jar_path.exists():
                jar_path = Path.home() / "plantuml.jar"


            if not jar_path.exists():
                raise FileNotFoundError(
                    "PlantUML jar not found."
                )


            sys.argv = [
                "uml_json_to_pdf",
                summary_path,
                "--plantuml-jar",
                str(jar_path),
            ]


            try:
                uml_main()

            finally:
                sys.argv = old_argv


        return self._run_command(
            "generate_uml",
            task,
        )


    def generate_all_uml(self, summary_dir: str):
        """
        Generate UML PDFs for every JSON summary
        in a directory.

        Refactor of old:
            uml_generation()
        """

        summary_dir = Path(summary_dir)


        def task():

            self.send_progress("Generating UML diagrams...")

            if not summary_dir.exists():
                raise FileNotFoundError(
                    f"Summary directory not found: {summary_dir}"
                )


            generated = []


            for summary_file in summary_dir.glob("*.json"):

                result = self.generate_uml(
                    str(summary_file)
                )

                generated.append(result)


                if not result["success"]:
                    raise RuntimeError(
                        result["error"]
                    )


            return {
                "generated_files": generated
            }


        return self._run_command(
            "generate_all_uml",
            task,
        )
    
        # -----------------------------------------------------
    # Configuration Commands
    # -----------------------------------------------------

    def set_api_key(self, api_key: str):
        """
        Save the LLM API key.

        Refactor of old:
            get_api()

        The frontend now supplies the key instead of
        prompting the user through input().
        """

        def task():

            self.send_progress("Saving API key...")

            env_path = self.app_dir / ".env"

            with open(
                env_path,
                "w",
                encoding="utf-8"
            ) as env:

                env.write(
                    f"GOOGLE_API_KEY={api_key}\n"
                )


            return {
                "message": "API key saved"
            }


        return self._run_command(
            "set_api_key",
            task,
        )


    

    # -----------------------------------------------------
    # Pipeline Command
    # -----------------------------------------------------

    def full_pipeline(self, codebase: str):

        
        """
        Run the complete analysis pipeline.

        Replacement for the old menu option:

            1. Full Codebase Analysis Pipeline

        """

        codebase_path = Path(codebase)

        logger.info(f"Pipeline codebase: {codebase}")
        logger.info(f"Resolved path: {codebase_path.resolve()}")

        if not codebase_path.exists():
            return {
                "success": False,
                "command": "full_pipeline",
                "error": (
                    f"Codebase does not exist: "
                    f"{codebase_path}"
                ),
            }


        codebase_name = codebase_path.name


        rules_path = (
            self.app_dir
            / "agent"
            / "file_summary_agent_output"
            / codebase_name
            / "business_rules"
            / "business_rules.json"
        )


        validated_rules_path = (
            self.app_dir
            / "agent"
            / "BR_agent_output"
            / codebase_name
            / "validated_rules.json"
        )


        summary_directory = (
            self.app_dir
            / "agent"
            / "file_summary_agent_output"
            / codebase_name
        )


        def task():

            steps = []

            
            steps.append( self._require_success(self.build_database(str(codebase_path))))

            
            steps.append( self._require_success(self.generate_file_summaries(str(codebase_path))))

            
            steps.append( self._require_success(self.build_summary_database(str(codebase_path))))

            
            steps.append( self._require_success(self.generate_directory_summaries(str(codebase_path))))
            
            
            steps.append( self._require_success(self.validate_business_rules(str(codebase_path))))

            
            steps.append( self._require_success(self.generate_unit_tests(str(codebase_path))))

            
            steps.append( self._require_success(self.generate_all_uml(str(summary_directory))))


            failed = [
                step
                for step in steps
                if not step["success"]
            ]


            if failed:
                raise RuntimeError(
                    failed
                )


            return {
                "steps": steps,
                "message": (
                    "Full pipeline completed"
                ),
            }


        return self._run_command(
            "full_pipeline",
            task,
        )