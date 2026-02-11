"""
File: tree_parse_test.py
Purpose: Library for testing tree_parse.py
"""
from tree_parse import *

def test_parse():
    """
    :test_parse function: does a test parse on ConsoleTables
    :return: None
    :post: prints out information on parsed files

    :NOTE: directory path may be different as targetCodebases is an ignored directory.
           Additionally, pathway must either be an absolute path or relative to pwd of
           the terminal.
    """
    # Create bundles
    bundles = parse_dir("./targetCodebases/consoleTables/ConsoleTables")

    # print out information on bundles
    for i, bundle in enumerate(bundles):
        root=bundle.tree.root_node
        kb_size = len(bundle.content) / 1024
        print(f"File {i+1}: {bundle.path.name}")
        print(f"  - Full Path: {bundle.path}")
        print(f"  - Size:      {kb_size:.2f} KB")
        print(f"  - AST Root:  {root.type}")
        print(f"  - Children:  {root.child_count} top-level nodes")
        
        # Peek at the first 50 characters of the code
        # We decode only a slice for the preview
        preview = bundle.content[:50].decode('utf-8', errors='ignore').replace('\n', ' ')
        print(f"  - Preview:   {preview}...")
        print("-" * 30)

    # Show total number of tree's made
    print(f"\nTotal bundles verified: {len(bundles)}")

# Main entry point
if __name__ == "__main__":
    test_parse()