"""Export recognized text to the supported text formats.

Single entry point: `export_text()` writes the result to one or more formats.
Formats: TXT, MD, RTF, HTML, DOCX, ODT, PDF, EPUB, JSON.
"""

from __future__ import annotations

import json
import os
import re
import datetime
from dataclasses import dataclass, field

from . import otsl

EXPORT_FORMATS = ["txt", "md", "rtf", "html", "docx", "odt", "pdf", "epub", "json"]


@dataclass
class OcrText:
    """Recognized document: full text plus per-page records."""
    source_path: str
    full_text: str
    pages: list[dict] = field(default_factory=list)  # [{index, image, text}]

    @property
    def base_name(self) -> str:
        return os.path.splitext(os.path.basename(self.source_path))[0]

    def as_dict(self) -> dict:
        return {
            "source_file": os.path.basename(self.source_path),
            "recognized_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "model": "SeerRay-Lab/Xiaomi-OCR-0",
            "pages": self.pages,
            "full_text": self.full_text,
        }


# ------------------------------------------------------------------ prep ----

H1_RE = re.compile(r"^#{1,6}\s*", re.M)


def plain_from_markdown(md: str) -> str:
    """Markdown -> plain text (no markup, LaTeX preserved)."""
    text = otsl.preprocess_markdown(md)
    # HTML tables -> text rows/cells
    def table_to_text(m: re.Match) -> str:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(0), re.S)
        if not cells:
            return ""
        return " | ".join(re.sub(r"<[^>]+>", "", c) for c in cells)
    text = re.sub(r"<table.*?</table>", table_to_text, text, flags=re.S)

    lines = text.split("\n")
    out = []
    in_code = False
    for line in lines:
        s = line
        if s.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            s = re.sub(r"^#{1,6}\s*", "", s)
            s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
            s = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", s)
            s = re.sub(r"^\s*[-*]\s+", "• ", s)
        out.append(s)
    return "\n".join(out).strip()


# ------------------------------------------------------------- markdown ----

HTML_CSS = """
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 2.5em auto; max-width: 900px;
       line-height: 1.55; color: #1a1a1a; padding: 0 1em; }
h1,h2,h3 { line-height: 1.25; }
pre { background: #f5f5f7; border: 1px solid #e2e2e6; padding: .8em 1em; overflow-x: auto; border-radius: 6px; }
code { background: #f5f5f7; border-radius: 3px; padding: 0 .3em; }
table.xt-table { border-collapse: collapse; margin: 1em 0; width: 100%; font-size: .95em; }
.xt-table td, .xt-table th { border: 1px solid #c8c8cc; padding: .35em .6em; vertical-align: top; }
.xt-table th { background: #eef1f6; }
.xt-merge-left { border-left-color: transparent; }
.xt-merge-top { border-top-color: transparent; }
.xt-merge-right { border: none; }
blockquote { border-left: 3px solid #d0d0d0; margin-left: 0; padding-left: 1em; color: #444; }
img { max-width: 100%; }
"""

KATEX_HEAD = (
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js" '
    'onload="renderMathInElement(document.body,{delimiters:['
    '{left:\'\\\\[\',right:\'\\\\]\',display:true},{left:\'\\\\(\',right:\'\\\\)\',display:false}]});"></script>'
)


def md_to_html_body(md: str) -> str:
    import markdown
    prepared = otsl.preprocess_markdown(md)
    return markdown.markdown(
        prepared,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
        output_format="html5",
    )


def build_html_doc(md: str, title: str, with_katex: bool = True) -> str:
    body = md_to_html_body(md)
    head = KATEX_HEAD if with_katex else ""
    return (
        "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{title}</title>\n{head}\n<style>{HTML_CSS}</style>\n</head>\n<body>\n"
        + body + "\n</body>\n</html>\n"
    )


# ------------------------------------------------------------------ rtf ----

def _rtf_escape(s: str) -> str:
    out = []
    for ch in s:
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ord(ch) > 127:
            out.append("\\u%d?" % (ord(ch) if ord(ch) < 32768 else ord(ch) - 65536))
        elif ch == "\n":
            out.append("\\par\n")
        else:
            out.append(ch)
    return "".join(out)


