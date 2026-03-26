"""Image preprocessor for OCR optimization.

Supports two paths:
  1. OpenCV (cv2) -- full pipeline (deskew, denoise, CLAHE, adaptive threshold)
  2. PIL-only     -- basic contrast/denoise/binarize

Ported from DocEngine with minor adaptations for async pipeline.
"""

import io
import logging
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available. Using basic PIL preprocessing.")


class ImagePreprocessor:
    """Image preprocessing pipeline for OCR optimization."""

    def __init__(self, config=None):
        self.config = config or {}
        self.deskew = self.config.get("deskew", True)
        self.denoise = self.config.get("denoise", True)
        self.enhance_contrast = self.config.get("enhance_contrast", True)
        self.binarize = self.config.get("binarize", False)
        self.scale_factor = self.config.get("scale_factor", 2.0)

    def process(self, image_data: bytes) -> bytes:
        """Run image_data through preprocessing. Returns PNG bytes."""
        try:
            image = Image.open(io.BytesIO(image_data))
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Scale up small images only
            MIN_WIDTH = 2000
            MAX_PIXELS = 20_000_000
            if self.scale_factor != 1.0 and image.width < MIN_WIDTH:
                new_w = int(image.width * self.scale_factor)
                new_h = int(image.height * self.scale_factor)
                if new_w * new_h > MAX_PIXELS:
                    ratio = (MAX_PIXELS / (new_w * new_h)) ** 0.5
                    new_w = int(new_w * ratio)
                    new_h = int(new_h * ratio)
                image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

            if CV2_AVAILABLE:
                image = self._process_with_cv2(image)
            else:
                image = self._process_with_pil(image)

            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()

        except Exception as e:
            logger.error("Preprocessing failed: %s", e)
            return image_data

    def process_pil_image(self, image: Image.Image) -> Image.Image:
        """Process a PIL Image directly (avoids bytes round-trip)."""
        if image.mode != "RGB":
            image = image.convert("RGB")

        MIN_WIDTH = 2000
        MAX_PIXELS = 20_000_000
        if self.scale_factor != 1.0 and image.width < MIN_WIDTH:
            new_w = int(image.width * self.scale_factor)
            new_h = int(image.height * self.scale_factor)
            if new_w * new_h > MAX_PIXELS:
                ratio = (MAX_PIXELS / (new_w * new_h)) ** 0.5
                new_w = int(new_w * ratio)
                new_h = int(new_h * ratio)
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        if CV2_AVAILABLE:
            return self._process_with_cv2(image)
        return self._process_with_pil(image)

    def _process_with_pil(self, image: Image.Image) -> Image.Image:
        if self.enhance_contrast:
            image = ImageEnhance.Contrast(image).enhance(1.5)
            image = ImageEnhance.Sharpness(image).enhance(1.5)
        if self.denoise:
            image = image.filter(ImageFilter.MedianFilter(size=3))
        if self.binarize:
            image = image.convert("L")
            image = image.point(lambda x: 0 if x < 128 else 255, "1")
            image = image.convert("RGB")
        return image

    def _process_with_cv2(self, image: Image.Image) -> Image.Image:
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        if self.deskew:
            cv_image = self._deskew(cv_image)
        if self.denoise:
            cv_image = cv2.fastNlMeansDenoisingColored(cv_image, None, 10, 10, 7, 21)
        if self.enhance_contrast:
            lab = cv2.cvtColor(cv_image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            cv_image = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        if self.binarize:
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            cv_image = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2BGR)

        return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))

    def _deskew(self, image):
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
            if lines is not None:
                angles = []
                for line in lines[:20]:
                    _, theta = line[0]
                    angle = (theta * 180 / np.pi) - 90
                    if abs(angle) < 45:
                        angles.append(angle)
                if angles:
                    median_angle = np.median(angles)
                    if abs(median_angle) > 0.5:
                        h, w = image.shape[:2]
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                        image = cv2.warpAffine(
                            image, M, (w, h),
                            flags=cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_REPLICATE,
                        )
            return image
        except Exception as e:
            logger.warning("Deskew failed: %s", e)
            return image
