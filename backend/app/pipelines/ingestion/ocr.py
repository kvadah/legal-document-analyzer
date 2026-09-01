"""OCR and text extraction for uploaded documents."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree

from app.core.config import settings


@dataclass
class TextBlock:
    text: str
    page_number: int
    paragraph_index: int
    confidence: float = 1.0
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None


@dataclass
class OCRResult:
    pages: list[list[TextBlock]] = field(default_factory=list)
    skipped_ocr: bool = False
    average_confidence: float = 1.0
    low_quality_warning: str | None = None

    @property
    def page_count(self) -> int:
        return max(len(self.pages), 1)

    def to_json(self) -> dict:
        return {
            "skipped_ocr": self.skipped_ocr,
            "average_confidence": self.average_confidence,
            "low_quality_warning": self.low_quality_warning,
            "pages": [
                [
                    {
                        "text": block.text,
                        "page_number": block.page_number,
                        "paragraph_index": block.paragraph_index,
                        "confidence": block.confidence,
                        "bounding_box": {
                            "x": block.x,
                            "y": block.y,
                            "width": block.width,
                            "height": block.height,
                        },
                    }
                    for block in page
                ]
                for page in self.pages
            ],
        }


def run_ocr(file_bytes: bytes, file_type: str) -> OCRResult:
    ext = file_type.lower().lstrip(".")
    if ext in {"txt", "rtf"}:
        return _extract_plain_text(file_bytes)
    if ext in {"docx", "doc"}:
        return _extract_docx(file_bytes)
    if ext == "pdf":
        return _extract_pdf(file_bytes)
    raise ValueError(f"Unsupported file type for OCR: {file_type}")


def _extract_plain_text(file_bytes: bytes) -> OCRResult:
    text = file_bytes.decode("utf-8", errors="replace")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    blocks = [
        TextBlock(text=para, page_number=1, paragraph_index=idx)
        for idx, para in enumerate(paragraphs)
    ]
    return OCRResult(pages=[blocks], skipped_ocr=True, average_confidence=1.0)


def _extract_docx(file_bytes: bytes) -> OCRResult:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ValueError("Unable to read DOCX content") from exc

    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", ns):
        texts = [node.text for node in para.findall(".//w:t", ns) if node.text]
        if texts:
            paragraphs.append("".join(texts).strip())

    blocks = [
        TextBlock(text=para, page_number=1, paragraph_index=idx)
        for idx, para in enumerate(paragraphs)
        if para
    ]
    return OCRResult(pages=[blocks or [TextBlock(text="", page_number=1, paragraph_index=0)]], skipped_ocr=True)


def _extract_pdf(file_bytes: bytes) -> OCRResult:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[list[TextBlock]] = []
    total_chars = 0

    for page_idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        total_chars += len(text)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()] or [text]
        blocks = [
            TextBlock(text=para, page_number=page_idx, paragraph_index=p_idx)
            for p_idx, para in enumerate(paragraphs)
            if para
        ]
        pages.append(blocks or [TextBlock(text="", page_number=page_idx, paragraph_index=0)])

    page_count = max(len(pages), 1)
    avg_chars = total_chars / page_count
    if avg_chars >= settings.ocr_skip_min_chars_per_page:
        return OCRResult(pages=pages, skipped_ocr=True, average_confidence=1.0)

    return _run_tesseract_on_pdf(file_bytes, page_count=len(reader.pages))


def _run_tesseract_on_pdf(file_bytes: bytes, page_count: int) -> OCRResult:
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError as exc:
        raise ValueError(
            "Scanned PDF requires OCR dependencies (pdf2image, pytesseract, poppler, tesseract)"
        ) from exc

    images = convert_from_bytes(file_bytes)
    pages: list[list[TextBlock]] = []
    confidences: list[float] = []

    for page_idx, image in enumerate(images, start=1):
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        paragraphs: dict[int, list[str]] = {}
        block_conf: dict[int, list[float]] = {}
        for i, text in enumerate(data["text"]):
            if not text or not text.strip():
                continue
            block_num = data["block_num"][i]
            conf = float(data["conf"][i]) if data["conf"][i] != "-1" else 0.0
            paragraphs.setdefault(block_num, []).append(text.strip())
            block_conf.setdefault(block_num, []).append(conf)

        blocks: list[TextBlock] = []
        for p_idx, block_num in enumerate(sorted(paragraphs)):
            joined = " ".join(paragraphs[block_num]).strip()
            avg_conf = sum(block_conf[block_num]) / max(len(block_conf[block_num]), 1) / 100.0
            confidences.append(avg_conf)
            blocks.append(
                TextBlock(
                    text=joined,
                    page_number=page_idx,
                    paragraph_index=p_idx,
                    confidence=avg_conf,
                )
            )
        pages.append(blocks or [TextBlock(text="", page_number=page_idx, paragraph_index=0, confidence=0.0)])

    avg_confidence = sum(confidences) / max(len(confidences), 1)
    warning = None
    if avg_confidence < settings.ocr_low_confidence_threshold:
        warning = (
            "This document was scanned at low quality; extraction accuracy may be reduced."
        )
    return OCRResult(
        pages=pages,
        skipped_ocr=False,
        average_confidence=avg_confidence,
        low_quality_warning=warning,
    )
