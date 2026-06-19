from __future__ import annotations

import json
from pathlib import Path

from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict


PDF_PATHS = [
    Path("docs/rag/shortest_path/shortest_paths_theory_notes.pdf"),
    Path("docs/rag/dsl/domain_specific_language_theory.pdf"),
]

OUTPUT_DIR = Path("docs/rag/chunks")

# Marker's OCR-only converter emits OCR JSON, not RAG chunks. For chunk output
# with better inline math handling, force OCR on the PDF converter instead.
MARKER_CONFIG = {
    "output_format": "chunks",
    "force_ocr": True,
    "disable_image_extraction": True,
}


def build_converter() -> PdfConverter:
    config_parser = ConfigParser(MARKER_CONFIG)
    return PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service(),
    )


def write_chunks(converter: PdfConverter, pdf_path: Path) -> Path:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")

    rendered = converter(str(pdf_path))
    output_path = OUTPUT_DIR / f"{pdf_path.stem}.chunks.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(rendered.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    return output_path


def main() -> None:
    converter = build_converter()

    for pdf_path in PDF_PATHS:
        output_path = write_chunks(converter, pdf_path)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
