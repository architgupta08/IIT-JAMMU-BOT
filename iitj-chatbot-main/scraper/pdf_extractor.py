"""
pdf_extractor.py — Extract text from IIT Jammu PDF documents

Handles fee charts, admission brochures, circular notices etc.
Uses PyMuPDF (fitz) — free and excellent.

Run standalone:
  python pdf_extractor.py <pdf_url_or_path>

Or import:
  from pdf_extractor import extract_pdf_to_markdown
"""
import os
import re
import logging
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "../data/raw"))

# Important PDFs on IIT Jammu website
IMPORTANT_PDFS = [
    {
        "url": "https://www.iitjammu.ac.in/Programme/ugadmissions/2023/Institute%20Profile_2023.pdf",
        "name": "institute_profile_2023.md",
        "topic": "About IIT Jammu",
    },
    # Add more PDF URLs as discovered during crawl
]


def extract_pdf_to_markdown(source: str, output_name: Optional[str] = None) -> Optional[str]:
    """
    Extract text from a PDF file or URL and convert to Markdown.

    Args:
        source: File path or URL to PDF
        output_name: Output markdown filename (auto-generated if None)

    Returns:
        Extracted markdown text, or None on failure
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
        return None

    pdf_bytes = None

    # Load from URL or file
    if source.startswith("http"):
        try:
            resp = requests.get(source, timeout=30, headers={
                "User-Agent": "IITJammuChatbotResearcher/1.0"
            })
            resp.raise_for_status()
            pdf_bytes = resp.content
        except Exception as e:
            logger.warning(f"Failed to fetch PDF {source}: {e}")
            return None
    else:
        path = Path(source)
        if not path.exists():
            logger.warning(f"PDF file not found: {source}")
            return None
        pdf_bytes = path.read_bytes()

    # Parse PDF
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning(f"Failed to open PDF: {e}")
        return None

    lines = [
        f"# {doc.metadata.get('title', 'IIT Jammu Document')}",
        f"\n**Source:** {source}\n",
        f"**Pages:** {doc.page_count}\n",
        "---\n",
    ]

    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)

        # Extract text blocks with position info
        blocks = page.get_text("blocks")

        page_lines = [f"\n## Page {page_num + 1}\n"]

        for block in blocks:
            # block = (x0, y0, x1, y1, text, block_no, block_type)
            text = block[4].strip()
            if not text or len(text) < 2:
                continue

            # Heuristic: short lines at top = headings
            if len(text) < 80 and text.isupper():
                page_lines.append(f"\n### {text.title()}\n")
            elif len(text) < 100 and block[1] < 150:  # Near top of page
                page_lines.append(f"\n**{text}**\n")
            else:
                page_lines.append(text)

        lines.extend(page_lines)

    doc.close()

    # Clean up
    content = "\n".join(lines)
    content = re.sub(r"\n{4,}", "\n\n\n", content)  # Max 3 consecutive newlines
    content = re.sub(r"[ \t]{3,}", " ", content)    # Collapse spaces

    # Save to file
    if output_name:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_path = RAW_DATA_DIR / output_name
        out_path.write_text(content, encoding="utf-8")
        logger.info(f"Saved PDF extraction: {out_path}")

    return content


def extract_all_important_pdfs():
    """Extract all known important PDFs from IIT Jammu."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for item in IMPORTANT_PDFS:
        logger.info(f"Extracting PDF: {item['url']}")
        result = extract_pdf_to_markdown(item["url"], item["name"])
        if result:
            logger.info(f"  ✅ Success: {item['name']} ({len(result)} chars)")
        else:
            logger.warning(f"  ⚠️  Failed: {item['url']}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) > 1:
        result = extract_pdf_to_markdown(sys.argv[1], "extracted_pdf.md")
        if result:
            print(f"Extracted {len(result)} characters")
            print(result[:500])
    else:
        extract_all_important_pdfs()
