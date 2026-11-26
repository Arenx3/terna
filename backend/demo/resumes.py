"""Tiny, valid PDFs with real text, for fictional demo candidates.

Hand-written PDF 1.4 with the standard Helvetica fonts, so no PDF library is
needed and the résumé parser has real text to read. The first line is the
name; lines starting with "# " are section headings, in bold.
"""

LINES_PER_PAGE = 40


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(lines: list[str], first_page: bool) -> bytes:
    commands = ["BT", "56 780 Td"]
    for number, line in enumerate(lines):
        if number:
            commands.append("0 -18 Td")
        if first_page and number == 0:
            commands += ["/F2 18 Tf", f"({_escape(line)}) Tj"]
        elif line.startswith("# "):
            commands += ["/F2 12 Tf", f"({_escape(line[2:])}) Tj"]
        else:
            commands += ["/F1 11 Tf", f"({_escape(line)}) Tj"]
    commands.append("ET")
    return "\n".join(commands).encode("cp1252", errors="replace")


def resume_pdf(lines: list[str]) -> bytes:
    """A PDF with `lines`, 40 to a page."""
    pages = [lines[i : i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
    # 1 catalog, 2 pages, 3 regular font, 4 bold font, then a page and its content per page.
    kids = " ".join(f"{5 + 2 * index} 0 R" for index in range(len(pages))).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % len(pages),
        font % b"Helvetica",
        font % b"Helvetica-Bold",
    ]
    for index, page_lines in enumerate(pages):
        stream = _page_stream(page_lines, first_page=index == 0)
        objects += [
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>"
            % (6 + 2 * index),
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)
