"""
@file main.py
@brief Central CLI entry point for the Codebase Analysis project.
@details Provides a menu-driven interface to orchestrate the end-to-end 
summarization pipeline, manage vector databases, and preview indexed source 
code and summaries.
"""

import sys
import os

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

import os
import subprocess
from xml.parsers.expat import errors
import chromadb
import time
import json
from pathlib import Path

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

"""
if len(sys.argv) > 1:
    output_dir = sys.argv[1]
else:
"""

output_dir = str(APP_DIR)

import subprocess
from xml.parsers.expat import errors
import chromadb
import time
from pathlib import Path

def clear_screen():
    """
    @brief Clears the terminal screen for better readability.
    @details Detects the operating system and issues the appropriate system 
    command ('cls' for Windows, 'clear' for Unix-like systems).
    """
    os.system("cls" if os.name == "nt" else "clear")

def run_step(step_name: str, module: str, args: list, errors: list):
    print(f"Running step: {step_name}...")
    start = time.perf_counter()
    try:
        from src.build_database import build_database as _build_db
        from src.build_database_JSON import build_database as _build_db_json
        from agent.file_summary_agent import FileSummaryAgent
        from agent.directory_agent import DirectoryAgent
        from agent.BR_agent import BRAgent
        from agent.UT_agent import UTAgent
        from agent.UTV_agent import UTVAgent
        from utils.uml_json_to_pdf import main as _uml_main
        from agent.structured_output.file_summary_output import BusinessRule
        from agent.structured_output.UT_output import ValidatedRule
        import json

        def run_file_summary(args):
            agent = FileSummaryAgent()
            agent.run(args[0], output_dir=output_dir)

        def run_directory(args):
            agent = DirectoryAgent()
            agent.run(args[0], output_dir=output_dir)

        def run_br(args):
            codebase_name, rules_path = args[0], args[1]
            with open(rules_path, "r", encoding="utf-8") as f:
                raw_rules = json.load(f)
            input_rules = {
                path: [BusinessRule(**rule) for rule in rules]
                for path, rules in raw_rules.items()
            }
            agent = BRAgent()
            agent.run(input_rules, codebase_name, output_dir=output_dir)

        def run_ut(args):
            codebase_path, rules_path, input_ids = str(args[0]), args[1], args[2]
            codebase_name = Path(codebase_path).name
            with open(rules_path, "r", encoding="utf-8") as f:
                raw_rules = json.load(f)
            if len(input_ids) == 0:
                input_rules = [ValidatedRule.model_validate(rule) for rule in raw_rules]
            else:
                input_rules = []
                for rule in raw_rules:
                    if rule["id"] in input_ids:
                        input_rules.append(ValidatedRule.model_validate(rule))
            agent = UTAgent()
            agent.run(input_rules, codebase_name, codebase_path)

        def run_utv(args):
            codebase_path, rules_path = str(args[0]), args[1]
            codebase_name = Path(codebase_path).name
            with open(rules_path, "r", encoding="utf-8") as f:
                raw_rules = json.load(f)
            input_rules = [ValidatedRule.model_validate(rule) for rule in raw_rules]
            agent = UTVAgent()
            agent.run(input_rules, codebase_name, codebase_path, output_dir=output_dir)
        
        def run_uml(args):
            old_argv = sys.argv
            jar_path = APP_DIR / "plantuml.jar"
            if not jar_path.exists():
                jar_path = Path.home() / "plantuml.jar"
            sys.argv = ['uml_json_to_pdf', args[0], '--plantuml-jar', str(jar_path)]
            try:
                _uml_main()
            finally:
                sys.argv = old_argv

        dispatch = {
            "src.build_database":       lambda args: _build_db(args[0]),
            "src.build_database_JSON":  lambda args: _build_db_json(args[0]),
            "agent.file_summary_agent": run_file_summary,
            "agent.directory_agent":    run_directory,
            "agent.BR_agent":           run_br,
            "agent.UT_agent":           run_ut,
            "agent.UTV_agent":          run_utv,
            "utils.uml_json_to_pdf":    run_uml,
        }

        if module not in dispatch:
            raise RuntimeError(f"Unknown module: {module}")

        dispatch[module](args)

        elapsed = time.perf_counter() - start
        print(f"{step_name} completed in {elapsed:.2f} seconds.")
        return True

    except Exception as e:
        err_msg = f"Failed to run {step_name}: {e}"
        print(f"\n[!] {err_msg}")
        errors.append(err_msg)
        return False
    
