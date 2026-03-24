"""
@file main.py
@brief Central CLI entry point for the Codebase Analysis project.
@details Provides a menu-driven interface to orchestrate the end-to-end 
summarization pipeline, manage vector databases, and preview indexed source 
code and summaries.
"""

import os
import subprocess
import sys
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
    """
    @brief Executes a subprocess for a given step in the pipeline.
    """
    print(f"Running step: {step_name}...")
    start = time.perf_counter()
    try:
        # result.returncode is 0 if success, something else if it crashed
        result = subprocess.run([sys.executable, "-m", module] + args, text=True)
        
        if result.returncode != 0:
            err_msg = f"{step_name} failed with exit code {result.returncode}."
            print(f"\n[!] {err_msg}")
            errors.append(err_msg)
            return False

        elapsed = time.perf_counter() - start
        print(f"{step_name} completed in {elapsed:.2f} seconds.")
        return True

    except Exception as e:
        err_msg = f"Failed to launch {step_name}: {e}"
        print(f"\n[!] {err_msg}")
        errors.append(err_msg)
        return False

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
        print("6. Return to Main Menu")
        print("----------------------------------------")
        choice = input("Select an option (1-6): ")
        if choice == '6':
            break
        if choice in ['1', '2', '3', '4', '5']:
            path_input = input("\nEnter the path to the codebase: ").strip()
            if not path_input: 
                continue
            
            codebase = Path(path_input).resolve()
            codebase_name = codebase.name

            if not codebase.exists():
                print(f"Error: Path '{codebase}' does not exist.")
                time.sleep(2)
                continue

            if choice == '1':
                if run_step("Code Vectorization", "src.build_database", [str(codebase)], errors):
                    if run_step("File Summary Generation", "agent.file_summary_agent", [str(codebase)], errors):
                        if run_step("Summary Vectorization", "src.build_database_JSON", [codebase_name], errors):
                            if run_step("Directory Summary Generation", "agent.directory_agent", [str(codebase)], errors):
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
    db_dir = Path("vectorStores").resolve()
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
        print("1. Create Summaries & Index Codebase")
        print("2. View Summary Collections")
        print("3. View Source Code Collections")
        print("4. View Errors")
        print("5. Exit")
        print("----------------------------------------")
        
        choice = input("Select an option (1-5): ")

        if choice == '1':
            processing_menu(errors)
        elif choice == '2':
            view_collections(db_type="summary")
        elif choice == '3':
            view_collections(db_type="code")
        elif choice == '4':
            clear_screen()
            print("--- ERROR LOG ---")
            if errors:
                for i, err in enumerate(errors):
                    print(f"\n[ERROR {i+1}]:\n{err}\n{'-'*40}")
            else:
                print("No errors recorded.")
            input("\nPress enter to return to menu...")
        elif choice == '5':
            print("Exiting system. Goodbye!")
            sys.exit()
        else:
            print("Invalid selection. Try again.")

if __name__ == "__main__":
    main_menu()