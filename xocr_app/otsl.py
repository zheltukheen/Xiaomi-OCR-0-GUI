"""Конвертация таблиц OTSL (выходной формат таблиц Xiaomi-OCR-0) в HTML.

OTSL (Optimized Table Structure Language) — разметка таблиц, которой модель
отвечает для табличных областей. Здесь выполняется базовая конвертация в
HTML-таблицу: ячейки, разделители строк, заголовки и merge-ячейки.
"""

from __future__ import annotations

import re

TOKEN_RE = re.compile(
    r"<(nl|fcel|ecel|lcel|ucel|xcel|rh|rhb|fm|fs|fsl|sum|cap|nel|reol|neol)\b[^>]*>|([^<&]+|<|&)"
)

CELL_TOKENS = {"fcel", "ecel", "lcel", "ucel", "xcel", "rh", "rhb", "fm", "fs", "fsl", "sum"}
ROW_SEP = "nl"

HEADER_TOKENS = {"rh", "rhb"}
MERGE_CSS = {
    "lcel": "xt-merge-left",
    "ucel": "xt-merge-top",
    "xcel": "xt-merge-left xt-merge-top",
}


def is_otsl(text: str) -> bool:
    low = text.strip().lower()
    return "<fcel>" in low and ("<nl>" in low or "<rh>" in low or "<ecel>" in low)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def otsl_to_html(otsl: str) -> str:
    """Преобразует строку OTSL в HTML <table> (best-effort)."""
    rows: list[list[dict]] = []
    cur_row: list[dict] = []
    cur_cell_text: list[str] = []
    pending_kind: str | None = None

    def emit_cell():
        text = "".join(cur_cell_text).strip()
        cur_cell_text.clear()
        kind = pending_kind
        if kind is None and not text:
            return
        if kind is None:
            kind = "fcel"
        cur_row.append({
            "text": text,
            "kind": kind,
            "header": kind in HEADER_TOKENS,
            "cls": MERGE_CSS.get(kind, ""),
            "colspan": 1,
        })

    for m in TOKEN_RE.finditer(otsl):
        token, plain = m.group(1), m.group(2)
        if token:
            if token == ROW_SEP:
                emit_cell()
                if cur_row:
                    rows.append(cur_row)
                    cur_row = []
                    pending_kind = None
            elif token in CELL_TOKENS:
                emit_cell()
                pending_kind = token
        elif plain is not None:
            cur_cell_text.append(plain)

    emit_cell()
    if cur_row:
        rows.append(cur_row)

    if not rows:
        return ""

    width = max(len(r) for r in rows)
    html_rows = []
    for row in rows:
        tds = []
        for cell in row:
            tag = "th" if cell["header"] else "td"
            attrs = []
            if cell["colspan"] > 1:
                attrs.append(f'colspan="{cell["colspan"]}"')
            if cell["cls"]:
                attrs.append(f'class="{cell["cls"]}"')
            markup = f'<{tag} {" ".join(attrs)}>' if attrs else f"<{tag}>"
            tds.append(markup + _escape(cell["text"]) + f"</{tag}>")
        # дополним неполные строки пустыми ячейками для ровной сетки
        filled = sum(c["colspan"] for c in row)
        if filled < width:
            tds.extend(['<td class="xt-merge-right"></td>'] * (width - filled))
        html_rows.append("<tr>" + "".join(tds) + "</tr>")

    body = "\n".join(html_rows)
    return (
        '<table class="xt-table">\n'
        "<tbody>\n" + body + "\n</tbody>\n"
        "</table>"
    )


def is_otsl_line(line: str) -> bool:
    low = line.lower()
    return "<fcel>" in low or "<ecel>" in low or "<nl>" in low or "<rh" in low


def preprocess_markdown(md: str) -> str:
    """Заменяет найденные OTSL-фрагменты в markdown на HTML-таблицы."""
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if is_otsl_line(line):
            block = []
            while i < n and is_otsl_line(lines[i]):
                block.append(lines[i])
                i += 1
            html = otsl_to_html("\n".join(block))
            out.append(html if html else "\n".join(block))
            out.append("")
        else:
            out.append(line)
            i += 1
    return "\n".join(out)
