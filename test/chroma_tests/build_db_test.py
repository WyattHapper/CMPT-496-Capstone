"""
@file inspect_chromadb_with_vectors.py
@brief Diagnostic utility to inspect ChromaDB collections and vector data.

@note This script is AI generated and is only inteded for debugging and 
verification purposes.
"""

import sys
from pathlib import Path
import chromadb
import numpy as np

def inspect_database(db_path: str, sample_count: int = 10, vector_preview: int = 10):
    """
    @brief Scans a local ChromaDB instance and prints a summary of its content.
    
    This function connects to a persistent ChromaDB client, lists all available 
    collections, and retrieves a sample of documents, metadata, and embeddings 
    for visual verification.

    @param db_path        The filesystem path to the directory containing the vector store.
    @param sample_count   The number of records to display per collection. Defaults to 3.
    @param vector_preview The number of dimensions to show for each vector. Defaults to 10.

    @note If no embeddings are found in the collection, the script will report 
          "<not stored or not included>".
    """
    db_path = Path(db_path).resolve()
    if not db_path.exists() or not db_path.is_dir():
        print(f"Error: {db_path} does not exist or is not a directory.")
        return

    client = chromadb.PersistentClient(path=str(db_path))
    collections = client.list_collections()

    if not collections:
        print("No collections found in database.")
        return

    for col_info in collections:
        collection = client.get_collection(col_info.name)
        
        # We explicitly request 'embeddings' to ensure they are fetched from storage
        data = collection.get(include=['documents', 'metadatas', 'embeddings'])
        ids = data['ids']
        docs = data['documents']
        metadatas = data['metadatas']
        embeddings = data.get('embeddings', None)

        print(f"\n=== Collection: {col_info.name} ===")
        print(f"Total chunks: {len(ids)}")
        print(f"Sample of first {min(sample_count, len(ids))} entries:")

        for i in range(min(sample_count, len(ids))):
            print(f"\nID: {ids[i]}")
            # Truncate document text for cleaner console output
            print(f"Document: {docs[i][:100]}{'...' if len(docs[i]) > 100 else ''}")
            print(f"Metadata: {metadatas[i]}")

            if embeddings is not None:
                vec = np.array(embeddings[i])
                print(f"Vector (first {vector_preview} dims): {vec[:vector_preview]}")
                print(f"Vector shape: {vec.shape}, min: {vec.min():.4f}, max: {vec.max():.4f}, mean: {vec.mean():.4f}")
            else:
                print("Vector: <not stored or not included>")

if __name__ == "__main__":
    """
    @brief Main entry point for the script.
    
    Expects one command line argument representing the database path.
    """
    if len(sys.argv) != 2:
        print("Usage: python build_db_test.py <path_to_vectorStores>")
        sys.exit(1)

    db_path = sys.argv[1]
    inspect_database(db_path)