def uml_generation(dir_path: Path, errors: list):
    """
    @brief Generates UML diagrams from JSON summaries in the specified directory.
    @details Iterates through all JSON files in the given directory, invoking the
    UML generation utility for each file to produce corresponding PDF diagrams.
    @param dir_path The path to the directory containing JSON summary files.
    @param errors A list to collect any errors that occur during the process.
    @return None
    """
    summaries = [str(file) for file in dir_path.glob("*.json")]
    for summary_path in summaries:
        if not run_step("UML Generation", "utils.uml_json_to_pdf", [summary_path], errors):
            return False
    return True

def get_api():
    env_path = APP_DIR / ".env"
    if env_path.exists():
        while True:
            clear_screen()
            print("========================================")
            print("WARNING: API key already exists.")
            print("Are you sure you would like to continue?")
            print("(Doing so will overwrite previous key)")
            print("========================================")
            print("1. Continue")
            print("2. Exit")
            choice = input("\nSelect option (1 or 2): ")
            if choice == '2':
                return False
            elif choice == '1':
                break
    key = input("\nEnter LLM API key: ")
    try:
        with open(env_path, "w", encoding = "utf-8") as env:
            env.write(f"GOOGLE_API_KEY={key}")
    except Exception as e:
        input(f"\nUnable to add API key: {e}. Press Enter... ")
        return False
    input("\nAPI key successfully added! Press Enter... ")
    return True

def select_rules(validated_rules_path):
    with open(validated_rules_path, "r", encoding="utf-8") as file:
        raw_rules = json.load(file)
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("================================")
        print("   Validated Rules Selection")
        print("================================")
        for rule in raw_rules:
            print(f"\n{rule['id']}. {rule['rule']}")
        choice = input("Select the rules you would like to generate tests for (Seperate the IDs with commas) or select every rule (All): ").lower()
        if choice == "all":
            return []
        try: 
            selections = [int(id.strip()) for id in choice.split(",")]
        except:
            input("Invalid output please try again.")
            continue
        return selections
    