def build_rtf(md: str) -> str:
    plain = plain_from_markdown(md)
    parts = [r"{\rtf1\ansi\deff0{\fonttbl{\f0\fswiss Arial;}}\fs20"]
    for line in plain.split("\n"):
        stripped = line.strip()
        if not stripped:
            parts.append(r"\par\par")
            continue
        if otsl.is_otsl_line(stripped):
            continue
        parts.append(_rtf_escape(stripped) + r"\par")
    parts.append("}")
    return "\n".join(parts)


# ----------------------------------------------------------------- docx ----

def build_docx(md: str, path: str, monospace_font: str = "Courier New") -> None:
    import docx
    from docx.shared import Pt

    doc = docx.Document()  # new empty document

    def add_table(rows: list[list[str]]):
        if not rows:
            return
        n_cols = max(len(r) for r in rows)
        t = doc.add_table(rows=len(rows), cols=n_cols)
        t.style = "Table Grid"
        for ri, row in enumerate(rows):
            for ci in range(n_cols):
                cell = t.rows[ri].cells[ci]
                cell.text = row[ci] if ci < len(row) else ""

    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if otsl.is_otsl_line(stripped):
            block = []
            while i < len(lines) and otsl.is_otsl_line(lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            html = re.sub(r"\s*\n\s*", " ", "\n".join(block))
            html = otsl.otsl_to_html(html)
            rows: list[list[str]] = []
            for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
                cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
                if cells:
                    rows.append(cells)
            add_table(rows)
            continue

        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            p = doc.add_paragraph()
            run = p.add_run("\n".join(buf))
            run.font.name = monospace_font
            run.font.size = Pt(9)
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)), 4)
            doc.add_heading(m.group(2), level=level)
            i += 1
            continue

        if re.match(r"^(\|\s?)", stripped) and stripped.endswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = []
            for r_ in block:
                if re.match(r"^\|[\s:-]+\|[|\s:-]*$", r_):
                    continue
                rows.append([c.strip() for c in r_.strip("|").split("|")])
            add_table(rows)
            continue

        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            doc.add_paragraph(m.group(1), style="List Bullet")
            i += 1
            continue
        if re.match(r"^\d+[.)]\s+(.*)$", stripped):
            doc.add_paragraph(re.sub(r"^\d+[.)]\s+", "", stripped), style="List Number")
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        p = doc.add_paragraph()
        run = p.add_run(stripped)
        run.font.size = Pt(11)
        i += 1

    doc.save(path)


# ------------------------------------------------------------------ odt ----

def build_odt(md: str, path: str) -> None:
    from odf import style as odf_style, text as odf_text
    from odf.opendocument import OpenDocumentText

    doc = OpenDocumentText()

    hstyles = {}
    for lvl, size in ((1, "20pt"), (2, "16pt"), (3, "13pt")):
        st = odf_style.Style(name=f"HeadingX{lvl}", family="paragraph")
        st.addElement(odf_style.TextProperties(fontsize=size, fontweight="bold"))
        doc.automaticstyles.addElement(st)
        hstyles[lvl] = f"HeadingX{lvl}"

    def para(t: str, stylename: str | None = None):
        p = odf_text.P(text=t)
        if stylename:
            p.setAttribute("stylename", stylename)
        doc.text.addElement(p)

    lines = re.sub(
        r"<table.*?</table>",
        lambda m: " | ".join(
            re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(0), re.S)
        ),
        otsl.preprocess_markdown(md),
        flags=re.S,
    ).split("\n")

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            para(m.group(2), hstyles[min(len(m.group(1)), 3)])
            i += 1
            continue
        if s.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                para(lines[i])
                i += 1
            i += 1
            continue
        if s:
            para(s.lstrip("-*• ").lstrip())
        i += 1

    doc.save(path)


# ------------------------------------------------------------------ pdf ----

_UFONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    # Windows
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]


def _find_unicode_font() -> str | None:
    for c in _UFONT_CANDIDATES:
        if os.path.isfile(c):
            return c
    # generic search under /usr/share/fonts
    if os.path.isdir("/usr/share/fonts"):
        for root, _dirs, files in os.walk("/usr/share/fonts"):
            for f in files:
                if f.lower() in {"dejavusans.ttf", "liberationre_gular.ttf", "liberationregular.ttf", "notosansregular.ttf"}:
                    return os.path.join(root, f)
    return None


