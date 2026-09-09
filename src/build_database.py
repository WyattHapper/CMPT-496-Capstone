"""
@file build_database.py
@brief Core script for indexing a codebase into a ChromaDB vector store.
"""
import logging
logger = logging.getLogger(__name__)
import chromadb
import sys
from pathlib import Path
from utils.tree_parse import *
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from backend.progress_logging import progress

def build_database(source_path: str) -> None:
    """
    @brief Assembles a local ChromaDB database from a directory of source files.
    
    This function performs the ETL (Extract, Transform, Load) process for the codebase:
    1. **Extract**: Parses the directory into code bundles.
    2. **Transform**: Chunks code by class/method and formats it into searchable strings.
    3. **Load**: Embeds the text and upserts it into a persistent ChromaDB collection.

    @param source_path The relative path to the directory containing the source code to index.
    
    @return None
    
    @note The database is stored in a directory named 'vectorStores' at the project root.
    """
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent

    source_dir = (base_dir / source_path).resolve()
    db_dir = (base_dir / "vectorStores").resolve()
    db_name = f"{source_dir.name}_code_db"

    progress(
        f"Preparing codebase indexing: {source_dir.name}",
        percent=5
    )

    # Create the vectoreStores directory if it doesn't exist
    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)

    progress(
        "Loading embedding model...",
        percent=15
    )

    embedding = SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    progress(
        "Embedding model loaded",
        percent=25
    )
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=str(db_dir))
    logger.info(f"\n--- Building Collection: {db_name} ---")

    # Create or get the collection
    collection = client.get_or_create_collection(name=db_name, embedding_function = embedding)

    progress(
        "Initialized vector database collection",
        percent=30
    )

    progress(
        "Parsing source files...",
        percent=35
    )

    bundles = parse_dir(str(source_dir))

    progress(
        f"Parsed {len(bundles)} source bundles",
        percent=45
    )

    # track id's, embeddings, and metadata for upsert
    ids = []
    embeddings = []
    metadatas = []

    progress(
        "Extracting code chunks and metadata...",
        percent=50
    )

    for bundle in bundles:
        chunks = get_chunks(bundle)
        for i, chunk in enumerate(chunks):
            # Create unique ID for the chunk
            unique_id = f"{chunk['file']}_{chunk['container']}_{chunk['name']}_{i}"

            # Create string for embedder
            embedded_string = f"Namespace: {chunk['namespace']}\nContainer: {chunk['container']}\nType: {chunk['type']}\nCode: {chunk['code']}"

            # Prepare metadata
            metadata = {
                "name": chunk["name"],
                "container": chunk["container"],
                "file": chunk["file"],
                "type": chunk["type"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "namespace": chunk["namespace"],
                "language": chunk["language"],
                "imports": chunk["imports"] 
            }

            # append to lists for batch upsert
            ids.append(unique_id)
            embeddings.append(embedded_string)
            metadatas.append(metadata)


    progress(
        f"Prepared {len(ids)} code chunks for indexing",
        percent=70
    )

    # Verification before upsert
    if not (len(ids) == len(embeddings) == len(metadatas)):
        logger.critical(f"CRITICAL ERROR: Data mismatch! IDs: {len(ids)}, Docs: {len(embeddings)}, Meta: {len(metadatas)}")
        sys.exit(1)

    if not ids:
        logger.info("No valid chunks were generated. Aborting upsert.")
        sys.exit(1)


    progress(
        "Storing embeddings in vector database...",
        percent=75
    )
    # batch upsert chunks
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end_index = min(i+batch_size, len(ids))
        collection.upsert(ids=ids[i:end_index], 
                            documents=embeddings[i:end_index], 
                            metadatas=metadatas[i:end_index])
    
    progress(
        f"Finished indexing {len(ids)} items",
        percent=100,
        step_complete=True
    )

    logger.info(
        f"Finished indexing {len(ids)} unique items for {db_name}"
    )


if __name__ == "__main__":
    """
    @brief Standard entry point logic.
    Validates command-line arguments and ensures the target source directory exists.
    """
    if len(sys.argv) != 2:
        logger.info("Usage: python -m src.build_database <source_directory>\nNote: Please execute from CMPT-496-Capstone directory.")
        sys.exit(1)
    source_path = sys.argv[1]

    # check if source path exists and is a directory
    if not Path(source_path).exists() or not Path(source_path).is_dir():
        logger.error(f"Error: {source_path} does not exist or is not a directory.")
        sys.exit(1)

    build_database(source_path)