from dataclasses import dataclass

@dataclass (frozen = True)
class TestFrameworkConfig:
    language:str
    framework:str
    test_file:str
    test_directory:str
    runner:str



TEST_FRAMEWORKS = {
    "csharp": TestFrameworkConfig(
        language="csharp",
        framework="xunit",
        test_file="UnitTest1.cs",
        test_directory="{codebase_name}.Tests",
        runner="dotnet"
    ),
    "python": TestFrameworkConfig(
        language="python",
        framework="pytest",
        test_file="test_generated.py",
        test_directory="tests",
        runner="python -m pytest"
    ),
    "javascript": TestFrameworkConfig(
        language="javascript",
        framework="jest",
        test_file="generated.test.js",
        test_directory="tests",
        runner="npx jest"
    ),
    "typescript": TestFrameworkConfig(
        language="typescript",
        framework="vitest",
        test_file="generated.test.ts",
        test_directory="tests",
        runner="npx vitest"
    ),
    "java": TestFrameworkConfig(
        language="java",
        framework="junit5",
        test_file="GeneratedTest.java",
        test_directory="src/test/java",
        runner="maven-or-gradle"
    ),

}

def get_test_framework(language: str):
    return TEST_FRAMEWORKS.get(language.lower())
