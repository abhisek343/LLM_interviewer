# LLM_interviewer/server/app/services/resume_parser.py

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import io

# Import necessary parsing libraries (ensure they are in requirements.txt)
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
    logging.warning("pypdf2 library not found. PDF parsing will be unavailable.")

try:
    import docx # python-docx library
except ImportError:
    docx = None
    logging.warning("python-docx library not found. DOCX parsing will be unavailable.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResumeParserError(Exception):
    """Custom exception for resume parsing errors."""
    pass

async def parse_resume(file_path: Path) -> Optional[str]:
    """
    Parses the text content from a resume file (PDF or DOCX).

    Args:
        file_path: The Path object pointing to the resume file.

    Returns:
        The extracted text content as a string, or None if parsing fails
        or the file type is unsupported.

    Raises:
        ResumeParserError: If a known parsing issue occurs.
        FileNotFoundError: If the file_path does not exist.
    """
    if not file_path.is_file():
        logger.error(f"Resume file not found at path: {file_path}")
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    file_extension = file_path.suffix.lower()
    logger.info(f"Attempting to parse resume file: {file_path} (type: {file_extension})")

    try:
        if file_extension == ".pdf":
            if not PyPDF2:
                logger.error("Cannot parse PDF: pypdf2 library is not installed.")
                raise ResumeParserError("PDF parsing library (pypdf2) not available.")
            return await _parse_pdf(file_path)
        elif file_extension == ".docx":
            if not docx:
                logger.error("Cannot parse DOCX: python-docx library is not installed.")
                raise ResumeParserError("DOCX parsing library (python-docx) not available.")
            return await _parse_docx(file_path)
        elif file_extension == ".doc":
            # Handling .doc is complex and often requires external tools like antiword or LibreOffice.
            # It's generally recommended to ask users to upload PDF or DOCX.
            logger.warning(f"Parsing '.doc' files is not directly supported. File: {file_path}")
            return None # Or raise ResumeParserError("Unsupported file type: .doc")
        else:
            logger.warning(f"Unsupported resume file type: {file_extension}. File: {file_path}")
            return None # Or raise ResumeParserError(f"Unsupported file type: {file_extension}")

    except FileNotFoundError: # Should be caught above, but as safety
        raise
    except ResumeParserError: # Re-raise specific parsing errors
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during parsing of {file_path}: {e}", exc_info=True)
        raise ResumeParserError(f"Failed to parse resume file {file_path.name} due to an unexpected error.") from e


async def _parse_pdf(file_path: Path) -> Optional[str]:
    """Helper function to parse PDF files using PyPDF2."""
    text_content = ""
    try:
        with file_path.open("rb") as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(reader.pages)
            logger.info(f"Parsing PDF file '{file_path.name}' with {num_pages} pages.")
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                text_content += page.extract_text() or "" # Add extracted text, handle None
        logger.info(f"Successfully extracted text from PDF: {file_path.name}")
        return text_content.strip() if text_content else None
    except PyPDF2.errors.PdfReadError as e:
        logger.error(f"PyPDF2 error reading PDF {file_path.name}: {e}")
        raise ResumeParserError(f"Invalid or corrupted PDF file: {file_path.name}") from e
    except Exception as e:
        logger.error(f"Error parsing PDF {file_path.name}: {e}", exc_info=True)
        raise ResumeParserError(f"Failed to parse PDF {file_path.name}") from e


async def _parse_docx(file_path: Path) -> Optional[str]:
    """Helper function to parse DOCX files using python-docx."""
    try:
        document = docx.Document(file_path)
        logger.info(f"Parsing DOCX file: {file_path.name}")
        full_text = [para.text for para in document.paragraphs]
        content = '\n'.join(full_text)
        logger.info(f"Successfully extracted text from DOCX: {file_path.name}")
        return content.strip() if content else None
    except Exception as e:
        # python-docx can raise various errors (e.g., PackageNotFoundError for corrupted files)
        logger.error(f"Error parsing DOCX {file_path.name}: {e}", exc_info=True)
        raise ResumeParserError(f"Failed to parse DOCX file {file_path.name}. It might be corrupted or not a valid DOCX.") from e

# --- Potential Future Enhancements ---
# async def extract_entities(text: str) -> Dict[str, Any]:
#     """Placeholder for extracting structured data (skills, experience years, etc.) using NLP/LLM."""
#     logger.info("Extracting entities from resume text (Placeholder)...")
#     # Add NLP logic here (e.g., using spaCy, NLTK, or another LLM call)
#     return {"skills": [], "experience_years": None, "summary": text[:500]} # Example placeholder