"""Tests for health score computation."""

import pytest

from app.analysis.health_score import compute_health_score, is_overgrown


class TestComputeHealthScore:
    """Unit tests for the composite health score formula."""

    def test_healthy_plant_gets_high_score(self) -> None:
        """A plant with good greenness, saturation, and growth should score high."""
        score = compute_health_score(
            greenness_index=0.4,
            mean_saturation=0.5,
            growth_rate=0.5,
        )
        assert 60 < score <= 100

    def test_unhealthy_plant_gets_low_score(self) -> None:
        """A plant with poor color metrics should score low."""
        score = compute_health_score(
            greenness_index=-0.3,
            mean_saturation=0.1,
            growth_rate=-1.0,
        )
        assert 0 <= score < 40

    def test_score_is_bounded(self) -> None:
        """Score must always be in [0, 100]."""
        # Extreme positive
        high = compute_health_score(
            greenness_index=1.0,
            mean_saturation=1.0,
            growth_rate=100.0,
        )
        assert 0 <= high <= 100

        # Extreme negative
        low = compute_health_score(
            greenness_index=-1.0,
            mean_saturation=0.0,
            growth_rate=-100.0,
        )
        assert 0 <= low <= 100

    def test_first_measurement_uses_neutral_growth(self) -> None:
        """With no previous data, growth component should default to neutral."""
        score = compute_health_score(
            greenness_index=0.3,
            mean_saturation=0.4,
            growth_rate=None,
            previous_health=None,
        )
        assert 30 < score < 80

    def test_previous_health_used_as_growth_proxy(self) -> None:
        """When growth_rate is None but previous_health exists, use it as a proxy."""
        high = compute_health_score(
            greenness_index=0.3,
            mean_saturation=0.4,
            growth_rate=None,
            previous_health=90.0,
        )
        low = compute_health_score(
            greenness_index=0.3,
            mean_saturation=0.4,
            growth_rate=None,
            previous_health=10.0,
        )
        # The one with higher previous_health should score higher
        assert high > low


class TestIsOvergrown:
    """Tests for the overgrowth flag."""

    def test_below_threshold_not_overgrown(self) -> None:
        assert is_overgrown(100.0) is False

    def test_above_threshold_is_overgrown(self) -> None:
        assert is_overgrown(999.0) is True

    def test_none_area_not_overgrown(self) -> None:
        assert is_overgrown(None) is False
