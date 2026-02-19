"""
@file test_chroma_retrieval.py
@brief Unit test to verify similarity search and top-k retrieval from ChromaDB.
@details This script validates that the vector store can successfully perform 
         semantic search using the SentenceTransformer embedding function.
"""
import chromadb
from pathlib import Path
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

def test_top_k():
    """
    @brief Executes a similarity search against the Humanizer_db collection.
    
    This test verifies the end-to-end retrieval pipeline:
    1. Locates the persistent database on disk.
    2. Initializes the MiniLM-L6-v2 embedding model.
    3. Performs a nearest-neighbor search for a sample natural language query.
    4. Outputs the top 5 most relevant code chunks.
    """
    embedding = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
    # Absolute path verification
    db_path = (Path(__file__).parent.parent.parent / "vectorStores").resolve()

    client = chromadb.PersistentClient(path=str(db_path))

    # Target Humanizer_db collection for testing
    target_name = "Humanizer_db"

    collection = client.get_collection(name=target_name, embedding_function=embedding)
    
    # Crete random query to test top-k retrieval
    query = "How does Humanizer round times?"
    results = collection.query(query_texts=[query], n_results=5)

    print(f"\nQuery: {query}")
    for i, doc in enumerate(results['documents'][0]):
        print(f"\nResult {i+1}: {doc}")

if __name__ == "__main__":
    """
    @brief Entry point for the retrieval test.
    """
    test_top_k()