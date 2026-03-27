"""Compute lens distortion calibration from ChArUco board images.

Usage
-----
    cd backend
    python -m scripts.calibrate_lens --image-dir ../distortion-images

Optional flags
--------------
    --squares-x 9           ChArUco board columns
    --squares-y 6           ChArUco board rows
    --square-length 37.5    Square side length in mm
    --marker-length 28.125  ArUco marker side length in mm
    --dict DICT_4X4_50      ArUco dictionary name
    --output ../calibration/lens_calibration.json

The output JSON can be loaded by the analysis pipeline to undistort
every captured image before processing.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.lens_calibration import calibrate_from_charuco, save_calibration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute lens distortion calibration from ChArUco board images."
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        required=True,
        help="Directory containing ChArUco board calibration images.",
    )
    parser.add_argument(
        "--squares-x",
        type=int,
        default=9,
        help="Number of chessboard squares in the X direction (default: 9).",
    )
    parser.add_argument(
        "--squares-y",
        type=int,
        default=6,
        help="Number of chessboard squares in the Y direction (default: 6).",
    )
    parser.add_argument(
        "--square-length",
        type=float,
        default=37.5,
        help="Physical side length of each chessboard square in mm (default: 37.5).",
    )
    parser.add_argument(
        "--marker-length",
        type=float,
        default=28.125,
        help="Physical side length of each ArUco marker in mm (default: 28.125).",
    )
    parser.add_argument(
        "--dict",
        dest="dictionary",
        type=str,
        default="DICT_4X4_50",
        help="ArUco dictionary name (default: DICT_4X4_50).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for calibration JSON (default: <project>/calibration/lens_calibration.json).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent
    output_path = args.output or (
        project_root / "calibration" / "lens_calibration.json"
    )

    image_dir = args.image_dir
    if not image_dir.is_absolute():
        image_dir = Path.cwd() / image_dir
    image_dir = image_dir.resolve()

    if not image_dir.is_dir():
        logger.error("Image directory does not exist: %s", image_dir)
        sys.exit(1)

    print(f"\n{'='*60}")
    print("  Lens Distortion Calibration")
    print(f"{'='*60}")
    print(f"  Image directory : {image_dir}")
    print(f"  Board size      : {args.squares_x} × {args.squares_y} squares")
    print(f"  Square length   : {args.square_length} mm")
    print(f"  Marker length   : {args.marker_length} mm")
    print(f"  ArUco dictionary: {args.dictionary}")
    print(f"  Output          : {output_path}")
    print(f"{'='*60}\n")

    try:
        calibration = calibrate_from_charuco(
            image_dir=image_dir,
            squares_x=args.squares_x,
            squares_y=args.squares_y,
            square_length_mm=args.square_length,
            marker_length_mm=args.marker_length,
            dictionary_name=args.dictionary,
        )
    except RuntimeError as exc:
        logger.error("Calibration failed: %s", exc)
        sys.exit(1)

    save_calibration(calibration, output_path)

    print(f"\n{'='*60}")
    print("  Calibration Results")
    print(f"{'='*60}")
    print(f"  Images used       : {calibration.num_images_used}")
    print(
        f"  Image size        : {calibration.image_size[0]} × {calibration.image_size[1]}"
    )
    print(f"  Reprojection error: {calibration.reprojection_error:.4f} px")
    print(f"  Distortion coeffs : {calibration.dist_coeffs.ravel()}")
    print(f"  Saved to          : {output_path}")
    print(f"{'='*60}")

    if calibration.reprojection_error < 0.5:
        print("\n  ✓ Excellent calibration (error < 0.5 px)")
    elif calibration.reprojection_error < 1.0:
        print("\n  ✓ Good calibration (error < 1.0 px)")
    elif calibration.reprojection_error < 2.0:
        print("\n  ⚠ Acceptable calibration — consider retaking some images")
    else:
        print("\n  ✗ Poor calibration — retake images with better coverage")
    print()


if __name__ == "__main__":
    main()
