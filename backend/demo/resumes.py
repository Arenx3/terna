"""Tiny, valid PDFs with real text, for fictional demo candidates.

Hand-written PDF 1.4 with the standard Helvetica font, so no PDF library is
needed and the text can be extracted later by the résumé parser.
"""


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def resume_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with `lines`; the first one is set as the heading."""
    commands = ["BT", "/F1 18 Tf", "56 780 Td", f"({_escape(lines[0])}) Tj", "/F1 11 Tf"]
    for line in lines[1:]:
        commands += ["0 -18 Td", f"({_escape(line)}) Tj"]
    commands.append("ET")
    stream = "\n".join(commands).encode("cp1252", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
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
