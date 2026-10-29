"""Voice-Optimized Document Chunker.

Transforms documents (Markdown, TXT) into conversational speech chunks:
- Strips markdown tables, bullets, and asterisks into spoken declarative sentences.
- Chunks strictly along sentence boundaries (150-220 tokens).
- Applies acoustic overlap to preserve conversational context across chunk seams.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Approximate conversion: 1 token ~ 4 characters in English
DEFAULT_CHUNK_TOKENS = 180
DEFAULT_OVERLAP_TOKENS = 30
CHARS_PER_TOKEN = 4


@dataclass
class DocumentChunk:
    """A granular document chunk optimized for conversational voice retrieval."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    @property
    def token_count(self) -> int:
        return max(1, len(self.text) // CHARS_PER_TOKEN)


class VoiceChunker:
    """Pre-processes text into voice-first declarative chunks."""

    def __init__(
        self,
        chunk_size_tokens: int = DEFAULT_CHUNK_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ) -> None:
        self.chunk_size_chars = chunk_size_tokens * CHARS_PER_TOKEN
        self.overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    @staticmethod
    def clean_markdown_for_speech(text: str) -> str:
        """Strips markdown syntax into natural spoken text."""
        if not text:
            return ""

        cleaned = text

        # 1. Convert markdown tables: '| Room | Price |' -> declarative line
        table_lines = []
        in_table = False
        headers = []

        output_lines = []
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                in_table = True
                cols = [c.strip() for c in stripped.strip("|").split("|")]
                # Skip divider line |---|---|
                if all(re.match(r"^:?-+:?$", c) for c in cols):
                    continue
                if not headers:
                    headers = cols
                else:
                    # Map row cells to headers
                    row_desc = []
                    for h, v in zip(headers, cols):
                        if h and v:
                            row_desc.append(f"{h} is {v}")
                    if row_desc:
                        output_lines.append(", ".join(row_desc) + ".")
            else:
                if in_table:
                    in_table = False
                    headers = []
                output_lines.append(line)

        cleaned = "\n".join(output_lines)

        # 2. Strip HTML tags
        cleaned = re.sub(r"<[^>]+>", "", cleaned)

        # 3. Strip links: [label](url) -> label
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

        # 4. Strip headings: # Title -> Title
        cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)

        # 5. Strip bold and italics: **text** -> text, *text* -> text
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
        cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
        cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)

        # 6. Convert bullet and numbered lists into declarative clauses
        cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*\d+[.)]\s+", "", cleaned, flags=re.MULTILINE)

        # 7. Collapse repeated whitespace and newlines
        cleaned = re.sub(r"\n+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def chunk_text(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        doc_name: str = "document",
    ) -> list[DocumentChunk]:
        """Splits raw text into sentence-aware, voice-ready chunks."""
        cleaned = self.clean_markdown_for_speech(text)
        if not cleaned:
            return []

        # Split along sentence boundaries: period, exclamation, question mark followed by space
        sentence_end = re.compile(r"(?<=[.!?])\s+")
        sentences = [s.strip() for s in sentence_end.split(cleaned) if s.strip()]

        chunks: list[DocumentChunk] = []
        current_sentences: list[str] = []
        current_len = 0
        chunk_idx = 0

        base_meta = metadata.copy() if metadata else {}
        base_meta.setdefault("doc_name", doc_name)
        base_meta.setdefault("created_at", datetime.now(timezone.utc).isoformat())

        for sentence in sentences:
            sentence_len = len(sentence) + 1  # +1 for space

            # If adding this sentence exceeds chunk size and we already have content
            if current_len + sentence_len > self.chunk_size_chars and current_sentences:
                chunk_str = " ".join(current_sentences).strip()
                chunk_meta = {**base_meta, "chunk_index": chunk_idx}
                chunks.append(
                    DocumentChunk(
                        id=f"{doc_name}_{chunk_idx}_{uuid.uuid4().hex[:6]}",
                        text=chunk_str,
                        metadata=chunk_meta,
                    )
                )
                chunk_idx += 1

                # Calculate overlap: retain the last sentence(s) that fit within overlap_chars
                overlap_sentences = []
                overlap_len = 0
                for s in reversed(current_sentences):
                    if overlap_len + len(s) + 1 <= self.overlap_chars:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s) + 1
                    else:
                        break

                current_sentences = overlap_sentences + [sentence]
                current_len = sum(len(s) + 1 for s in current_sentences)
            else:
                current_sentences.append(sentence)
                current_len += sentence_len

        # Append remaining sentences
        if current_sentences:
            chunk_str = " ".join(current_sentences).strip()
            chunk_meta = {**base_meta, "chunk_index": chunk_idx}
            chunks.append(
                DocumentChunk(
                    id=f"{doc_name}_{chunk_idx}_{uuid.uuid4().hex[:6]}",
                    text=chunk_str,
                    metadata=chunk_meta,
                )
            )

        return chunks
