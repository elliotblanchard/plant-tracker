"""QR code detection and decoding using OpenCV.

Locates a QR code in the image and returns the decoded plant ID string.
Falls back gracefully if no QR code is found.
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def detect_qr_code(image: np.ndarray) -> str | None:
    """Detect and decode a QR code in the given BGR image.

    Tries OpenCV's QRCodeDetector first; if that fails, falls back to
    a contrast-enhanced version of the image.

    Args:
        image: BGR image as a NumPy array (as returned by cv2.imread).

    Returns:
        The decoded QR string (e.g. ``"plant-001"``), or ``None`` if no
        QR code could be found/decoded.
    """
    detector = cv2.QRCodeDetector()

    # First attempt: original image
    decoded, points, _ = detector.detectAndDecode(image)
    if decoded:
        logger.info("QR code detected: %s", decoded)
        return decoded

    # Second attempt: convert to grayscale and apply CLAHE for better contrast
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    # QRCodeDetector expects a 3-channel image
    enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    decoded, points, _ = detector.detectAndDecode(enhanced_bgr)
    if decoded:
        logger.info("QR code detected (enhanced): %s", decoded)
        return decoded

    # Third attempt: threshold-based binarization for difficult lighting
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    decoded, points, _ = detector.detectAndDecode(binary_bgr)
    if decoded:
        logger.info("QR code detected (binarized): %s", decoded)
        return decoded

    logger.warning("No QR code found in image")
    return None
