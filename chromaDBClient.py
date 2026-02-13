import chromadb

client = chromadb.PersistentClient(path="./my_chroma_data")

# everything below is sample data that i was messing around with to see if i was actually able to add and query the database
# was able to add unembedded info and query it using chromaDB

collection = client.get_or_create_collection("test_collection")

collection.add(
    documents=["Hello world"],
    ids=["id1"]
)

results = collection.query(
    query_texts=["Hello"],
    n_results=1
)

print(results)
