"""PDF to image conversion using pdf2image (Poppler) or PyMuPDF."""

import io
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

HAS_PYMUPDF = False
try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    pass

HAS_PDF2IMAGE = False
try:
    from pdf2image import convert_from_path, pdfinfo_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    pass


class PDFConverter:
    """Convert PDF pages to PIL Images."""

    def __init__(self):
        self.method: Optional[str] = None
        if HAS_PYMUPDF:
            self.method = "pymupdf"
        elif HAS_PDF2IMAGE:
            self.method = "pdf2image"

        if self.method:
            logger.info("PDF backend: %s", self.method)
        else:
            logger.warning("No PDF backend available. Install PyMuPDF or pdf2image.")

    def get_page_count(self, pdf_path: str) -> int:
        pdf_path = str(pdf_path)
        if self.method == "pymupdf":
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        if self.method == "pdf2image":
            try:
                info = pdfinfo_from_path(pdf_path)
                return info.get("Pages", 0)
            except Exception:
                return 0
        return 0

    def convert(
        self,
        pdf_path: str,
        dpi: int = 300,
        output_dir: Optional[Path] = None,
    ) -> List[Tuple[int, Image.Image]]:
        """Convert all pages of a PDF to images.

        Returns list of (page_number, PIL.Image) tuples (1-indexed).
        If output_dir is provided, also saves images as PNG files.
        """
        if not self.method:
            raise RuntimeError(
                "No PDF library available. Install PyMuPDF or pdf2image."
            )

        pdf_path = str(pdf_path)
        total = self.get_page_count(pdf_path)
        results: List[Tuple[int, Image.Image]] = []

        if self.method == "pymupdf":
            doc = fitz.open(pdf_path)
            for page_num in range(1, total + 1):
                page = doc[page_num - 1]
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                results.append((page_num, img))
            doc.close()

        elif self.method == "pdf2image":
            for page_num in range(1, total + 1):
                images = convert_from_path(
                    pdf_path, dpi=dpi, first_page=page_num, last_page=page_num
                )
                if images:
                    results.append((page_num, images[0]))

        # Save to disk if output_dir specified
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(pdf_path).stem
            for page_num, img in results:
                out_path = output_dir / f"{stem}_page_{page_num:03d}.png"
                img.save(str(out_path), "PNG")

        logger.info("Converted %d pages from %s", len(results), pdf_path)
        return results
