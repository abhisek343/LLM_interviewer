# LLM_interviewer/server/app/services/resume_parser.py

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import io

# --- MODIFIED: Import PdfReader from pypdf ---
try:
    # Use the correct library name from requirements.txt
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError # Import specific error if needed
    PYPDF_AVAILABLE = True
except ImportError:
    PdfReader = None
    PdfReadError = None # Define as None if import fails
    PYPDF_AVAILABLE = False
    # Updated warning message
    logging.warning("pypdf library not found. PDF parsing will be unavailable.")
# --- END MODIFIED IMPORT ---

try:
    import docx # python-docx library
    DOCX_AVAILABLE = True
except ImportError:
    docx = None
    DOCX_AVAILABLE = False
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
            # --- MODIFIED: Check for PYPDF_AVAILABLE ---
            if not PYPDF_AVAILABLE:
                logger.error("Cannot parse PDF: pypdf library is not installed.")
                # Updated error message
                raise ResumeParserError("PDF parsing library (pypdf) not available.")
            # --- END MODIFIED CHECK ---
            return await _parse_pdf(file_path) # Call updated function
        elif file_extension == ".docx":
            if not DOCX_AVAILABLE:
                logger.error("Cannot parse DOCX: python-docx library is not installed.")
                raise ResumeParserError("DOCX parsing library (python-docx) not available.")
            return await _parse_docx(file_path) # No changes needed here
        elif file_extension == ".doc":
            logger.warning(f"Parsing '.doc' files is not directly supported. File: {file_path}")
            return None
        else:
            logger.warning(f"Unsupported resume file type: {file_extension}. File: {file_path}")
            return None

    except FileNotFoundError: # Should be caught above, but as safety
        raise
    except ResumeParserError: # Re-raise specific parsing errors
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during parsing of {file_path}: {e}", exc_info=True)
        raise ResumeParserError(f"Failed to parse resume file {file_path.name} due to an unexpected error.") from e

# --- FUNCTION MODIFIED TO USE pypdf ---
async def _parse_pdf(file_path: Path) -> Optional[str]:
    """Helper function to parse PDF files using pypdf."""
    text_content = ""
    try:
        # pypdf uses PdfReader directly with the file path or a stream
        reader = PdfReader(file_path)
        num_pages = len(reader.pages)
        logger.info(f"Parsing PDF file '{file_path.name}' with {num_pages} pages using pypdf.")
        for page in reader.pages:
            # Concatenate text from each page
            extracted = page.extract_text()
            if extracted:
                text_content += extracted + "\n" # Add newline between pages

        logger.info(f"Successfully extracted text from PDF using pypdf: {file_path.name}")
        return text_content.strip() if text_content else None
    # Catch pypdf specific errors if available, or general exceptions
    except PdfReadError as e: # Catch specific pypdf error
        logger.error(f"pypdf error reading PDF {file_path.name}: {e}")
        raise ResumeParserError(f"Invalid or corrupted PDF file (pypdf): {file_path.name}") from e
    except Exception as e: # Catch other unexpected errors
        logger.error(f"Error parsing PDF {file_path.name} with pypdf: {e}", exc_info=True)
        raise ResumeParserError(f"Failed to parse PDF {file_path.name} using pypdf") from e
# --- END FUNCTION MODIFICATION ---


async def _parse_docx(file_path: Path) -> Optional[str]:
    """Helper function to parse DOCX files using python-docx."""
    # This function remains the same as it uses python-docx
    try:
        document = docx.Document(file_path)
        logger.info(f"Parsing DOCX file: {file_path.name}")
        full_text = [para.text for para in document.paragraphs]
        content = '\n'.join(full_text)
        logger.info(f"Successfully extracted text from DOCX: {file_path.name}")
        return content.strip() if content else None
    except Exception as e:
        logger.error(f"Error parsing DOCX {file_path.name}: {e}", exc_info=True)
        raise ResumeParserError(f"Failed to parse DOCX file {file_path.name}. It might be corrupted or not a valid DOCX.") from e