from pathlib import Path

from agent.testing.framework_registry import get_test_framework
from lsp.language import detect_language

class RunnerRegistry:
    """Use langauge detection to find out what framework should be used and find the registry that correlates to it to create the runner"""
    
    RUNNER_CLASSES = {
        "xunit": ("agent.testing.runners.xunit_runner", "XUnitRunner"),
        "pytest": ("agent.testing.runners.pytest_runner", "PytestRunner"),
        "jest": ("agent.testing.runners.jest_runner", "JestRunner"),
        "vitest": ("agent.testing.runners.vitest_runner", "VitestRunner"),
        "junit5": ("agent.testing.runners.junit_runner", "JUnitRunner"),
    }
    
    SUPPORTED_RUNNER_LANGUAGES = {
        "csharp",
        "python",
        "javascript",
        "typescript",
        "java",
    }
    @classmethod
    def detect_language(cls, state: dict) -> str:
        """
        detect the language so that the proper framework can be chosen for unit testing"""

        languages = set()

        for test in state.get("unit_tests", []):
            if isinstance(test,dict):
                paths = test.get("source_file_paths", [])
            else: 
                paths = getattr(test, "source_file_paths", [])

            if isinstance(paths, (str,Path)):
                paths = [paths]

            for path in paths or []:
                language = detect_language(str(path))

                if language in cls.SUPPORTED_RUNNER_LANGUAGES:
                    languages.add(language)

            if len(languages == 1):
                return languages.pop()
            
            if len(languages) > 1:
                raise ValueError(f"Generated tests reference multiple languages: {', '.join(languages)}\nMixed language runner support is not implemented yet.")
            
            raise ValueError("uld not determine a test language")
        
    @classmethod
    def create_runner(cls, language:str):
        config = get_test_framework(language)

        if config is None: raise ValueError(f"There is no configured tesst framework for this language: {language}")

        runner_info = cls.RUNNER_CLASSES.get(config.framework)

        if runner_info is None:
            raise ValueError(f"No runner for registered framework: {config.framework}")
        
        module_name, class_name = runner_info

        try:
            module = __import__(module_name, fromList=[class_name])

            runner_class = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            raise NotImplementedError(f"The {config.framework} runner is configured but has not been implemented or could not be imported: {module_name}.{class_name}") from exc
        
        return runner_class()