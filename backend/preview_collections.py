"""
backend/preview_collections.py

Utilities for inspecting ChromaDB collections.

This module replaces the CLI-only view_collections()
function from main.py.
"""

from pathlib import Path

import chromadb


if getattr(__import__("sys"), "frozen", False):
    APP_DIR = Path(__import__("sys").executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent



class CollectionPreview:
    """
    Provides collection discovery and preview operations.
    """


    def __init__(self):
        self.db_dir = APP_DIR / "vectorStores"


    def _get_client(self):
        """
        Create ChromaDB persistent client.
        """

        if not self.db_dir.exists():
            raise FileNotFoundError(
                f"Vector store directory not found: {self.db_dir}"
            )


        return chromadb.PersistentClient(
            path=str(self.db_dir)
        )


    def list_collections(self, db_type: str):
        """
        Return available collections.

        db_type:
            summary
            code
        """

        client = self._get_client()


        suffix = (
            "_summary_db"
            if db_type == "summary"
            else "_code_db"
        )


        collections = [
            collection.name
            for collection in client.list_collections()
            if collection.name.endswith(suffix)
        ]


        return {
            "success": True,
            "type": db_type,
            "collections": collections
        }



    def preview_collection(
        self,
        collection_name: str,
        limit: int = 5
    ):
        """
        Preview entries from one collection.
        """

        client = self._get_client()


        collections = client.list_collections()


        target = None

        for collection in collections:
            if collection.name == collection_name:
                target = collection
                break


        if target is None:
            return {
                "success": False,
                "error": (
                    f"Collection not found: "
                    f"{collection_name}"
                )
            }



        results = target.peek(
            limit=limit
        )


        entries = []


        for i in range(len(results["ids"])):

            metadata = results["metadatas"][i]

            document = results["documents"][i]


            entries.append({

                "id":
                    results["ids"][i],

                "metadata":
                    metadata,

                "document":
                    document

            })


        return {
            "success": True,

            "collection":
                collection_name,

            "entries":
                entries
        }



    def preview_collections(
        self,
        db_type: str,
        limit: int = 5
    ):
        """
        Convenience method.

        Returns all matching collections
        and their previews.
        """

        available = self.list_collections(
            db_type
        )


        if not available["success"]:
            return available


        output = []


        for name in available["collections"]:

            output.append(
                self.preview_collection(
                    name,
                    limit
                )
            )


        return {
            "success": True,

            "type":
                db_type,

            "collections":
                output
        }