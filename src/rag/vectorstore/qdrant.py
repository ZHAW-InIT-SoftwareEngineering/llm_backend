import os
from pathlib import Path

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from src.rag.ingest.documents import create_documents
from src.rag.vectorstore.embedding_model import get_embedding_model


COLLECTION_NAME = "DemoObject_LLM"
QDRANT_URL = os.getenv("QDRANT_URL")

client = QdrantClient(url=QDRANT_URL) if QDRANT_URL else QdrantClient(":memory:")


def store_documents(
    embedding_model: HuggingFaceEmbeddings,
    documents: list[Document],
) -> QdrantVectorStore:
    if not documents:
        raise ValueError("No documents to store")

    vector_size = len(embedding_model.embed_query(documents[0].page_content))

    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embedding_model,
    )

    vector_store.add_documents(documents=documents)
    return vector_store


def main(paths: list[Path]) -> None:
    embedding_model = get_embedding_model()
    documents = []

    for path in paths:
        documents.extend(create_documents(path))

    store_documents(embedding_model, documents)
    print(f"Stored {len(documents)} documents in {COLLECTION_NAME}")


if __name__ == "__main__":
    CHUNK_PATHS = [
        Path("docs/rag/chunks/shortest_paths_theory_notes.chunks.json"),
        Path("docs/rag/chunks/domain_specific_language_theory.chunks.json"),
    ]

    main(CHUNK_PATHS)