def build_pdf(text: str, path: str, title: str = "") -> None:
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_title(title)
    pdf.add_page()

    font = _find_unicode_font()
    if font:
        pdf.add_font("uni", "", font)
        main = "uni"
        bold = None
        try:
            for cand in _UFONT_CANDIDATES:
                b = cand.replace("Arial Unicode", "Arial Bold").replace("Arial.ttf", "Arial Bold.ttf")
                if os.path.isfile(b):
                    pdf.add_font("uniB", "", b)
                    bold = "uniB"
                    break
        except Exception:
            bold = None
    else:
        main = "helvetica"  # Latin; Cyrillic may render incorrectly
        bold = "bold"

    def emit(line: str, size: float = 11, is_bold: bool = False):
        font_name = bold if (bold and is_bold) else main
        pdf.set_font(font_name, size=size)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, size * 0.55, line)
        if is_bold:
            pdf.set_font(main, size=11)
        pdf.set_x(pdf.l_margin)

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            pdf.ln(2)
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line.strip())
        if m:
            size = {1: 18, 2: 15, 3: 13}[len(m.group(1))]
            emit(m.group(2), size, is_bold=bool(bold))
            i += 1
            continue
        stripped = line.strip()
        if otsl.is_otsl_line(stripped):
            cells = []
            while i < len(lines) and otsl.is_otsl_line(lines[i].strip()):
                cells.extend(re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", lines[i], re.S))
                i += 1
            emit(" | ".join(re.sub(r"<[^>]+>", "", c) for c in cells), 9)
            continue
        emit(stripped.strip(" `"), 9 if stripped.startswith("```") else 11)
        i += 1

    pdf.output(path)


# ---------------------------------------------------------------- epub ----

def build_epub(md: str, path: str, title: str = "", author: str = "Xiaomi OCR") -> None:
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("xiaomi-ocr-" + str(abs(hash(title)) % 10**10))
    book.set_title(title or "Recognized document")
    book.set_language("ru")
    book.add_author(author)

    css = epub.EpubItem(uid="style", file_name="style/main.css", media_type="text/css", content=HTML_CSS)
    book.add_item(css)

    html_body = md_to_html_body(md)
    chapter = epub.EpubHtml(title=title, file_name="doc.xhtml", lang="ru")
    chapter.content = f"<h1>{title}</h1>\n{html_body}"
    chapter.add_item(css)
    book.add_item(chapter)

    book.toc = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    epub.write_epub(path, book)


# --------------------------------------------------------------- the API ----

def export_text(text_obj: OcrText, out_dir: str, formats: list[str]) -> list[str]:
    """Writes the result to the selected formats. Returns the files created."""
    os.makedirs(out_dir, exist_ok=True)
    base = _safe_name(text_obj.base_name)
    title = text_obj.base_name
    written = []

    for fmt in formats:
        fmt = fmt.lower()
        path = _unique(os.path.join(out_dir, f"{base}.{fmt}"))
        try:
            if fmt == "txt":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(plain_from_markdown(text_obj.full_text) + "\n")
            elif fmt == "md":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text_obj.full_text + "\n")
            elif fmt == "rtf":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(build_rtf(text_obj.full_text))
            elif fmt == "html":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(build_html_doc(text_obj.full_text, title))
            elif fmt == "docx":
                build_docx(text_obj.full_text, path)
            elif fmt == "odt":
                build_odt(text_obj.full_text, path)
            elif fmt == "pdf":
                build_pdf(plain_from_markdown(text_obj.full_text), path, title=title)
            elif fmt == "epub":
                build_epub(text_obj.full_text, path, title=title)
            elif fmt == "json":
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(text_obj.as_dict(), f, ensure_ascii=False, indent=2)
            else:
                continue
            written.append(path)
        except ModuleNotFoundError:
            raise
        except Exception as e:
            # one failing format must not abort the whole export
            written.append(f"! {os.path.basename(path)}: {e}")
    return written


def _unique(path: str) -> str:
    """Never overwrite: add a _2, _3 … suffix when the file already exists."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 2
    while True:
        cand = f"{base}_{i}{ext}"
        if not os.path.exists(cand):
            return cand
        i += 1


def _safe_name(s: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", s).strip() or "result"
