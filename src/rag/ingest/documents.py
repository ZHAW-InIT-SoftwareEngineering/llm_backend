from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


def create_documents(path: Path) -> list[Document]:
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    return [
        Document(
            page_content=block["html"],
            metadata={
                "source": str(path),
                "block_id": block.get("id"),
                "block_type": block.get("block_type"),
                "page": block.get("page"),
                "section_hierarchy": block.get("section_hierarchy"),
            },
        )
        for block in data["blocks"]
        if block.get("html")
    ]


def create_embeddings(
    model_name: str = "sentence-transformers/all-mpnet-base-v2",
) -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": True},
    )


def main(paths: list) -> None:
    for path in paths: 
        create_documents(path)


if __name__ == "__main__":
    PDF_PATHS = [
        Path("docs/rag/chunks/shortest_paths_theory_notes.chunks.json"),
        Path("docs/rag/chunks/domain_specific_language_theory.chunks.json"),
    ]
    
    main(PDF_PATHS)
    