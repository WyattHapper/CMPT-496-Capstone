"""
@file test_vector_store_wrapper.py
@brief Unit test for the ChromaManager wrapper class to ensure it can connect to the persistent ChromaDB and perform similarity search
"""

# Ensure project root is on `sys.path` when running this test directly
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from utils.vector_store_wrapper import ChromaManager

def test_chroma_manager():
    """
    @brief Tests the ChromaManager's ability to connect to the ChromaDB and perform a similarity search.
    
    This test will:
    1. Initialize the ChromaManager with the path to the persistent database and collection name.
    2. Perform a similarity search with a sample query.
    3. Print the results for verification.
    """
    # Absolute path verification
    db_path = "./vectorStores" 
    collection_name = "ConsoleTables_db"

    try:
        manager = ChromaManager(db_path=db_path, collection_name=collection_name)
        query = "What kind of data can ConsoleTables print?"
        results = manager.similarity_search(query=query, k=3)

        print(f"\nQuery: {query}")
        for i, doc in enumerate(results):
            print(f"\nResult {i+1}: {doc}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_chroma_manager()