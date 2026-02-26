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

def create_summaries():
    """
    @brief Orchestrates the full codebase analysis pipeline.
    @details Executes three primary sub-processes in sequence:
    1. Source code vectorization (src.build_database).
    2. LLM-based summary generation (agent.file_summary_agent).
    3. Summary vectorization (src.build_database_JSON).
    @return None
    """
    clear_screen()
    codebase = Path(input("\nEnter the path to the codebase to analyze: ").strip()).resolve()
    codebase_name = codebase.name

    start_time = time.perf_counter()

    # get relative path to target codebase from targetCodebases directory


    print("Building vector database...")
    subprocess.run([sys.executable, "-m", "src.build_database", str(codebase)], text=True)

    code_vectorization_time = time.perf_counter() - start_time
    print(f"\nCode vectorization completed in {code_vectorization_time:.2f} seconds.\n")
    
    print("Generating summaries...")
    subprocess.run([sys.executable, "-m", "agent.file_summary_agent", str(codebase)], text=True)

    code_summary_time = time.perf_counter() - start_time - code_vectorization_time
    print(f"\nSummary generation completed in {code_summary_time:.2f} seconds.\n")

    print("Building summary database...")
    subprocess.run([sys.executable, "-m", "src.build_database_JSON", codebase_name], text=True)

    summary_vectorization_time = time.perf_counter() - start_time - code_vectorization_time - code_summary_time
    print(f"\nSummary vectorization completed in {summary_vectorization_time:.2f} seconds.\n")

    print("Summaries generated successfully!")
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    print(f"Total execution time: {elapsed/60:.2f} minutes.")
    input("Press enter to return to main menu...")

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
            
            if db_type == "source":
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
    while True:
        clear_screen()
        print("========================================")
        print("   CODEBASE ANALYSIS SYSTEM - CLI")
        print("========================================")
        print("1. Create Summaries & Index Codebase")
        print("2. View Summary Collections")
        print("3. View Source Code Collections")
        print("4. Exit")
        print("----------------------------------------")
        
        choice = input("Select an option (1-4): ")

        if choice == '1':
            create_summaries()
        elif choice == '2':
            view_collections(db_type="summary")
        elif choice == '3':
            view_collections(db_type="source")
        elif choice == '4':
            print("Exiting system. Goodbye!")
            sys.exit()
        else:
            print("Invalid selection. Try again.")

if __name__ == "__main__":
    main_menu()