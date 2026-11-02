"""HTML rendering of a result page."""

import os

from .. import exporters

PAGE_EMPTY_HTML = "<p><i>Waiting for recognition…</i></p>"


def md_to_styled_html(md: str) -> str:
    body = exporters.md_to_html_body(md)
    return (
        "<style>"
        + exporters.HTML_CSS
        + ("body{margin:0;padding:1em;color:#111;}"
           ".xt-table{border-collapse:collapse;margin:.8em 0;width:100%;font-size:.95em;}"
           ".xt-table td,.xt-table th{border:1px solid #bbb;padding:.3em .55em;vertical-align:top;}"
           ".xt-table th{background:#eef1f6;}"
           ".xt-merge-left{border-left-color:transparent;}"
           ".xt-merge-top{border-top-color:transparent;}"
           ".xt-merge-right{border:none}")
        + "</style>"
    ) + body


def page_to_html(text: str) -> str:
    text = text or ""
    if not text.strip():
        return PAGE_EMPTY_HTML
    return md_to_styled_html(text)
