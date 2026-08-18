def make_minimal_pdf_bytes(text: str = "Hello World") -> bytes:
    """Hand-builds a minimal, spec-valid single-page PDF with the given text
    drawn on the page (or no text operator at all if `text` is empty).
    Avoids depending on a PDF-writing library just for test fixtures.
    """
    content_stream = f"BT /F1 24 Tf 20 100 Td ({text}) Tj ET".encode() if text else b""

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 200 200] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream
        + b"\nendstream",
    ]

    buffer = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj_body in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer += f"{index} 0 obj\n".encode() + obj_body + b"\nendobj\n"

    xref_offset = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode()
    buffer += b"0000000000 65535 f \n"
    for offset in offsets:
        buffer += f"{offset:010d} 00000 n \n".encode()
    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    return bytes(buffer)


def make_multi_page_pdf_bytes(pages: list[str]) -> bytes:
    """Builds a valid multi-page PDF by combining single-page PDFs (built
    by make_minimal_pdf_bytes) with pypdf, which handles the multi-page
    xref/structure correctly — more reliable than hand-writing it.
    """
    import io

    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for page_text in pages:
        reader = PdfReader(io.BytesIO(make_minimal_pdf_bytes(page_text)))
        writer.add_page(reader.pages[0])

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
