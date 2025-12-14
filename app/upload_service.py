"""
PDF Upload and Ingestion Service for Admin
Handles PDF thesis uploads with duplicate detection and FAISS index appending

Uses PyMuPDF (fitz) for PDF extraction - research standard for academic papers:
- 10x faster than PyPDF2
- Better handling of academic formatting (columns, figures, tables)
- Superior text extraction accuracy for theses
"""
import os
import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Get base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DIR = os.path.join(BASE_DIR, "index")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
METADATA_FILE = os.path.join(INDEX_DIR, "uploaded_documents.json")

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)


class DuplicateDocumentError(Exception):
    """Raised when attempting to upload a document that already exists"""
    pass


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails"""
    pass


def _load_document_metadata() -> Dict:
    """Load metadata of previously uploaded documents"""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load document metadata: {e}")
    return {"documents": [], "title_hashes": {}, "content_hashes": {}}


def _save_document_metadata(metadata: Dict):
    """Save document metadata for duplicate detection"""
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Could not save document metadata: {e}")


def _compute_content_hash(text: str) -> str:
    """Compute hash of document content for duplicate detection"""
    # Normalize text: lowercase, remove extra whitespace
    normalized = ' '.join(text.lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _compute_title_hash(title: str) -> str:
    """Compute hash of document title for quick lookup"""
    # Normalize title
    normalized = ' '.join(title.lower().split())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def _extract_title_from_pdf(doc: fitz.Document) -> str:
    """
    Extract thesis title from PDF
    Attempts multiple strategies:
    1. PDF metadata
    2. First page text (common for academic papers)
    """
    # Try PDF metadata first
    metadata = doc.metadata
    if metadata.get('title') and len(metadata['title'].strip()) > 10:
        return metadata['title'].strip()
    
    # Extract from first page - thesis titles are usually in the first few lines
    if doc.page_count > 0:
        first_page = doc[0]
        text = first_page.get_text("text")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Look for title-like text (usually uppercase or title case, substantial length)
        for line in lines[:10]:  # Check first 10 lines
            # Skip short lines or lines that look like headers/page numbers
            if len(line) > 20 and not line.isdigit():
                # Thesis titles are often in uppercase
                if line.isupper() or (len(line) > 30 and any(c.isupper() for c in line)):
                    return line
    
    return ""


def _extract_abstract_from_pdf(doc: fitz.Document) -> str:
    """
    Extract abstract from PDF thesis
    Looks for section labeled 'Abstract' and extracts the content
    """
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n"
    
    # Common patterns for abstract section
    abstract_patterns = [
        r'(?i)abstract\s*\n+(.*?)(?=\n\s*(?:introduction|chapter|table of contents|keywords|1\.|i\.))',
        r'(?i)abstract\s*\n+(.*?)(?=\n{3,})',
        r'(?i)abstract[:\s]*(.*?)(?=\n\s*(?:introduction|keywords))',
    ]
    
    for pattern in abstract_patterns:
        match = re.search(pattern, full_text, re.DOTALL)
        if match:
            abstract = match.group(1).strip()
            # Clean up the abstract
            abstract = ' '.join(abstract.split())
            if len(abstract) > 100:  # Reasonable abstract length
                return abstract[:2000]  # Cap at 2000 chars
    
    return ""


def extract_text_from_pdf(pdf_path: str) -> Tuple[str, Dict]:
    """
    Extract text and metadata from PDF using PyMuPDF
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Tuple of (full_text, metadata_dict)
        
    Raises:
        PDFExtractionError: If text extraction fails
    """
    try:
        doc = fitz.open(pdf_path)
        
        # Extract metadata
        title = _extract_title_from_pdf(doc)
        abstract = _extract_abstract_from_pdf(doc)
        
        # Extract full text
        full_text = ""
        pages_text = []
        
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")
            pages_text.append({
                "page": page_num + 1,
                "text": page_text
            })
            full_text += page_text + "\n\n"
        
        doc.close()
        
        if not full_text.strip():
            raise PDFExtractionError("No text could be extracted from the PDF. It may be scanned/image-based.")
        
        metadata = {
            "title": title,
            "abstract": abstract,
            "page_count": len(pages_text),
            "filename": os.path.basename(pdf_path),
            "pages": pages_text
        }
        
        logger.info(f"Extracted {len(full_text)} characters from {metadata['page_count']} pages")
        return full_text, metadata
        
    except fitz.FileDataError as e:
        raise PDFExtractionError(f"Invalid or corrupted PDF file: {e}")
    except Exception as e:
        raise PDFExtractionError(f"PDF extraction failed: {e}")


def check_duplicate(title: str, content: str, allow_duplicate: bool = False) -> Tuple[bool, Optional[Dict]]:
    """
    Check if document already exists in the system
    
    Args:
        title: Document title
        content: Full document text
        allow_duplicate: If True, skip duplicate check
        
    Returns:
        Tuple of (is_duplicate, existing_document_info)
    """
    if allow_duplicate:
        return False, None
    
    metadata = _load_document_metadata()
    
    # Check by content hash (most reliable)
    content_hash = _compute_content_hash(content)
    if content_hash in metadata.get("content_hashes", {}):
        existing = metadata["content_hashes"][content_hash]
        logger.warning(f"Duplicate detected by content hash: {existing['filename']}")
        return True, existing
    
    # Check by title hash (for quick detection)
    if title:
        title_hash = _compute_title_hash(title)
        if title_hash in metadata.get("title_hashes", {}):
            existing = metadata["title_hashes"][title_hash]
            logger.warning(f"Duplicate detected by title: {existing['filename']}")
            return True, existing
    
    return False, None


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    Split text into chunks for embedding
    
    Uses RecursiveCharacterTextSplitter which is ideal for academic text:
    - Tries to split on paragraphs, then sentences, then words
    - Maintains semantic coherence within chunks
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    return splitter.split_text(text)


def get_embeddings():
    """Get the embeddings model matching the existing index"""
    # Match the embedding model used in rag_service.py
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )


def add_to_index(
    chunks: List[str],
    metadata: Dict,
    title: str,
    url: str = "",
    department: str = "",
    year: str = ""
) -> int:
    """
    Add document chunks to the existing FAISS index
    
    Args:
        chunks: List of text chunks to embed
        metadata: Document metadata
        title: Thesis title
        url: Google Drive URL (optional)
        department: Department/College (optional)
        year: Publication year (optional)
        
    Returns:
        Number of chunks added
    """
    embeddings = get_embeddings()
    
    # Create Document objects with metadata
    documents = []
    for i, chunk in enumerate(chunks):
        doc_metadata = {
            "source": metadata.get("filename", "uploaded_document"),
            "title": title,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "department": department,
            "year": year,
            "url": url,
            "upload_date": datetime.now().isoformat(),
        }
        documents.append(Document(page_content=chunk, metadata=doc_metadata))
    
    # Also create a document for the abstract if available
    if metadata.get("abstract"):
        abstract_doc = Document(
            page_content=metadata["abstract"],
            metadata={
                "source": metadata.get("filename", "uploaded_document"),
                "title": title,
                "content_type": "abstract",
                "department": department,
                "year": year,
                "url": url,
                "upload_date": datetime.now().isoformat(),
            }
        )
        documents.insert(0, abstract_doc)  # Prioritize abstract
    
    index_path = os.path.join(INDEX_DIR, "index.faiss")
    
    if os.path.exists(index_path):
        # Load existing index and merge
        logger.info("Loading existing FAISS index...")
        existing_vs = FAISS.load_local(
            INDEX_DIR, 
            embeddings, 
            allow_dangerous_deserialization=True
        )
        
        # Create new vectorstore from documents
        logger.info(f"Creating embeddings for {len(documents)} chunks...")
        new_vs = FAISS.from_documents(documents, embeddings)
        
        # Merge indices
        logger.info("Merging with existing index...")
        existing_vs.merge_from(new_vs)
        
        # Save merged index
        existing_vs.save_local(INDEX_DIR)
        logger.info("Merged index saved successfully")
    else:
        # Create new index
        logger.info(f"Creating new FAISS index with {len(documents)} chunks...")
        vs = FAISS.from_documents(documents, embeddings)
        vs.save_local(INDEX_DIR)
        logger.info("New index created and saved")
    
    return len(documents)


def update_title_url_file(title: str, url: str, department: str = ""):
    """
    Append new thesis to the data_title_url.txt file
    """
    title_url_file = os.path.join(INDEX_DIR, "data_title_url.txt")
    
    try:
        # Read existing content to get the next number
        existing_count = 0
        if os.path.exists(title_url_file):
            with open(title_url_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Count existing entries
                existing_count = len(re.findall(r'^\d+\.', content, re.MULTILINE))
        
        # Append new entry
        with open(title_url_file, 'a', encoding='utf-8') as f:
            entry = f"\n\n{existing_count + 1}. {title.upper()}\n"
            if url:
                entry += f"url: {url}\n"
            f.write(entry)
        
        logger.info(f"Added entry #{existing_count + 1} to data_title_url.txt")
        
    except IOError as e:
        logger.error(f"Could not update title_url file: {e}")


def update_abstract_file(title: str, abstract: str):
    """
    Append new abstract to the data_abstract.txt file
    """
    abstract_file = os.path.join(INDEX_DIR, "data_abstract.txt")
    
    try:
        with open(abstract_file, 'a', encoding='utf-8') as f:
            entry = f"\n\n{'='*80}\nTitle: {title}\n{'='*80}\n{abstract}\n"
            f.write(entry)
        
        logger.info(f"Added abstract for '{title}' to data_abstract.txt")
        
    except IOError as e:
        logger.error(f"Could not update abstract file: {e}")


def process_pdf_upload(
    file,
    filename: str,
    title: str = "",
    url: str = "",
    department: str = "",
    year: str = "",
    allow_duplicate: bool = False,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> Dict:
    """
    Main function to process a PDF upload
    
    Args:
        file: File object from Flask request
        filename: Original filename
        title: Thesis title (optional, will be extracted if not provided)
        url: Google Drive URL
        department: Department/College
        year: Publication year
        allow_duplicate: If True, allow re-uploading existing documents
        chunk_size: Size of text chunks for embedding
        chunk_overlap: Overlap between chunks
        
    Returns:
        Dict with upload results
        
    Raises:
        DuplicateDocumentError: If document already exists and allow_duplicate is False
        PDFExtractionError: If PDF extraction fails
    """
    import tempfile
    from werkzeug.utils import secure_filename
    
    # Secure the filename
    safe_filename = secure_filename(filename)
    
    # NOTE: PDF files are NOT saved permanently to save storage costs
    # We use a temporary file for processing, then delete it after indexing
    # The document metadata is still saved and displayed in UI
    # Only the vector embeddings are stored in the FAISS index
    
    # Save to temp file for processing
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    filepath = temp_file.name
    file.save(filepath)
    temp_file.close()
    logger.info(f"Saved uploaded file to temp: {filepath}")
    
    # COMMENTED OUT: Permanent file storage (to save database/storage costs)
    # Uncomment below lines if you want to save PDF files permanently
    # filepath = os.path.join(UPLOAD_DIR, safe_filename)
    # file.save(filepath)
    # logger.info(f"Saved uploaded file to {filepath}")
    
    try:
        # Extract text and metadata
        full_text, pdf_metadata = extract_text_from_pdf(filepath)
        
        # Use provided title or extracted title
        final_title = title.strip() if title else pdf_metadata.get("title", "")
        if not final_title:
            final_title = os.path.splitext(safe_filename)[0]  # Use filename as fallback
        
        # Check for duplicates
        is_duplicate, existing_doc = check_duplicate(final_title, full_text, allow_duplicate)
        
        if is_duplicate:
            # Clean up temp file
            if os.path.exists(filepath):
                os.remove(filepath)
            raise DuplicateDocumentError(
                f"This document appears to already exist in the system. "
                f"Previously uploaded as: {existing_doc.get('filename', 'Unknown')} "
                f"on {existing_doc.get('upload_date', 'Unknown date')}. "
                f"If you want to upload it anyway, check 'Allow duplicate'."
            )
        
        # Chunk the text
        chunks = chunk_text(full_text, chunk_size, chunk_overlap)
        logger.info(f"Created {len(chunks)} chunks from document")
        
        # Add to FAISS index
        docs_added = add_to_index(
            chunks=chunks,
            metadata=pdf_metadata,
            title=final_title,
            url=url,
            department=department,
            year=year
        )
        
        # Update auxiliary files
        update_title_url_file(final_title, url, department)
        
        if pdf_metadata.get("abstract"):
            update_abstract_file(final_title, pdf_metadata["abstract"])
        
        # Save document metadata for future duplicate detection
        doc_metadata = _load_document_metadata()
        
        content_hash = _compute_content_hash(full_text)
        title_hash = _compute_title_hash(final_title)
        
        doc_record = {
            "filename": safe_filename,
            "title": final_title,
            "department": department,
            "year": year,
            "url": url,
            "upload_date": datetime.now().isoformat(),
            "chunks": len(chunks),
            "pages": pdf_metadata.get("page_count", 0)
        }
        
        doc_metadata["documents"].append(doc_record)
        doc_metadata["content_hashes"][content_hash] = doc_record
        if final_title:
            doc_metadata["title_hashes"][title_hash] = doc_record
        
        _save_document_metadata(doc_metadata)
        
        # Clean up temp file after successful processing
        # PDF is now indexed in FAISS, no need to keep the file
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Cleaned up temp file: {filepath}")
        
        return {
            "success": True,
            "filename": safe_filename,
            "title": final_title,
            "abstract": pdf_metadata.get("abstract", "")[:500] + "..." if len(pdf_metadata.get("abstract", "")) > 500 else pdf_metadata.get("abstract", ""),
            "pages": pdf_metadata.get("page_count", 0),
            "chunks": len(chunks),
            "documents_added": docs_added,
            "message": f"Successfully uploaded and indexed '{final_title}' ({docs_added} document chunks)"
        }
        
    except (DuplicateDocumentError, PDFExtractionError):
        # Clean up on known errors
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    except Exception as e:
        # Clean up on unexpected errors
        if os.path.exists(filepath):
            os.remove(filepath)
        logger.error(f"Upload processing failed: {e}")
        raise


def get_uploaded_documents() -> List[Dict]:
    """Get list of all uploaded documents"""
    metadata = _load_document_metadata()
    return metadata.get("documents", [])


def delete_document(filename: str) -> bool:
    """
    Delete a document from the system
    Note: This removes metadata but doesn't remove from FAISS index
    (FAISS doesn't support deletion well - would need full rebuild)
    
    Since PDFs are not saved permanently (only indexed), this only removes metadata.
    The vectors remain in FAISS until a full index rebuild.
    """
    metadata = _load_document_metadata()
    
    # Find and remove document
    doc_to_remove = None
    for doc in metadata["documents"]:
        if doc["filename"] == filename:
            doc_to_remove = doc
            break
    
    if not doc_to_remove:
        return False
    
    metadata["documents"].remove(doc_to_remove)
    
    # Remove from hash lookups
    content_hashes_to_remove = [
        h for h, d in metadata.get("content_hashes", {}).items() 
        if d.get("filename") == filename
    ]
    for h in content_hashes_to_remove:
        del metadata["content_hashes"][h]
    
    title_hashes_to_remove = [
        h for h, d in metadata.get("title_hashes", {}).items() 
        if d.get("filename") == filename
    ]
    for h in title_hashes_to_remove:
        del metadata["title_hashes"][h]
    
    _save_document_metadata(metadata)
    
    # COMMENTED OUT: PDF file deletion (files are not saved permanently)
    # Uncomment if you enable permanent PDF storage
    # filepath = os.path.join(UPLOAD_DIR, filename)
    # if os.path.exists(filepath):
    #     os.remove(filepath)
    
    logger.info(f"Deleted document metadata: {filename}")
    return True
