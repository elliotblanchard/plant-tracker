#!/usr/bin/env python3
"""Visual diagnostic tool for the Plant Tracker analysis pipeline.

Runs each pipeline module independently on every image in the test directory
and produces:
  - Annotated overlay images saved to output/diagnostics/
  - A console summary table

Usage:
    cd backend
    python scripts/diagnose.py --image-dir ../test-plant
    python scripts/diagnose.py --image-dir ../test-plant --step qr
    python scripts/diagnose.py --image-dir ../test-plant --step ruler
    python scripts/diagnose.py --image-dir ../test-plant --step seg
    python scripts/diagnose.py --image-dir ../test-plant --step all
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.color_metrics import extract_color_metrics
from app.analysis.health_score import compute_health_score, is_overgrown
from app.analysis.qr_detection import detect_qr_code
from app.analysis.segmentation import segment_plant
from app.analysis.size_calibration import calibrate_from_ruler
from app.config import settings

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "diagnostics"


def collect_images(image_dir: Path) -> list[Path]:
    patterns = ["Plant_*.jpg", "Plant_*.jpeg", "Plant_*.png",
                "plant_*.jpg", "plant_*.jpeg", "plant_*.png"]
    files: list[Path] = []
    for p in patterns:
        files.extend(image_dir.glob(p))
    return sorted(set(files), key=lambda f: f.name)


# ── QR Diagnostic ────────────────────────────────────────────────────

def diagnose_qr(images: list[Path]) -> list[dict]:
    """Run QR detection on each image. Save annotated overlay."""
    qr_dir = OUTPUT_DIR / "qr"
    qr_dir.mkdir(parents=True, exist_ok=True)
    results = []

    detector = cv2.QRCodeDetector()

    for img_path in images:
        image = cv2.imread(str(img_path))
        decoded = detect_qr_code(image)

        # Also get bounding box for visualization
        overlay = image.copy()
        _, points, _ = detector.detectAndDecode(image)

        if points is not None and len(points) > 0:
            pts = points[0].astype(int)
            for i in range(len(pts)):
                cv2.line(overlay, tuple(pts[i]), tuple(pts[(i + 1) % len(pts)]),
                         (0, 255, 0), 3)
            # Label
            label = decoded if decoded else "DECODE FAILED"
            cv2.putText(overlay, label, (pts[0][0], pts[0][1] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        else:
            cv2.putText(overlay, "QR NOT FOUND", (30, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

        out_path = qr_dir / f"{img_path.stem}_qr.jpg"
        cv2.imwrite(str(out_path), overlay)
        results.append({"file": img_path.name, "qr_decoded": decoded, "overlay": str(out_path)})

    return results


# ── Ruler Diagnostic ──────────────────────────────────────────────────

def diagnose_ruler(images: list[Path]) -> list[dict]:
    """Run ruler calibration on each image. Save overlay with tick marks."""
    ruler_dir = OUTPUT_DIR / "ruler"
    ruler_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for img_path in images:
        image = cv2.imread(str(img_path))
        h, w = image.shape[:2]

        # Run calibration
        cal = calibrate_from_ruler(image)

        overlay = image.copy()

        # If ROI is configured, draw it
        roi = settings.ruler_roi
        if roi:
            rx, ry, rw, rh = roi
            cv2.rectangle(overlay, (rx, ry), (rx + rw, ry + rh), (255, 165, 0), 2)
            cv2.putText(overlay, "Ruler ROI", (rx, ry - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)

        # Annotate with result
        label = f"px/mm={cal.px_per_mm:.2f}  ticks={cal.tick_count}" if cal.px_per_mm else f"FAILED  ticks={cal.tick_count}"
        cv2.putText(overlay, label, (30, h - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

        out_path = ruler_dir / f"{img_path.stem}_ruler.jpg"
        cv2.imwrite(str(out_path), overlay)
        results.append({
            "file": img_path.name,
            "ruler_detected": cal.ruler_detected,
            "px_per_mm": cal.px_per_mm,
            "tick_count": cal.tick_count,
            "median_spacing": cal.median_tick_spacing_px,
        })

    return results


# ── Segmentation Diagnostic ──────────────────────────────────────────

def diagnose_segmentation(images: list[Path]) -> list[dict]:
    """Run plant segmentation on each image. Save mask overlay."""
    seg_dir = OUTPUT_DIR / "segmentation"
    seg_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for img_path in images:
        image = cv2.imread(str(img_path))
        seg = segment_plant(image)

        # Create a green overlay where the mask is active
        overlay = image.copy()
        green_tint = np.zeros_like(image)
        green_tint[:, :, 1] = 255  # pure green
        mask_bool = seg.mask > 0
        overlay[mask_bool] = cv2.addWeighted(
            image[mask_bool], 0.5, green_tint[mask_bool], 0.5, 0
        )

        # Draw contour outline
        if seg.contour is not None:
            cv2.drawContours(overlay, [seg.contour], -1, (0, 255, 0), 2)

        # Draw petri dish circle if detected
        dish_str = "no dish"
        if seg.dish_circle:
            cx, cy, r = seg.dish_circle
            cv2.circle(overlay, (cx, cy), r, (0, 200, 255), 2)
            dish_str = f"dish=({cx},{cy}) r={r}"

        # Label
        cv2.putText(overlay, f"area_px={seg.area_px:,}  {dish_str}",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        out_path = seg_dir / f"{img_path.stem}_seg.jpg"
        cv2.imwrite(str(out_path), overlay)

        # Also save the raw binary mask
        mask_path = seg_dir / f"{img_path.stem}_mask.jpg"
        cv2.imwrite(str(mask_path), seg.mask)

        results.append({
            "file": img_path.name,
            "area_px": seg.area_px,
            "success": seg.success,
            "dish": dish_str,
        })

    return results


# ── Full Summary Diagnostic ──────────────────────────────────────────

def diagnose_full(images: list[Path]) -> list[dict]:
    """Run all modules on each image. Produce a combined summary."""
    full_dir = OUTPUT_DIR / "full"
    full_dir.mkdir(parents=True, exist_ok=True)
    results = []
    prev_area_mm2 = None

    for img_path in images:
        image = cv2.imread(str(img_path))

        # QR
        qr = detect_qr_code(image)

        # Ruler
        cal = calibrate_from_ruler(image)

        # Segmentation
        seg = segment_plant(image)
        area_mm2 = None
        if seg.success and cal.px_per_mm and cal.px_per_mm > 0:
            area_mm2 = seg.area_px / (cal.px_per_mm ** 2)

        # Color
        colors = extract_color_metrics(image, seg.mask) if seg.success else None

        # Growth rate (relative to previous image)
        growth_rate = None
        if area_mm2 is not None and prev_area_mm2 is not None:
            growth_rate = area_mm2 - prev_area_mm2  # simple delta for diagnostics

        # Health
        health = None
        if colors:
            health = compute_health_score(
                greenness_index=colors.greenness_index,
                mean_saturation=colors.mean_saturation,
                growth_rate=growth_rate,
            )

        overgrown = is_overgrown(area_mm2)

        # Build combined overlay
        overlay = image.copy()
        green_tint = np.zeros_like(image)
        green_tint[:, :, 1] = 255
        mask_bool = seg.mask > 0
        overlay[mask_bool] = cv2.addWeighted(
            image[mask_bool], 0.5, green_tint[mask_bool], 0.5, 0
        )
        if seg.contour is not None:
            cv2.drawContours(overlay, [seg.contour], -1, (0, 255, 0), 2)

        # Info text
        lines = [
            f"QR: {qr or 'N/A'}",
            f"px/mm: {cal.px_per_mm:.2f}" if cal.px_per_mm else "px/mm: N/A",
            f"area: {seg.area_px:,} px" + (f" / {area_mm2:.1f} mm2" if area_mm2 else ""),
            f"greenness: {colors.greenness_index:.3f}" if colors else "greenness: N/A",
            f"health: {health:.1f}" if health else "health: N/A",
            f"overgrown: {overgrown}",
        ]
        for i, line in enumerate(lines):
            cv2.putText(overlay, line, (15, 30 + i * 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 4)
            cv2.putText(overlay, line, (15, 30 + i * 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)

        out_path = full_dir / f"{img_path.stem}_full.jpg"
        cv2.imwrite(str(out_path), overlay)

        results.append({
            "file": img_path.name,
            "qr": qr,
            "px_per_mm": cal.px_per_mm,
            "ticks": cal.tick_count,
            "area_px": seg.area_px,
            "area_mm2": round(area_mm2, 1) if area_mm2 else None,
            "greenness": round(colors.greenness_index, 3) if colors else None,
            "saturation": round(colors.mean_saturation, 3) if colors else None,
            "hue": round(colors.mean_hue, 1) if colors else None,
            "health": round(health, 1) if health else None,
            "overgrown": overgrown,
        })

        prev_area_mm2 = area_mm2

    return results


# ── Console Formatting ───────────────────────────────────────────────

def print_table(rows: list[dict], title: str) -> None:
    if not rows:
        print(f"  (no results for {title})")
        return
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")
    keys = list(rows[0].keys())
    # Compute column widths
    widths = {k: max(len(str(k)), max(len(str(r.get(k, ""))) for r in rows)) for k in keys}
    header = "  ".join(str(k).ljust(widths[k]) for k in keys)
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(str(row.get(k, "")).ljust(widths[k]) for k in keys))
    print()


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline diagnostic tool")
    parser.add_argument("--image-dir", type=str, default=str(settings.image_dir))
    parser.add_argument("--step", type=str, default="all",
                        choices=["qr", "ruler", "seg", "full", "all"],
                        help="Which diagnostic to run (default: all)")
    args = parser.parse_args()

    image_dir = Path(args.image_dir).resolve()
    images = collect_images(image_dir)
    if not images:
        print(f"No images found in {image_dir}")
        sys.exit(1)

    print(f"Found {len(images)} images in {image_dir}")
    print(f"Output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    step = args.step

    if step in ("qr", "all"):
        print("\n--- QR Detection ---")
        qr_results = diagnose_qr(images)
        print_table(qr_results, "QR Detection Results")

    if step in ("ruler", "all"):
        print("\n--- Ruler Calibration ---")
        ruler_results = diagnose_ruler(images)
        print_table(ruler_results, "Ruler Calibration Results")

    if step in ("seg", "all"):
        print("\n--- Segmentation ---")
        seg_results = diagnose_segmentation(images)
        print_table(seg_results, "Segmentation Results")

    if step in ("full", "all"):
        print("\n--- Full Pipeline Summary ---")
        full_results = diagnose_full(images)
        print_table(full_results, "Full Pipeline Summary")

    print(f"\nDiagnostic images saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
