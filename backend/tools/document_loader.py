"""Document ingestion tool parsing user-uploaded reference documents (PDF, TXT, MD, DOCX)."""
import os
from typing import Dict, Any, List
from backend.core.logging_config import logger
from backend.core.exceptions import ToolExecutionError
from backend.core.security import sanitize_upload_filename
from backend.tools.source_extractor import extract_evidence_from_content

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".docx"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text from a PDF file using pypdf."""
    try:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                pages_text.append(f"[Page {i + 1}]\n{text.strip()}")
        return "\n\n".join(pages_text)
    except Exception as exc:
        raise ToolExecutionError(f"Failed to extract text from PDF: {exc}", tool_name="document_loader")

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extracts text from a DOCX file using python-docx or zipfile fallback."""
    try:
        import io
        import zipfile
        import xml.etree.ElementTree as ET

        # Fast XML extraction from docx zip without external heavy dependencies
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as docx:
            xml_content = docx.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            # Find all w:t text nodes
            paragraphs = []
            for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                texts = [node.text for node in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if node.text]
                if texts:
                    paragraphs.append("".join(texts))
            return "\n\n".join(paragraphs)
    except Exception as exc:
        raise ToolExecutionError(f"Failed to extract text from DOCX: {exc}", tool_name="document_loader")

def ingest_document(
    filename: str,
    file_bytes: bytes,
    task_id: str,
    start_evidence_index: int = 1,
) -> Dict[str, Any]:
    """Ingests, validates, extracts text, and produces traceable user evidence from an uploaded document."""
    clean_name = sanitize_upload_filename(filename)
    ext = os.path.splitext(clean_name)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ToolExecutionError(
            f"Unsupported document format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            tool_name="document_loader"
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ToolExecutionError(
            f"File size ({len(file_bytes)} bytes) exceeds the maximum limit of 10 MB.",
            tool_name="document_loader"
        )

    logger.info(f"Ingesting document '{clean_name}' ({len(file_bytes)} bytes) for task {task_id}")

    # Extract text based on extension
    if ext == ".pdf":
        extracted_text = extract_text_from_pdf(file_bytes)
    elif ext == ".docx":
        extracted_text = extract_text_from_docx(file_bytes)
    else:
        # Plain text / Markdown
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = file_bytes.decode("latin-1", errors="replace")

    if not extracted_text or len(extracted_text.strip()) < 20:
        raise ToolExecutionError(
            f"Document '{clean_name}' contains insufficient readable text ({len(extracted_text)} characters).",
            tool_name="document_loader"
        )

    doc_url = f"file://user-uploads/{clean_name}"
    
    # Extract evidence records tagged as user_upload
    evidences = extract_evidence_from_content(
        content=extracted_text,
        source_url=doc_url,
        source_title=f"[User Document] {clean_name}",
        domain="user_upload",
        start_index=start_evidence_index,
        provenance="user_upload",
    )

    source_record = {
        "title": f"[Uploaded Document] {clean_name}",
        "url": doc_url,
        "domain": "user_upload",
        "access_status": "user_provided",
        "http_status_code": 200,
        "extracted_chars": len(extracted_text),
        "raw_content_preview": extracted_text[:400],
        "provenance": "user_upload",
    }

    return {
        "filename": clean_name,
        "extracted_chars": len(extracted_text),
        "source": source_record,
        "evidences": evidences,
        "summary": f"Successfully parsed {clean_name} ({len(extracted_text):,} chars). Generated {len(evidences)} user-provided evidence records.",
    }
