"""
Structure-Aware Document Chunker
─────────────────────────────────
Splits documents along semantic boundaries (markdown headers, procedures,
numbered steps, and paragraphs) while preserving section hierarchy and context.
"""

from __future__ import annotations

import re
from typing import Any
from app.services.rag.interfaces.chunker import ChunkOutput, DocumentChunker


class StructureAwareChunker(DocumentChunker):
    """Chunks documents preserving headings, procedural lists, and structural context."""

    def chunk_document(
        self,
        raw_text: str,
        document_title: str,
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[ChunkOutput]:
        meta = dict(metadata or {})
        lines = raw_text.splitlines()

        sections: list[tuple[str, list[str]]] = []
        current_heading = document_title
        current_lines: list[str] = []

        header_regex = re.compile(r"^(#{1,4}\s+.*|[A-Z\s]{4,}:|Section\s+\d+:?|Procedure\s+\d+:?)", re.IGNORECASE)

        for line in lines:
            stripped = line.strip()
            if header_regex.match(stripped):
                if current_lines:
                    sections.append((current_heading, current_lines))
                    current_lines = []
                current_heading = stripped.lstrip("#").strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, current_lines))

        chunks: list[ChunkOutput] = []
        chunk_idx = 0

        for heading, s_lines in sections:
            section_text = "\n".join(s_lines).strip()
            if not section_text:
                continue

            words = section_text.split()
            if len(words) <= chunk_size:
                formatted_content = f"[{document_title} > {heading}]\n{section_text}"
                chunks.append(
                    ChunkOutput(
                        chunk_index=chunk_idx,
                        title=heading,
                        content=formatted_content,
                        token_count=len(words),
                        metadata={**meta, "section_heading": heading, "document_title": document_title},
                    )
                )
                chunk_idx += 1
            else:
                # Sliding window split across word boundaries
                step = max(50, chunk_size - chunk_overlap)
                for start in range(0, len(words), step):
                    window_words = words[start : start + chunk_size]
                    sub_text = " ".join(window_words)
                    formatted_content = f"[{document_title} > {heading} (part)]\n{sub_text}"
                    chunks.append(
                        ChunkOutput(
                            chunk_index=chunk_idx,
                            title=f"{heading} (part)",
                            content=formatted_content,
                            token_count=len(window_words),
                            metadata={**meta, "section_heading": heading, "document_title": document_title},
                        )
                    )
                    chunk_idx += 1

        return chunks
