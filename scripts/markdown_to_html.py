#!/usr/bin/env python3
"""Render the markdown pages as HTML, so they look like pages and not like
source code.

    scripts/markdown_to_html.py /srv/ios-pages/accounts.md /srv/ios-pages/accounts.html
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

STYLE = """
body { background:#0b0a0e; color:#f4f4f5; font:15px/1.6 -apple-system,BlinkMacSystemFont,
       'Helvetica Neue',Arial,sans-serif; margin:0; padding:28px; }
.wrap { max-width:860px; margin:0 auto; }
h1 { font-size:24px; margin:0 0 18px; }
h2 { font-size:18px; margin:30px 0 10px; padding-bottom:6px; border-bottom:1px solid #26262c; }
h3 { font-size:15px; margin:22px 0 8px; }
table { border-collapse:collapse; width:100%; margin:14px 0; font-size:14px; }
th, td { border:1px solid #2c2c2e; padding:8px 10px; text-align:left; vertical-align:top; }
th { background:#17161c; }
code, .mono { font-family:ui-monospace,Menlo,monospace; font-size:13px; background:#17161c;
       padding:2px 5px; border-radius:4px; }
pre { background:#17161c; border:1px solid #2c2c2e; border-radius:10px; padding:14px;
      overflow:auto; }
pre code { background:none; padding:0; }
a { color:#f5428c; }
ul, ol { padding-left:22px; }
li { margin:5px 0; }
blockquote { border-left:3px solid #f5428c; margin:14px 0; padding:4px 14px; color:#d4d4d8; }
hr { border:0; border-top:1px solid #26262c; margin:26px 0; }
"""


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def convert(markdown: str) -> str:
    out: list[str] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            block = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(html.escape(lines[index]))
                index += 1
            out.append("<pre><code>" + "\n".join(block) + "</code></pre>")
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(lines) and set(lines[index + 1].strip()) <= set("|-: "):
            header = [cell.strip() for cell in line.strip().strip("|").split("|")]
            index += 2
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr>")
            for row in rows:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            out.append("</table>")
            continue
        if line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif re.match(r"^[-*] ", line):
            items = []
            while index < len(lines) and re.match(r"^[-*] ", lines[index]):
                items.append(f"<li>{inline(lines[index][2:])}</li>")
                index += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif re.match(r"^\d+\. ", line):
            items = []
            while index < len(lines) and re.match(r"^\d+\. ", lines[index]):
                items.append(f"<li>{inline(re.sub(r'^\d+\. ', '', lines[index]))}</li>")
                index += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
        elif not line.strip():
            pass
        else:
            out.append(f"<p>{inline(line)}</p>")
        index += 1
    body = "\n".join(out)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>SuperCraftOS</title><style>{STYLE}</style></head>"
            f'<body><div class="wrap">{body}</div></body></html>')


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    source = Path(sys.argv[1])
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_suffix(".html")
    target.write_text(convert(source.read_text()))
    print(f"{source} -> {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
