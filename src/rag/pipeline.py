from pathlib import Path

from src.rag.ingest.chunks import OUTPUT_DIR, build_converter, write_chunks
from src.rag.ingest.documents import create_documents
from src.rag.vectorstore.embedding_model import get_embedding_model
from src.rag.vectorstore.qdrant import COLLECTION_NAME, store_documents


PDF_PATHS = [
    Path("docs/rag/shortest_path/shortest_paths_theory_notes.pdf"),
    Path("docs/rag/dsl/domain_specific_language_theory.pdf"),
]


def run_pipeline(paths: list[Path]) -> None:
    converter = build_converter()
    chunk_paths = []

    for path in paths:
        chunk_path = write_chunks(converter, path, OUTPUT_DIR)
        chunk_paths.append(chunk_path)
        print(f"Wrote {chunk_path}")

    documents = []

    for path in chunk_paths:
        new_documents = create_documents(path)
        documents.extend(new_documents)
        print(f"Created {len(new_documents)} documents from {path}")

    embedding_model = get_embedding_model()
    store_documents(embedding_model, documents)
    print(f"Stored {len(documents)} documents in {COLLECTION_NAME}")


def main(paths: list[Path]) -> None:
    run_pipeline(paths)


if __name__ == "__main__":
    main(PDF_PATHS)
