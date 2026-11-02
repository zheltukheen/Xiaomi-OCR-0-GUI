"""File intake: reduce input to page images (for OCR) or to plain text.

PDFs and images go through OCR; office and plain-text files are converted
to text directly (no OCR needed).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".jfif", ".gif"}
TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".xml", ".log", ".yaml", ".yml", ".ini"}
RTF_EXTS = {".rtf"}
DOCX_EXTS = {".docx"}
PPTX_EXTS = {".pptx"}
ODT_EXTS = {".odt"}
PDF_EXTS = {".pdf"}

SUPPORTED_EXTS = IMAGE_EXTS | TEXT_EXTS | RTF_EXTS | DOCX_EXTS | PPTX_EXTS | ODT_EXTS | PDF_EXTS

KIND_OCR = "ocr"      # page images
KIND_TEXT = "text"    # text extracted directly


@dataclass
class IngestResult:
    path: str
    kind: str
    pages: list[str] = field(default_factory=list)   # paths to page images
    texts: list[str] = field(default_factory=list)   # text (KIND_TEXT: single entry)
    note: str = ""

    @property
    def page_count(self) -> int:
        return max(len(self.pages), len(self.texts))


def is_pdf(p): return os.path.splitext(p)[1].lower() in PDF_EXTS
def is_image(p): return os.path.splitext(p)[1].lower() in IMAGE_EXTS


class IngestError(RuntimeError):
    pass


def _pdf_to_images(path: str, dpi: int, tmpdir: str) -> list[str]:
    try:
        import pymupdf as fitz
    except ImportError:  # older versions
        import fitz  # type: ignore
    base = os.path.splitext(os.path.basename(path))[0]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    out = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png = os.path.join(tmpdir, f"{base}_p{i + 1:04d}.png")
            pix.save(png)
            out.append(png)
    return out


def _docx_text(path: str) -> str:
    import docx
    from docx.document import Document as _Doc
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(path)
    lines: list[str] = []

    def emit_table(tbl: Table) -> None:
        rows = []
        for row in tbl.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            rows.append("| " + " | ".join(cells) + " |")
        if len(rows) >= 2:
            n = rows[0].count("|") - 2
            rows.insert(1, "|" + " --- |" * max(n, 1))
        lines.extend(rows)
        lines.append("")

    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            style = (p.style.name or "").lower() if p.style is not None else ""
            t = p.text.strip()
            if not t:
                continue
            if style.startswith("heading"):
                try:
                    lvl = int(style.split()[-1])
                except ValueError:
                    lvl = 2
                lines.append("#" * min(lvl, 6) + " " + t)
            else:
                lines.append(p.text)
        elif child.tag == qn("w:tbl"):
            emit_table(Table(child, doc))

    text = "\n".join(lines).strip()
    return text


def _pptx_text(path: str) -> str:
    from pptx import Presentation

    prs = Presentation(path)
    out = []
    for i, slide in enumerate(prs.slides, 1):
        out.append(f"## Slide {i}")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = "".join(run.text for run in para.runs).strip()
                    if t:
                        out.append(t)
        out.append("")
    return "\n".join(out).strip()


def _odt_text(path: str) -> str:
    from odf import text as odf_text, teletype
    from odf.opendocument import load as odf_load

    doc = odf_load(path)
    paragraphs = doc.getElementsByType(odf_text.P) + doc.getElementsByType(odf_text.H)
    return "\n".join(teletype.extractText(p) for p in paragraphs if teletype.extractText(p)).strip()


def _rtf_text(path: str) -> str:
    from striprtf.striprtf import rtf_to_text
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return rtf_to_text(f.read()).strip()


def _plain_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".json"}:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            try:
                return json.dumps(json.load(f), ensure_ascii=False, indent=2)
            except Exception:
                f.seek(0)
                return f.read()
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read().strip()


def ingest(path: str, dpi: int = 200, tmpdir: str | None = None) -> IngestResult:
    """Reduce a file to a form suitable for recognition."""
    if not os.path.isfile(path):
        raise IngestError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise IngestError(
            f"Unknown format {ext or '(no extension)'}. Supported: PDF, images, DOCX, PPTX, ODT, RTF and text files."
        )

    cleanup_dir = None
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp(prefix="xiaomi_ocr_")
        cleanup_dir = tmpdir

    if is_pdf(path):
        pages = _pdf_to_images(path, dpi, tmpdir)
        if not pages:
            raise IngestError("The PDF has no pages")
        return IngestResult(path=path, kind=KIND_OCR, pages=pages)

    if is_image(path):
        return IngestResult(path=path, kind=KIND_OCR, pages=[path])

    try:
        if ext in DOCX_EXTS:
            text = _docx_text(path)
        elif ext in PPTX_EXTS:
            text = _pptx_text(path)
        elif ext in ODT_EXTS:
            text = _odt_text(path)
        elif ext in RTF_EXTS:
            text = _rtf_text(path)
        else:
            text = _plain_text(path)
    except IngestError:
        raise
    except Exception as e:
        raise IngestError(f"Could not read {os.path.basename(path)}: {e}")

    if not text:
        raise IngestError(f"File is empty or no text was extracted: {os.path.basename(path)}")

    if cleanup_dir:
        try:
            os.rmdir(cleanup_dir)
        except OSError:
            pass

    return IngestResult(path=path, kind=KIND_TEXT, texts=[text],
                        note="Text file: content extracted directly, OCR is not required.")