def processing_menu(errors: list):
    """
    @brief Sub-menu for initiating the summarization process.
    """
    while True:
        clear_screen()
        print("========================================")
        print("   CODEBASE ANALYSIS SYSTEM - CLI")
        print("========================================")
        print("1. Full Codebase Analysis Pipeline")
        print("2. Create Code Database Only")
        print("3. Create JSON Summaries Only")
        print("4. Create Summary Database from JSON Only")
        print("5. Create Directory Summaries Only")
        print("6. Run Business Rule Validation Only")
        print("7. Run UML Generation Only")
        print("8. Run Unit Test Generation Only")
        print("9. Run Unit Test Validation Only")
        print("10. Return to Main Menu")
        print("----------------------------------------")
        choice = input("Select an option (1-10): ")
        if choice == '10':
            break
        if choice in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            path_input = input("\nEnter the path to the codebase: ").strip()
            if not path_input: 
                continue
            
            codebase = Path(path_input).resolve()
            codebase_name = codebase.name

            if not codebase.exists():
                print(f"Error: Path '{codebase}' does not exist.")
                time.sleep(2)
                continue

            rules_path = str(Path(output_dir) / "agent" / "file_summary_agent_output" / codebase_name / "business_rules" / "business_rules.json")
            validated_rules_path = str(Path(output_dir) / "agent" / "BR_agent_output" / codebase_name / "validated_rules.json")
            dir_path = Path(output_dir) / "agent" / "file_summary_agent_output" / codebase_name

            if choice == '1':
                print(f"[DEBUG] sys.argv: {sys.argv}", flush=True)
                print(f"[DEBUG] os.getcwd(): {os.getcwd()}", flush=True)
                print(f"[DEBUG] APP_DIR: {APP_DIR}", flush=True)
                print(f"[DEBUG] output_dir: {output_dir}", flush=True)
                if run_step("Code Vectorization", "src.build_database", [str(codebase)], errors):
                    if run_step("File Summary Generation", "agent.file_summary_agent", [str(codebase)], errors):
                        if run_step("Summary Vectorization", "src.build_database_JSON", [codebase_name], errors):
                            if run_step("Directory Summary Generation", "agent.directory_agent", [str(codebase)], errors):
                                if run_step("Business Rule Validation", "agent.BR_agent", [codebase_name, rules_path], errors):
                                    if uml_generation(dir_path, errors):
                                        if run_step("Unit Test Generation", "agent.UT_agent", [codebase, validated_rules_path, []], errors):
                                            #if run_step("Unit Test Validation", "agent.UTV_agent", [codebase, validated_rules_path], errors):
                                            print("\nFull pipeline completed successfully!")
                input("\nPress enter to return to menu...")

            elif choice == '2':
                run_step("Code Vectorization", "src.build_database", [str(codebase)], errors)
                input("\nTask finished. Press enter...")

            elif choice == '3':
                run_step("Summary Generation", "agent.file_summary_agent", [str(codebase)], errors)
                input("\nTask finished. Press enter...")

            elif choice == '4':
                run_step("Summary Vectorization", "src.build_database_JSON", [codebase_name], errors)
                input("\nTask finished. Press enter...")

            elif choice == '5':
                run_step("Directory Summary Generation", "agent.directory_agent", [str(codebase)], errors)
                input("\nTask finished. Press enter...")

            elif choice == '6':
                if not Path(rules_path).exists():
                    print(f"Error: Business rules file not found at '{rules_path}'.")
                    print("Please run 'Create JSON Summaries' first to generate business rules.")
                    input("\nPress enter to return to menu...")
                    continue
                run_step("Business Rule Validation", "agent.BR_agent", [codebase_name, rules_path], errors)
                input("\nTask finished. Press enter...")

            elif choice == '7':
                if not Path(dir_path).exists():
                    print(f"Error: Summary files not found at '{dir_path}'.")
                    print("Please run 'Create JSON Summaries' first to generate summaries.")
                    input("\nPress enter to return to menu...")
                    continue
                uml_generation(dir_path, errors)
                input("\nTask finished. Press enter...")

            elif choice == '8':
                if not Path(validated_rules_path).exists():
                    print(f"Error: Validated rules file not found at '{validated_rules_path}'.")
                    print("Please run 'Business Rule Validation' first to generate validated rules.")
                    input("\nPress enter to return to menu...")
                    continue
                input_ids = select_rules(validated_rules_path)
                run_step("Unit Test Generation", "agent.UT_agent", [codebase, validated_rules_path, input_ids], errors)
                input("\nTask finished. Press enter...")

            elif choice == '9':
                if not Path(validated_rules_path).exists():
                    print(f"Error: Validated rules file not found at '{validated_rules_path}'.")
                    print("Please run 'Business Rule Validation' first to generate validated rules.")
                    input("\nPress enter to return to menu...")
                    continue
                run_step("Unit Test Validation", "agent.UTV_agent", [codebase, validated_rules_path], errors)
                input("\nTask finished. Press enter...")

            
