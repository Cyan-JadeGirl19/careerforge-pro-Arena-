"""Parse a reference list (text/PDF/DOCX) into structured references.

Heuristic but conservative: a reference needs an email or phone to be
worth adding; the name is the nearest plausible line above the contact
line. Everything comes back with permission_confirmed=False - the
candidate must confirm they have permission before anything is shared.
"""
import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?<![\w.])(\+?\d[\d\s()-]{8,}\d)(?![\w])")
_NAME_RE = re.compile(r"^[A-Z][a-zA-Z'.-]+(?: [A-Z][a-zA-Z'.-]+){1,3}$")
_SKIP = re.compile(
    r"^(ref|referee|reference|name|title|company|email|phone|contact|notes?|date|signature|typed|printed|relationship)\b",
    re.I,
)


def extract_text(filename: str, data: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    if lower.endswith(".docx"):
        import io

        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if lower.endswith(".pdf"):
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    raise ValueError("Unsupported file type for reference lists.")


def parse_reference_list(text: str) -> list[dict]:
    """One blank-line-separated block = one person. A block is kept only
    if it contains an email or phone. Permission is never assumed."""
    out: list[dict] = []
    used: set[str] = set()

    for block in re.split(r"\n\s*\n", text or ""):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        email = next((_EMAIL_RE.search(ln) for ln in lines if _EMAIL_RE.search(ln)), None)
        phone = next((_PHONE_RE.search(ln) for ln in lines if _PHONE_RE.search(ln)), None)
        if not email and not phone:
            continue
        name = None
        for ln in lines:
            if "@" in ln or _PHONE_RE.search(ln):
                continue
            if _NAME_RE.match(ln) and not _SKIP.search(ln):
                name = ln
                break
        key = (
            email.group(0).lower() if email else "",
            re.sub(r"\D", "", phone.group(1)) if phone else "",
        )
        if key in used:
            continue
        used.add(key)
        out.append(
            {
                "name": name,
                "email": email.group(0) if email else None,
                "phone": phone.group(1) if phone else None,
                "title": None,
                "company": None,
                "type": "current",
                "notes": None,
                "permission_confirmed": False,
            }
        )
    return out
