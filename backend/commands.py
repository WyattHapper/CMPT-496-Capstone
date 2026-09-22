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
import requests
from pathlib import Path
from backend.progress_logging import progress, pipeline_progress

# ---------------------------------------------------------
# Logging Configuration 
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

from backend.progress_logging import progress


# ---------------------------------------------------------
# IMPORTS FROM AGENT
# ---------------------------------------------------------

from agent.BR_agent import BRAgent
from agent.IT_agent import ITAgent
from agent.UT_agent import UTAgent
from agent.UTV_agent import UTVAgent
from agent.directory_agent import DirectoryAgent
from agent.file_summary_agent import FileSummaryAgent
from agent.structured_output.file_summary_output import BusinessRule
from agent.structured_output.UT_output import ValidatedRule
from agent.structured_output.UTV_output import UnitTest

from src.build_database import build_database
from src.build_database_JSON import build_database as build_summary_database

from utils.uml_json_to_pdf import (
    build_report as uml_build_report,
    parse_args as uml_parse_args,
)


def skipped_diagrams_message(skipped):
    """
    Warning for the Complete screen naming the diagrams the UML step
    skipped, so a missing picture in the PDF doesn't look like a bug.
    """
    noun = "diagram was" if len(skipped) == 1 else "diagrams were"
    return (
        f"{len(skipped)} UML {noun} skipped because the AI wrote invalid "
        f"diagram text: {', '.join(skipped)}. Everything else was created, "
        "and the PDF marks where each skipped diagram would be."
    )