def view_collections(db_type: str):
    """
    @brief Displays existing collections and allows the user to preview their contents.
    @details Connects to the ChromaDB persistent client, filters collections 
    based on the specified database type, and renders a formatted preview of 
    the metadata and documents stored within.
    @param db_type The type of database to view; expected values are 'summary' or 'source'.
    @return None
    """
    clear_screen()
    db_dir = Path(output_dir) / "vectorStores"
    if not db_dir.exists():
        print("No vector stores found. Please generate summaries first.")
        input("Press enter to return to main menu...")
        return
    
    # initialize client
    client = chromadb.PersistentClient(path = str(db_dir))
    collections = client.list_collections()
    
    # get suffix based on db type
    suffix = "_summary_db" if db_type == "summary" else "_code_db"

    # get relevant collections
    relevant = [col for col in collections if col.name.endswith(suffix)]

    if not relevant:
        print(f"No {db_type} collections found. Please generate summaries first.")
        input("Press enter to return to main menu...")
        return
    
    print(f"--- Available {db_type.capitalize()} Collections ---")
    for i, col in enumerate(relevant):
        print(f"{i+1}. {col.name}")
        
    choice = input(f"\nSelect a number to preview (or 'b' to go back): ")
    if choice.lower() == 'b':
        return
    if choice.isdigit() and int(choice) <= len(relevant):
        target = relevant[int(choice)-1]
        results = target.peek(limit=5) # Preview 5 items
        
        print(f"\n{'='*60}")
        print(f"PREVIEWING: {target.name}")
        print(f"{'='*60}")

        for i in range(len(results['ids'])):
            meta = results['metadatas'][i]
            doc = results['documents'][i]
            
            if db_type == "code":
                # Layout for Source Code DB
                print(f"\n[ENTRY {i+1}] {meta.get('name', 'N/A')}")
                print(f"  File: {meta.get('file')}")
                print(f"  Namespace: {meta.get('namespace')}")
                print(f"  Lines: {meta.get('start_line')} - {meta.get('end_line')}")
                print(f"  Type: {meta.get('type')}")
                print(f"  Preview:\n    {doc.split('Code: ')[-1][:150].strip()}...")

            else:
                # Layout for Summary DB
                entry_type = meta.get('type', 'Unknown').upper()
                name = meta.get('name', meta.get('path'))
                print(f"\n[{entry_type}] {name}")
                if meta.get('parent'):
                    print(f"  Parent Class: {meta.get('parent')}")
                print(f"  Path: {meta.get('path')}")
                
                # Strip out the redundant labels for a cleaner description
                clean_doc = doc.replace(f"File Path: {meta.get('path')}", "").strip()
                print(f"  Summary: {clean_doc[:200]}...")

            print(f"{'-'*30}")
        
    input("\nPress Enter to return to menu...")

def main_menu():
    """
    @brief Main execution loop for the CLI.
    @details Displays the primary menu and routes user input to the 
    corresponding orchestration or viewing functions.
    @return None
    """
    errors = []
    while True:
        clear_screen()
        print("========================================")
        print("   CODEBASE ANALYSIS SYSTEM - CLI")
        print("========================================")
        print("1. Run Analysis Tools")
        print("2. Enter API Key")
        print("3. View Summary Collections")
        print("4. View Source Code Collections")
        print("5. View Errors")
        print("6. Exit")
        print("----------------------------------------")
        
        choice = input("Select an option (1-6): ")

        if choice == '1':
            processing_menu(errors)
        elif choice == '2':
            get_api()
        elif choice == '3':
            view_collections(db_type="summary")
        elif choice == '4':
            view_collections(db_type="code")
        elif choice == '5':
            clear_screen()
            print("--- ERROR LOG ---")
            if errors:
                for i, err in enumerate(errors):
                    print(f"\n[ERROR {i+1}]:\n{err}\n{'-'*40}")
            else:
                print("No errors recorded.")
            input("\nPress enter to return to menu...")
        elif choice == '6':
            print("Exiting system. Goodbye!")
            sys.exit()
        else:
            print("Invalid selection. Try again.")

if __name__ == "__main__":
    main_menu()