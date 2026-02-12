"""Health score computation.

Combines color metrics and growth behaviour into a single 0–100 scalar.
Also provides the overgrowth flag.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def compute_health_score(
    greenness_index: float,
    mean_saturation: float,
    growth_rate: float | None,
    previous_health: float | None = None,
) -> float:
    """Compute a composite health score in the range 0–100.

    Formula (Phase 1):
        score = w1 * greenness_norm + w2 * sat_norm + w3 * growth_norm

    Each component is normalized to 0–1 by comparing against "healthy"
    reference values from config.  Values above the reference map to 1.0;
    values at zero map to 0.0.

    Args:
        greenness_index: ``(2G - R - B) / (R+G+B)``, typically -1 to +1.
        mean_saturation: Normalized 0–1.
        growth_rate: Area change per hour (mm²/h), or ``None`` for the
            first measurement.
        previous_health: Previous health score (used to dampen growth
            component when no growth data exists).

    Returns:
        Health score as a float between 0 and 100.
    """
    w1 = settings.health_weight_greenness
    w2 = settings.health_weight_saturation
    w3 = settings.health_weight_growth

    # Normalize greenness: map [-1, healthy_ref] to [0, 1], clamp
    green_ref = settings.healthy_greenness_ref
    greenness_norm = _clamp((greenness_index + 1.0) / (green_ref + 1.0), 0.0, 1.0)

    # Normalize saturation
    sat_ref = settings.healthy_saturation_ref
    sat_norm = _clamp(mean_saturation / sat_ref, 0.0, 1.0) if sat_ref > 0 else 0.0

    # Growth component
    if growth_rate is not None:
        # Positive growth is healthy; cap at 1.0
        # Negative (shrinking) maps toward 0
        if growth_rate >= 0:
            growth_norm = min(1.0, 0.5 + growth_rate * 0.1)  # baseline 0.5
        else:
            growth_norm = max(0.0, 0.5 + growth_rate * 0.1)
    elif previous_health is not None:
        # No growth data yet: use previous score as proxy
        growth_norm = previous_health / 100.0
    else:
        # Very first measurement, assume neutral
        growth_norm = 0.5

    total_weight = w1 + w2 + w3
    raw = (w1 * greenness_norm + w2 * sat_norm + w3 * growth_norm) / total_weight
    score = _clamp(raw * 100.0, 0.0, 100.0)

    logger.info(
        "Health score: %.1f (green=%.2f, sat=%.2f, growth=%.2f)",
        score,
        greenness_norm,
        sat_norm,
        growth_norm,
    )
    return round(score, 2)


def is_overgrown(area_mm2: float | None) -> bool:
    """Return ``True`` if the plant area exceeds the overgrowth threshold."""
    if area_mm2 is None:
        return False
    overgrown = area_mm2 > settings.overgrowth_threshold_mm2
    if overgrown:
        logger.info("Overgrowth detected: %.1f mm² > %.1f mm²", area_mm2, settings.overgrowth_threshold_mm2)
    return overgrown


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
