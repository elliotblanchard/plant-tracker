"""ArUCO marker detection for spatial calibration anchors.

Detects ArUCO markers (DICT_4X4_50) in camera images to provide anchor
points for ruler ROI and grey scale ROI positioning, replacing hardcoded
coordinates.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ArucoMarker:
    """A single detected ArUCO marker."""

    id: int
    corners: np.ndarray  # shape (4, 2) — four corner points
    center: tuple[int, int]


def detect_aruco_markers(image: np.ndarray) -> list[ArucoMarker]:
    """Detect all ArUCO markers (DICT_4X4_50) in the image.

    Args:
        image: BGR image (NumPy array).

    Returns:
        List of ``ArucoMarker`` instances, one per detected marker.
    """
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    corners_list, ids, _ = detector.detectMarkers(image)

    if ids is None or len(ids) == 0:
        logger.info("No ArUCO markers detected")
        return []

    markers: list[ArucoMarker] = []
    for i, marker_id in enumerate(ids.flatten()):
        corners = corners_list[i][0]  # shape (4, 2)
        cx = int(np.mean(corners[:, 0]))
        cy = int(np.mean(corners[:, 1]))
        markers.append(ArucoMarker(id=int(marker_id), corners=corners, center=(cx, cy)))
        logger.debug("ArUCO marker %d at (%d, %d)", marker_id, cx, cy)

    logger.info("Detected %d ArUCO marker(s): %s", len(markers), [m.id for m in markers])
    return markers


def get_marker_by_id(markers: list[ArucoMarker], marker_id: int) -> ArucoMarker | None:
    """Look up a specific marker by its ID.

    Args:
        markers: List of detected markers.
        marker_id: The ArUCO ID to find (e.g. 0 for ruler, 1 for grey scale).

    Returns:
        The matching ``ArucoMarker``, or ``None`` if not found.
    """
    for m in markers:
        if m.id == marker_id:
            return m
    return None
