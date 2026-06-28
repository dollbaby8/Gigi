"""Document loading with page tracking.

Reads PDF, DOCX, and TXT from the case-files folder and returns a uniform
``Document`` made of ``Page`` objects so that every extracted claim can cite a
specific document + page. Heavy parsers (pypdf, python-docx) are imported
lazily so that a TXT-only workflow needs no extra dependencies.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}

# YYYY-MM-DD or YYYY_MM_DD anywhere in a filename → used as the document date.
_DATE_RE = re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})")


@dataclass
class Page:
    """A single page of extracted text."""

    number: int  # 1-based
    text: str


@dataclass
class Document:
    """A loaded source document."""

    path: Path
    name: str
    pages: List[Page] = field(default_factory=list)
    doc_date: Optional[_dt.date] = None

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)


def infer_date(path: Path) -> Optional[_dt.date]:
    """Infer a document date from its filename, else fall back to mtime."""
    m = _DATE_RE.search(path.name)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    try:
        return _dt.date.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def _read_txt(path: Path) -> List[Page]:
    """Read a text file. Form-feed (\\f) characters mark page breaks."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    chunks = raw.split("\f")
    return [Page(number=i + 1, text=chunk) for i, chunk in enumerate(chunks)]


def _read_pdf(path: Path) -> List[Page]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            f"Reading PDF '{path.name}' requires pypdf. "
            f"Run: pip install -r requirements.txt  ({exc})"
        ) from exc

    reader = PdfReader(str(path))
    pages: List[Page] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append(Page(number=i + 1, text=text))
    return pages


def _read_docx(path: Path) -> List[Page]:
    try:
        import docx  # python-docx
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            f"Reading DOCX '{path.name}' requires python-docx. "
            f"Run: pip install -r requirements.txt  ({exc})"
        ) from exc

    document = docx.Document(str(path))
    # DOCX has no hard page model; treat an explicit page break as a boundary,
    # otherwise the whole document is page 1.
    pages: List[str] = [""]
    for para in document.paragraphs:
        text = para.text
        if "\f" in text:
            parts = text.split("\f")
            pages[-1] += parts[0] + "\n"
            for part in parts[1:]:
                pages.append(part + "\n")
        else:
            pages[-1] += text + "\n"
    return [Page(number=i + 1, text=t) for i, t in enumerate(pages)]


def load_document(path: Path) -> Document:
    """Load a single document by suffix."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        pages = _read_txt(path)
    elif suffix == ".pdf":
        pages = _read_pdf(path)
    elif suffix == ".docx":
        pages = _read_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {path.name}")

    return Document(
        path=path,
        name=path.name,
        pages=pages,
        doc_date=infer_date(path),
    )


def load_documents(case_dir: Path) -> List[Document]:
    """Load every supported document in ``case_dir`` (sorted by name)."""
    case_dir = Path(case_dir)
    if not case_dir.exists():
        raise FileNotFoundError(
            f"Case-files folder not found: {case_dir}. "
            "Create it and drop in your PDF/DOCX/TXT documents."
        )

    documents: List[Document] = []
    for path in sorted(case_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            documents.append(load_document(path))
    return documents
