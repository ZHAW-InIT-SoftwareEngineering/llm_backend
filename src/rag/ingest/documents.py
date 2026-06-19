from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


def create_documents(path: Path) -> list[Document]:
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    documents = []

    for block in data["blocks"]:
        if not block.get("html"):
            continue

        document = Document(
            page_content=block["html"],
            metadata={
                "source": str(path),
                "block_id": block.get("id"),
                "block_type": block.get("block_type"),
                "page": block.get("page"),
                "section_hierarchy": block.get("section_hierarchy"),
            },
        )

        documents.append(document)

    return documents


def main(paths: list[Path]) -> None:
    for path in paths:
        documents = create_documents(path)
        print(f"Created {len(documents)} documents from {path}")


if __name__ == "__main__":
    CHUNK_PATHS = [
        Path("docs/rag/chunks/shortest_paths_theory_notes.chunks.json"),
        # Path("docs/rag/chunks/domain_specific_language_theory.chunks.json"),
    ]

    main(CHUNK_PATHS)
