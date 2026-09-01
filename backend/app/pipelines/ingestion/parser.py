"""Parse OCR output into a structured document tree."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.pipelines.ingestion.ocr import OCRResult, TextBlock


@dataclass
class ParsedNode:
    node_type: str
    text: str
    page_number: int
    paragraph_index: int
    heading_level: int | None = None
    children: list[ParsedNode] = field(default_factory=list)


@dataclass
class ParsedDocument:
    nodes: list[ParsedNode] = field(default_factory=list)

    def to_json(self) -> dict:
        def serialize(node: ParsedNode) -> dict:
            return {
                "node_type": node.node_type,
                "text": node.text,
                "page_number": node.page_number,
                "paragraph_index": node.paragraph_index,
                "heading_level": node.heading_level,
                "children": [serialize(child) for child in node.children],
            }

        return {"nodes": [serialize(node) for node in self.nodes]}


_HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+|[A-Z][A-Z0-9\s\-]{3,})$")


def parse_document(ocr_result: OCRResult) -> ParsedDocument:
    nodes: list[ParsedNode] = []
    current_heading: str | None = None

    for page_blocks in ocr_result.pages:
        for block in page_blocks:
            if not block.text.strip():
                continue
            if _looks_like_heading(block.text):
                current_heading = block.text.strip()
                nodes.append(
                    ParsedNode(
                        node_type="heading",
                        text=current_heading,
                        page_number=block.page_number,
                        paragraph_index=block.paragraph_index,
                        heading_level=_heading_level(block.text),
                    )
                )
            else:
                nodes.append(
                    ParsedNode(
                        node_type="paragraph",
                        text=block.text.strip(),
                        page_number=block.page_number,
                        paragraph_index=block.paragraph_index,
                    )
                )
    return ParsedDocument(nodes=nodes)


def _looks_like_heading(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) > 120:
        return False
    if _HEADING_RE.match(stripped):
        return True
    if stripped.isupper() and len(stripped.split()) <= 8:
        return True
    return False


def _heading_level(text: str) -> int:
    match = re.match(r"^(\d+(?:\.\d+)*)", text.strip())
    if match:
        return match.group(1).count(".") + 1
    return 1


def flatten_paragraphs(parsed: ParsedDocument) -> list[TextBlock]:
    """Flatten parsed nodes into paragraph blocks for chunking."""
    blocks: list[TextBlock] = []
    current_heading: str | None = None
    for node in parsed.nodes:
        if node.node_type == "heading":
            current_heading = node.text
            continue
        blocks.append(
            TextBlock(
                text=node.text,
                page_number=node.page_number,
                paragraph_index=node.paragraph_index,
            )
        )
        if current_heading:
            blocks[-1].text = f"{current_heading}\n{blocks[-1].text}"
    return blocks
