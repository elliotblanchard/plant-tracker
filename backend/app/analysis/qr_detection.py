"""QR code detection and decoding using OpenCV.

Locates QR codes in the image and returns decoded plant ID strings.
Supports both single-QR (backward compat) and multi-QR detection for
images containing multiple plants.

Uses multiple strategies: direct multi-detect, CLAHE, binarization,
and region-based scanning for difficult images.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QRResult:
    """A single detected QR code with position information."""

    data: str
    bbox: np.ndarray  # bounding box points
    center: tuple[int, int]


def detect_all_qr_codes(image: np.ndarray) -> list[QRResult]:
    """Detect and decode all QR codes in the given BGR image.

    Uses ``QRCodeDetector.detectAndDecodeMulti()`` with CLAHE and
    binarization fallbacks. If multi-detect fails, falls back to
    scanning image quadrants individually.

    Args:
        image: BGR image as a NumPy array.

    Returns:
        List of ``QRResult`` instances, one per detected QR code.
    """
    # Strategy 1: direct detectAndDecodeMulti
    results = _try_detect_multi(image)
    if len(results) >= 2:
        return results

    # Strategy 2: CLAHE enhanced multi
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    results = _try_detect_multi(enhanced_bgr)
    if len(results) >= 2:
        logger.info("QR codes detected via CLAHE multi-detect")
        return results

    # Strategy 3: binarization multi
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    results = _try_detect_multi(binary_bgr)
    if len(results) >= 2:
        logger.info("QR codes detected via binarization multi-detect")
        return results

    # Strategy 4: scan regions individually using single-detect
    # Try each image variant with region scanning
    logger.info("Multi-detect failed — falling back to region scanning")
    results = _scan_regions(image, enhanced_bgr, binary_bgr)
    if results:
        return results

    logger.warning("No QR codes found in image")
    return []


def _try_detect_multi(image: np.ndarray) -> list[QRResult]:
    """Attempt multi-QR detection on a single image variant."""
    detector = cv2.QRCodeDetector()

    retval, decoded_info, points, _ = detector.detectAndDecodeMulti(image)

    if not retval or points is None:
        return []

    results: list[QRResult] = []
    for i, data in enumerate(decoded_info):
        if not data:
            continue
        bbox = points[i]
        cx = int(np.mean(bbox[:, 0]))
        cy = int(np.mean(bbox[:, 1]))
        results.append(QRResult(data=data, bbox=bbox, center=(cx, cy)))
        logger.info("QR code detected: %s at (%d, %d)", data, cx, cy)

    return results


def _scan_regions(
    original: np.ndarray,
    enhanced: np.ndarray,
    binary: np.ndarray,
) -> list[QRResult]:
    """Scan overlapping regions of the image with single-detect.

    Divides the image into a grid of overlapping tiles and tries
    single QR detection on each tile with each image variant.
    Deduplicates results by QR data string.
    """
    h, w = original.shape[:2]
    detector = cv2.QRCodeDetector()

    # Use overlapping regions: 3x3 grid with 50% overlap
    tile_h = h // 2
    tile_w = w // 2
    step_h = h // 3
    step_w = w // 3

    found: dict[str, QRResult] = {}

    for img_variant, label in [(original, "orig"), (enhanced, "clahe"), (binary, "binary")]:
        for row_start in range(0, h - tile_h + 1, step_h):
            for col_start in range(0, w - tile_w + 1, step_w):
                tile = img_variant[row_start:row_start + tile_h, col_start:col_start + tile_w]
                data, bbox, _ = detector.detectAndDecode(tile)
                if data and data not in found:
                    if bbox is not None and len(bbox) > 0:
                        # Offset bbox back to full-image coordinates
                        offset_bbox = bbox[0].copy()
                        offset_bbox[:, 0] += col_start
                        offset_bbox[:, 1] += row_start
                        cx = int(np.mean(offset_bbox[:, 0]))
                        cy = int(np.mean(offset_bbox[:, 1]))
                    else:
                        cx = col_start + tile_w // 2
                        cy = row_start + tile_h // 2
                        offset_bbox = np.array([[cx, cy]])
                    found[data] = QRResult(data=data, bbox=offset_bbox, center=(cx, cy))
                    logger.info("QR code found via %s region scan: %s at (%d, %d)", label, data, cx, cy)

        # If we already found 2+, stop early
        if len(found) >= 2:
            break

    return list(found.values())


def detect_qr_code(image: np.ndarray) -> str | None:
    """Detect and decode a single QR code (backward compatible).

    Args:
        image: BGR image as a NumPy array.

    Returns:
        The decoded QR string, or ``None`` if no QR code found.
    """
    results = detect_all_qr_codes(image)
    if results:
        return results[0].data
    return None