from backend.token_estimate import estimate_pipeline
from backend.token_usage import (
    record_usage,
    record_to_log,
    suggest_constants,
    emit_stage_total,
)


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

        # Set by the dispatcher so measured usage can be filed per codebase.
        self.current_codebase_name = "unknown"

    # -----------------------------------------------------
    # Internal helper
    # -----------------------------------------------------

    
    def _run_command(self, command_name: str, func, *args, individualStep = True, **kwargs):
        """
        Executes a command while timing it and returning a
        consistent response object.

        Every public command should call this helper instead
        of duplicating try/except logic.
        """

        start = time.perf_counter()

        try:
            # Records real token usage for any LLM call made inside func,
            # streaming a running total to the frontend as it goes. Scopes
            # nest, so full_pipeline totals its stages as well as itself.
            # Stages that call no model record nothing.
            with record_usage(command_name, live=True) as usage:
                result = func(*args, **kwargs)

            summary = usage.summary()

            if summary["calls"]:
                emit_stage_total(summary)

            record_to_log(
                self.app_dir,
                self.current_codebase_name,
                summary,
            )

            elapsed = time.perf_counter() - start

            return {
                "success": True,
                "command": command_name,
                "elapsed": round(elapsed, 2),
                "individualStep": individualStep,
                "result": result,
            }

        except Exception as exc:

            elapsed = time.perf_counter() - start

            return {
                "success": False,
                "command": command_name,
                "elapsed": round(elapsed, 2),
                "individualStep": individualStep,
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
    # Calibration Commands
    # -----------------------------------------------------

    def token_calibration(self, codebase: str = None, individualStep = True):
        """
        Report measured token usage and the constants it suggests.
        """

        def task():
            progress("Reading recorded token usage...")

            name = Path(codebase).name if codebase else None

            result = suggest_constants(self.app_dir, name)

            if not result.get("success", False):
                raise RuntimeError(
                    result.get("error", "Calibration failed")
                )

            return result

        return self._run_command(
            "token_calibration",
            task,
            individualStep=individualStep,
        )

    # -----------------------------------------------------
    # Estimation Commands
    # -----------------------------------------------------

    def estimate_tokens(self, codebase: str, individualStep = True):
        """
        Estimate token usage for a full pipeline run without calling any LLM.
        """

        def task():
            progress("Estimating token usage...")

            result = estimate_pipeline(codebase, app_dir=self.app_dir)

            # _run_command only marks a command failed when it raises, so a
            # returned failure dict would surface as success to the frontend.
            if not result.get("success", False):
                raise RuntimeError(
                    result.get("error", "Token estimate failed")
                )

            return result

        return self._run_command(
            "estimate_tokens",
            task,
            individualStep=individualStep,
        )

    # -----------------------------------------------------
    # Database Commands
    # -----------------------------------------------------

    def build_database(self, codebase: str, individualStep = True):
        """
        Build the source code vector database.
        """

        def task():
            progress("Building source code database...")
            return build_database(codebase)

        return self._run_command(
            "build_database",
            task,
            individualStep=individualStep,
        )

    def build_summary_database(self, codebase: str, individualStep = True):
        """
        Build the summary vector database.
        """

        codebase_name = Path(codebase).name

        def task():
            progress("Building summary database...")
            return build_summary_database(codebase_name)

        return self._run_command(
            "build_summary_database",
            task,
            individualStep=individualStep,
        )

    def generate_file_summaries(self, codebase: str, individualStep = True):
        """
        Generate file-level summaries.
        """

        def task():
            progress("Generating file summaries...")
            return FileSummaryAgent().run(codebase)

        return self._run_command(
            "generate_file_summaries",
            task,
            individualStep=individualStep,
        )
    
    # -----------------------------------------------------
    # Summary / Agent Commands
    # -----------------------------------------------------

    def generate_directory_summaries(self, codebase: str, individualStep = True):
        """
        Generate directory-level summaries.

        Refactor of old:
            run_directory()
        """

        def task():
            progress("Generating directory summaries...")
            return DirectoryAgent().run(codebase)

        return self._run_command(
            "generate_directory_summaries",
            task,
            individualStep=individualStep,
        )


    def validate_business_rules(
        self,
        codebase: str,
        rules_path: str = None,
        individualStep = True
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

            progress("Validating business rules...")

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
            individualStep=individualStep,
        )


    def generate_unit_tests(
        self,
        codebase: str,
        selected_rules: list,
        validated_rules_path: str = None,
        individualStep = True
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

            progress("Generating unit tests...")

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
            individualStep=individualStep,
        )
    
    def validate_unit_tests(
        self,
        codebase: str,
        test_path: str = None,
        individualStep = True
    ):
        """
        Generate unit tests from validated rules.

        Refactor of old:
            run_ut()
        """

        codebase_path = Path(codebase)
        codebase_name = codebase_path.name


        if test_path is None:
            test_path = (
                self.app_dir
                / "agent"
                / "UT_agent_output"
                / codebase_name
                / "unit_tests.json"
            )


        test_path = Path(test_path)


        def task():

            progress("Validating unit tests...")

            if not test_path.exists():
                raise FileNotFoundError(
                    f"Validated rules not found: {test_path}"
                )


            with open(
                test_path,
                "r",
                encoding="utf-8"
            ) as file:

                raw_tests = json.load(file)

            input_tests = []
            for test in raw_tests:
                input_tests.append(UnitTest.model_validate(test))

            UTVAgent().run(
                input_tests,
                codebase_name,
                str(codebase_path)
            )


        return self._run_command(
            "validate_unit_tests",
            task,
            individualStep=individualStep,
        )
    


    def generate_integration_tests(
        self,
        codebase: str,
        selected_rules: list,
        validated_rules_path: str = None,
        individualStep=True
    ):
        """
        Generate integration tests from validated business rules.

        Uses workflow grouping to combine multiple business rules
        into end-to-end integration tests.
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

            progress("Generating integration tests...")


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


            # Convert JSON into ValidatedRule objects
            if selected_rules == []:

                input_rules = [
                    ValidatedRule.model_validate(rule)
                    for rule in raw_rules
                ]

            else:

                input_rules = []

                for rule in raw_rules:
                    if rule["id"] in selected_rules:
                        input_rules.append(
                            ValidatedRule.model_validate(rule)
                        )


            result = ITAgent().run(
                input_rules,
                codebase_name,
                str(codebase_path)
            )


            return {
                "message": "Integration tests generated successfully",
                "rules_processed": len(input_rules),
                "workflows_generated": len(
                    result.get("integration_tests", [])
                )
            }


        return self._run_command(
            "generate_integration_tests",
            task,
            individualStep=individualStep,
        )
    # -----------------------------------------------------
    # UML Commands
    # -----------------------------------------------------

    def generate_uml(self, summary_path: str, individualStep = True):
        """
        Generate a UML PDF from a single JSON summary file.

        Refactor of the old inner function:
            run_uml()
        """

        summary_path = str(summary_path)

        def task():

            progress("Generating UML diagrams...")

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
                skipped = uml_build_report(uml_parse_args())

            finally:
                sys.argv = old_argv

            result = {"skipped_diagrams": skipped}

            if skipped:
                result["warning"] = skipped_diagrams_message(skipped)

            return result


        return self._run_command(
            "generate_uml",
            task,
            individualStep=individualStep,
        )


    def generate_all_uml(
        self,
        summary_dir: str = None,
        codebase: str = None,
        individualStep = True
    ):
        """
        Generate UML PDFs for every JSON summary
        in a directory.

        Refactor of old:
            uml_generation()
        """

        if summary_dir is None:
            if codebase is None:
                raise ValueError("Either summary_dir or codebase is required.")

            codebase_name = Path(codebase).name
            summary_dir = (
                self.app_dir
                / "agent"
                / "file_summary_agent_output"
                / codebase_name
            )

        summary_dir = Path(summary_dir)


        def task():

            progress("Generating UML diagrams...")

            if not summary_dir.exists():
                raise FileNotFoundError(
                    f"Summary directory not found: {summary_dir}"
                )


            generated = []


            for summary_file in summary_dir.glob("*.json"):

                result = self.generate_uml(
                    str(summary_file),
                    individualStep=False
                )

                generated.append(result)


                if not result["success"]:
                    raise RuntimeError(
                        result["error"]
                    )


            skipped = [
                label
                for result in generated
                for label in result["result"]["skipped_diagrams"]
            ]

            summary = {
                "generated_files": generated,
                "skipped_diagrams": skipped,
            }

            if skipped:
                summary["warning"] = skipped_diagrams_message(skipped)

            return summary


        return self._run_command(
            "generate_all_uml",
            task,
            individualStep=individualStep,
        )
    
        # -----------------------------------------------------
    # Configuration Commands
    # -----------------------------------------------------

    # Model the pipeline actually uses. Verifying against this one rather
    # than just checking the key also catches a key that is real but has
    # no access to this model -- a failure that would otherwise only show
    # up part-way through a run.
    VALIDATION_MODEL = "gemini-3-flash-preview"
    VALIDATION_TIMEOUT_SECONDS = 15

    def verify_api_key(self, api_key: str):
        """
        Check a key by making the smallest real generation call possible.

        Returns a dict with:
            ok      True accepted, False rejected, None could not ask.
                    A failure to ask is not a rejection, so it does not
                    block a key that may be perfectly good.
            detail  human-readable reason, Google's own wording when it
                    rejected the key.
            model   the model version Google answered with.
            tokens  what this check cost, from Google's own accounting.
        """

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.VALIDATION_MODEL}:generateContent"
        )

        try:
            response = requests.post(
                url,
                params={"key": api_key},
                json={
                    # One token in, one token out: enough to prove the key
                    # works without a meaningful cost.
                    "contents": [{"parts": [{"text": "hi"}]}],
                    "generationConfig": {"maxOutputTokens": 1},
                },
                timeout=self.VALIDATION_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            return {
                "ok": None,
                "detail": f"Could not reach Google to verify the key ({exc}).",
                "model": None,
                "tokens": None,
            }

        try:
            body = response.json()
        except ValueError:
            body = {}

        if response.status_code == 200:

            # Google reports the exact model that answered and what the
            # call cost. Both are worth surfacing: the model confirms the
            # key can reach the one the pipeline needs, and the token
            # count is the honest price of checking.
            usage = body.get("usageMetadata") or {}

            return {
                "ok": True,
                "detail": "Key accepted by Google.",
                "model": body.get("modelVersion") or self.VALIDATION_MODEL,
                "tokens": usage.get("totalTokenCount"),
            }

        # Google puts a readable reason in the body; prefer it to the code.
        try:
            detail = body["error"]["message"]
        except (KeyError, TypeError):
            detail = response.text[:200] or f"HTTP {response.status_code}"

        return {
            "ok": False,
            "detail": detail,
            "model": None,
            "tokens": None,
        }

    def set_api_key(self, api_key: str):
        """
        Save the LLM API key.

        Refactor of old:
            get_api()

        The frontend now supplies the key instead of
        prompting the user through input().
        """

        def task():

            # Guarded in the frontend too, but an empty key must never
            # reach the file: a bare "GOOGLE_API_KEY=" reads back as
            # "no key" on the next launch while the running app believes
            # one is set.
            if not api_key or not api_key.strip():
                raise ValueError("No API key provided.")

            progress("Verifying API key...")

            check = self.verify_api_key(api_key.strip())

            if check["ok"] is False:
                raise ValueError(
                    "Google rejected this API key: " + str(check["detail"])
                )

            progress("Saving API key...")

            env_path = self.app_dir / ".env"

            with open(
                env_path,
                "w",
                encoding="utf-8"
            ) as env:

                env.write(
                    f"GOOGLE_API_KEY={api_key}\n"
                )


            if check["ok"] is None:
                return {
                    "message": (
                        "API key saved, but not verified. "
                        + str(check["detail"])
                    ),
                    "verified": False,
                    "model": None,
                    "tokens": None,
                }

            tokens = check["tokens"]
            unit = "token" if tokens == 1 else "tokens"
            cost = f" - {tokens} {unit} used" if tokens else ""

            return {
                "message": (
                    f"Key verified against {check['model']}{cost}. Saved."
                ),
                "verified": True,
                "model": check["model"],
                "tokens": tokens,
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

        progress(f"Pipeline codebase: {codebase}")
        

        if not codebase_path.exists():
            return {
                "success": False,
                "command": "full_pipeline",
                "error": (
                    f"Codebase does not exist: "
                    f"{codebase_path}"
                ),
            }

        progress(f"Resolved path: {codebase_path.resolve()}")
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

            pipeline_progress("Building database...", 5)
            steps.append( self._require_success(self.build_database(str(codebase_path), False)))

            pipeline_progress("Generating file summaries...", 26)
            steps.append( self._require_success(self.generate_file_summaries(str(codebase_path), False)))

            pipeline_progress("Building summary database...", 35)
            steps.append( self._require_success(self.build_summary_database(str(codebase_path), False)))

            pipeline_progress("Generating directory summaries...", 50)
            steps.append( self._require_success(self.generate_directory_summaries(str(codebase_path), False)))
            
            pipeline_progress("Validating business rules...", 65)
            steps.append( self._require_success(self.validate_business_rules(str(codebase_path), individualStep=False)))

            pipeline_progress("Generating unit tests...", 85)
            steps.append( self._require_success(self.generate_unit_tests(str(codebase_path), [], individualStep=False)))

            pipeline_progress("Generating integration tests...", 90)
            steps.append(self._require_success(self.generate_integration_tests(str(codebase_path),[],individualStep=False)))

            pipeline_progress("Generating UML report...", 95)
            steps.append( self._require_success(self.generate_all_uml(str(summary_directory), individualStep=False)))


            failed = [
                step
                for step in steps
                if not step["success"]
            ]


            if failed:
                raise RuntimeError(
                    failed
                )

            summary = {
                "steps": steps,
                "message": "Full pipeline completed",
            }

            # The UML step is last; pass on its warning if it skipped any
            # diagrams, so the Complete screen can show it.
            warning = steps[-1]["result"].get("warning")

            if warning:
                summary["warning"] = warning

            pipeline_progress("Pipeline Complete", 100)
            return summary


        return self._run_command(
            "full_pipeline",
            task,
            individualStep=True,
        )