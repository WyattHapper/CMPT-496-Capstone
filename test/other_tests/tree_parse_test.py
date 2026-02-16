"""!
@file tree_parse_test.py
@brief Library for testing tree_parse.py
@details This script provides utility functions to verify the AST parsing 
capabilities of the tree_parse module using sample codebases.
"""

from utils.tree_parse import *

def test_parse():
    """!
    @brief Performs a test parse on ConsoleTables.
    @details Creates file bundles from a target directory and prints AST 
    metadata including file size, root node type, and child counts.
    
    @return None
    @post Prints detailed information on parsed files to the standard output.

    @note The directory path may be different as targetCodebases is an ignored 
    directory. Additionally, pathway must either be an absolute path or 
    relative to the pwd of the terminal.
    """
    # Create bundles
    bundles = parse_dir("./targetCodebases/consoleTables/ConsoleTables")

    # Print out information on bundles
    for i, bundle in enumerate(bundles):
        root = bundle.tree.root_node
        kb_size = len(bundle.content) / 1024
        print(f"File {i+1}: {bundle.path.name}")
        print(f"  - Full Path: {bundle.path}")
        print(f"  - Size:      {kb_size:.2f} KB")
        print(f"  - AST Root:  {root.type}")
        print(f"  - Children:  {root.child_count} top-level nodes")
        
        # Peek at the first 100 characters of the code
        # We decode only a slice for the preview
        preview = bundle.content[:100].decode('utf-8', errors='ignore').replace('\n', ' ')
        print(f"  - Preview:   {preview}...")
        print("-" * 30)

    # Show total number of trees made
    print(f"\nTotal bundles verified: {len(bundles)}")

def test_chunk():
    """!
    @brief Performs a test chunking on the ConsoleTables codebase.
    @details Iterates through all parsed bundles, extracts semantic chunks 
    (methods, constructors, properties), and prints their associated metadata 
    including class name, line range, and language.

    @return None
    @post Outputs structured chunk data to the console for verification.

    @note The directory path may be different as targetCodebases is an ignored 
    directory. Additionally, pathway must either be an absolute path or 
    relative to the pwd of the terminal.
    """
    bundles = parse_dir("./targetCodebases/humanizer/Humanizer")
    for bundle in bundles:
        chunks = get_chunks(bundle)
        for chunk in chunks:
            print(f"CHUNK:\t{chunk['name']} ({chunk['type']}) in class {chunk['class']}")
            print(f"LINES:\t{chunk['start_line']} - {chunk['end_line']}")
            print(f"FILE:\t{chunk['file']}")
            print(f"LANG:\t{chunk['language']}")
            print(f"NAMES:\t{chunk['namespace']}")
            print(f"IMPORT:\t{chunk['imports']}")
            # Extract first line for a clean console preview
            first_line = chunk['code'].strip().splitlines()[0]
            print(f"CODE:\t{first_line} ...")
            print("-"*30)      
    return

# Main entry point
if __name__ == "__main__":
    test_chunk()