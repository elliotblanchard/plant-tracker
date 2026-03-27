"""Lens distortion calibration using ChArUco board images.

Computes camera intrinsic matrix and distortion coefficients from a set
of ChArUco board images, saves them to a JSON file, and provides an
``undistort_image`` function that the main pipeline calls on every frame.

Typical workflow
----------------
1. Capture 10-20 images of a ChArUco board at varied positions/angles.
2. Run ``python -m scripts.calibrate_lens --image-dir ../distortion-images``
3. The calibration is saved to ``<project_root>/calibration/lens_calibration.json``.
4. The pipeline automatically loads the calibration and undistorts every
   image before analysis.

If the lens or camera changes, simply re-run step 1-2 with fresh images.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


@dataclass
class LensCalibration:
    """Stores the camera intrinsic matrix and distortion coefficients."""

    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    image_size: tuple[int, int]  # (width, height)
    reprojection_error: float
    num_images_used: int

    # Pre-computed undistort maps for fast remapping
    _map1: np.ndarray | None = None
    _map2: np.ndarray | None = None

    def _build_maps(self) -> None:
        """Build the undistortion remap lookup tables (computed once)."""
        w, h = self.image_size
        new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (w, h), alpha=0, newImgSize=(w, h)
        )
        self._map1, self._map2 = cv2.initUndistortRectifyMap(
            self.camera_matrix,
            self.dist_coeffs,
            None,
            new_camera_matrix,
            (w, h),
            cv2.CV_16SC2,
        )

    def undistort(self, image: np.ndarray) -> np.ndarray:
        """Remove lens distortion from an image.

        Uses pre-computed remap tables for efficiency (~5-10 ms per frame).
        If the image size differs from the calibration size, falls back to
        ``cv2.undistort`` which is slightly slower but handles any resolution.
        """
        h, w = image.shape[:2]
        if (w, h) != self.image_size:
            logger.warning(
                "Image size (%d x %d) differs from calibration size %s. "
                "Using cv2.undistort fallback.",
                w,
                h,
                self.image_size,
            )
            return cv2.undistort(image, self.camera_matrix, self.dist_coeffs)

        if self._map1 is None or self._map2 is None:
            self._build_maps()
        return cv2.remap(image, self._map1, self._map2, cv2.INTER_LINEAR)


def save_calibration(calibration: LensCalibration, path: Path) -> None:
    """Persist calibration data to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "camera_matrix": calibration.camera_matrix.tolist(),
        "dist_coeffs": calibration.dist_coeffs.tolist(),
        "image_size": list(calibration.image_size),
        "reprojection_error": calibration.reprojection_error,
        "num_images_used": calibration.num_images_used,
    }
    path.write_text(json.dumps(data, indent=2))
    logger.info("Calibration saved to %s", path)


def load_calibration(path: Path) -> LensCalibration | None:
    """Load calibration from a JSON file. Returns None if the file is missing."""
    if not path.is_file():
        logger.debug("No calibration file at %s", path)
        return None

    data = json.loads(path.read_text())
    cal = LensCalibration(
        camera_matrix=np.array(data["camera_matrix"], dtype=np.float64),
        dist_coeffs=np.array(data["dist_coeffs"], dtype=np.float64),
        image_size=tuple(data["image_size"]),
        reprojection_error=data["reprojection_error"],
        num_images_used=data["num_images_used"],
    )
    logger.info(
        "Loaded lens calibration (reproj error=%.4f px, %d images, size=%s)",
        cal.reprojection_error,
        cal.num_images_used,
        cal.image_size,
    )
    return cal


def calibrate_from_charuco(
    image_dir: Path,
    squares_x: int = 9,
    squares_y: int = 6,
    square_length_mm: float = 37.5,
    marker_length_mm: float = 28.125,
    dictionary_name: str = "DICT_4X4_50",
) -> LensCalibration:
    """Compute lens calibration from ChArUco board images.

    Args:
        image_dir: Directory containing calibration images.
        squares_x: Number of chessboard squares in the X direction.
        squares_y: Number of chessboard squares in the Y direction.
        square_length_mm: Physical side length of each chessboard square (mm).
        marker_length_mm: Physical side length of each ArUco marker (mm).
        dictionary_name: ArUco dictionary name (e.g. "DICT_4X4_50").

    Returns:
        A ``LensCalibration`` with the computed parameters.

    Raises:
        RuntimeError: If fewer than 3 images yield usable corners.
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary_name))
    charuco_board = cv2.aruco.CharucoBoard(
        (squares_x, squares_y), square_length_mm, marker_length_mm, aruco_dict
    )
    charuco_board.setLegacyPattern(True)
    charuco_detector = cv2.aruco.CharucoDetector(charuco_board)

    all_charuco_corners: list[np.ndarray] = []
    all_charuco_ids: list[np.ndarray] = []
    image_size: tuple[int, int] | None = None

    image_paths = sorted(
        p for p in image_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not image_paths:
        raise RuntimeError(f"No images found in {image_dir}")

    logger.info("Processing %d calibration images from %s", len(image_paths), image_dir)

    for img_path in image_paths:
        image = cv2.imread(str(img_path))
        if image is None:
            logger.warning("Cannot read image: %s — skipping", img_path)
            continue

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        if image_size is None:
            image_size = (w, h)

        charuco_corners, charuco_ids, marker_corners, marker_ids = (
            charuco_detector.detectBoard(gray)
        )

        n_markers = 0 if marker_ids is None else len(marker_ids)
        n_corners = 0 if charuco_ids is None else len(charuco_ids)

        if n_corners < 6:
            logger.warning(
                "%s: only %d Charuco corners found (%d markers) — skipping (need ≥6)",
                img_path.name,
                n_corners,
                n_markers,
            )
            continue

        all_charuco_corners.append(charuco_corners)
        all_charuco_ids.append(charuco_ids)
        logger.info(
            "%s: %d ArUco markers → %d Charuco corners ✓",
            img_path.name,
            n_markers,
            n_corners,
        )

    if len(all_charuco_corners) < 3:
        raise RuntimeError(
            f"Only {len(all_charuco_corners)} usable images found — "
            "need at least 3 for reliable calibration. "
            "Check board parameters (squares_x, squares_y, dictionary)."
        )

    logger.info(
        "Running calibration with %d usable images...", len(all_charuco_corners)
    )

    all_obj_points: list[np.ndarray] = []
    all_img_points: list[np.ndarray] = []

    for charuco_corners, charuco_ids in zip(all_charuco_corners, all_charuco_ids):
        obj_points, img_points = charuco_board.matchImagePoints(
            charuco_corners, charuco_ids
        )
        all_obj_points.append(obj_points)
        all_img_points.append(img_points)

    retval, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        all_obj_points,
        all_img_points,
        image_size,
        None,
        None,
    )

    calibration = LensCalibration(
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        image_size=image_size,
        reprojection_error=retval,
        num_images_used=len(all_charuco_corners),
    )

    logger.info(
        "Calibration complete — reprojection error: %.4f px (%d images)",
        retval,
        len(all_charuco_corners),
    )
    return calibration
