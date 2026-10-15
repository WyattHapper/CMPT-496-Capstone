import logging
import os
import subprocess
from pathlib import Path

from backend.progress_logging import progress

logger = logging.getLogger(__name__)

class XUnitRunner:
    def run(self, state):
            """
            @brief Creates test framework in target codebase and runs it

            @details Takes the generated unit tests and applies them with a testing framework and generates a report based on its results

            @param state Current workflow state contain unit_tests
            @return Empty dict
            """
            codebase_path = state["codebase_path"]
            codebase_name  = state["codebase_name"]
            test_subdir = os.path.join(codebase_path, f"{codebase_name}.Tests")

            # Generate Xunit framework
            if not Path(test_subdir).is_dir():
                try:
                    progress("Generating test framework", 98)
                    subprocess.run(["dotnet", "new", "xunit", "-o", f"{test_subdir}"])
                    with open(f"{test_subdir}/{codebase_name}.Tests.csproj", "r+", encoding="utf-8") as file:
                        lines = file.readlines()
                        lines.insert(-1, '<ItemGroup>\n<ProjectReference Include="..\\**\\*.csproj" Exclude="..\\**\\*.Tests.csproj" />\n</ItemGroup>\n\n')
                        file.seek(0)
                        file.writelines(lines)
                except Exception as e:
                    logger.error(f"Error: {e}")
                    progress("Error generating framework", 98)

            # Write generated tests to Xunit .cs file
            test_imports = state["test_imports"]
            unit_tests = state["unit_tests"]
            with open(f"{test_subdir}/UnitTest1.cs", "w", encoding="utf-8") as file:
                for import_statement in test_imports:
                    file.write(import_statement + "\n")
                file.write(f"\nnamespace {codebase_name}.Tests;\n".replace("-", "_"))
                file.write("\npublic class Tests {\n")
                for test in unit_tests:
                    file.write(test.unit_test + "\n\n")
                file.write("}")
            
            # Run generated tests and produce report
            base_output_dir = state.get("output_directory", "./agent/UT_agent_output")
            codebase_dir = os.path.join(base_output_dir, codebase_name)
            try:
                progress("Running generated tests", 99)
                subprocess.run(["dotnet", "test", f"{test_subdir}", "--logger", "html", "--results-directory", f"{codebase_dir}"])
                logger.info(f"Successfully ran tests and report generated to {codebase_dir}")
                progress(f"Successfully ran tests and report generated to {codebase_dir}", 100, True)
            except Exception as e:
                logger.error(e)
                progress("Error running tests!", 100, True)
            return {}
        

