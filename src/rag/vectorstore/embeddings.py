from langchain_huggingface import HuggingFaceEmbeddings
from pathlib import Path


MODEL_NAME: str = "sentence-transformers/all-mpnet-base-v2",

def create_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )


def main(paths: list) -> None:
    for path in paths: 
        create_embeddings(path)


if __name__ == "__main__":
    CHUNK_PATHS = [
        Path("docs/rag/chunks/shortest_paths_theory_notes.chunks.json"),
        Path("docs/rag/chunks/domain_specific_language_theory.chunks.json"),
    ]
    
    main(CHUNK_PATHS)