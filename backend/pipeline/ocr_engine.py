"""OCR engine using Tesseract. English-focused for financial documents."""

import io
import logging
from typing import Any, Dict, List, Optional

from PIL import Image

logger = logging.getLogger(__name__)

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available")


class OCREngine:
    """OCR engine with configurable language and confidence filtering."""

    LANG_MAP = {
        "en": "eng",
        "eng": "eng",
        "ur": "urd",
        "urd": "urd",
        "ar": "ara",
        "ara": "ara",
    }

    def __init__(self, languages: Optional[List[str]] = None, min_confidence: int = 30):
        self.languages = languages or ["en"]
        self.min_confidence = min_confidence
        self.tesseract_langs = "+".join(
            self.LANG_MAP.get(lang, lang) for lang in self.languages
        )

    def extract_text(self, image_data: bytes) -> Dict[str, Any]:
        """Full OCR extraction with blocks, positions, and confidence.

        Returns dict with: text, blocks, confidence, block_count, error.
        """
        if not TESSERACT_AVAILABLE:
            return {"text": "", "blocks": [], "confidence": 0, "error": "Tesseract not available"}

        try:
            image = Image.open(io.BytesIO(image_data))
            if image.mode != "RGB":
                image = image.convert("RGB")

            config = "--psm 6 --oem 3"

            ocr_data = pytesseract.image_to_data(
                image, lang=self.tesseract_langs,
                output_type=pytesseract.Output.DICT, config=config,
            )

            blocks: List[Dict[str, Any]] = []
            confidences: List[int] = []

            for i in range(len(ocr_data["text"])):
                text = ocr_data["text"][i].strip()
                conf = int(ocr_data["conf"][i])
                if not text or conf < self.min_confidence:
                    continue
                blocks.append({
                    "text": text,
                    "confidence": conf / 100.0,
                    "bbox": {
                        "x": ocr_data["left"][i],
                        "y": ocr_data["top"][i],
                        "width": ocr_data["width"][i],
                        "height": ocr_data["height"][i],
                    },
                })
                confidences.append(conf)

            full_text = pytesseract.image_to_string(
                image, lang=self.tesseract_langs, config=config
            )
            avg_conf = sum(confidences) / len(confidences) if confidences else 0

            return {
                "text": full_text.strip(),
                "blocks": blocks,
                "confidence": avg_conf / 100.0,
                "block_count": len(blocks),
            }

        except Exception as e:
            logger.error("OCR failed: %s", e)
            return {"text": "", "blocks": [], "confidence": 0, "error": str(e)}

    def extract_text_simple(self, image_data: bytes) -> str:
        """Simple text extraction -- returns just the text string."""
        return self.extract_text(image_data).get("text", "")

    def extract_from_image(self, image: Image.Image) -> Dict[str, Any]:
        """Extract text from a PIL Image directly."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return self.extract_text(buf.getvalue())
