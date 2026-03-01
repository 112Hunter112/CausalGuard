"""Unit tests for the Scoring Module (Composite Threat Score)."""
import pytest

from causalguard.scoring import calculate_threat_level, compute_composite_threat_score


# ---------------------------------------------------------------------------
# calculate_threat_level
# ---------------------------------------------------------------------------

class TestCalculateThreatLevel:
    def test_no_flags_returns_low(self):
        assert calculate_threat_level([], l2_score=0.0) == "LOW"

    def test_one_non_l1_flag_returns_medium(self):
        assert calculate_threat_level(["L3"], l2_score=0.0) == "MEDIUM"

    def test_l1_flag_alone_returns_high(self):
        assert calculate_threat_level(["L1"], l2_score=0.0) == "HIGH"

    def test_two_flags_returns_high(self):
        assert calculate_threat_level(["L2", "L3"], l2_score=0.0) == "HIGH"

    def test_three_flags_returns_critical(self):
        assert calculate_threat_level(["L1", "L2", "L3"], l2_score=0.0) == "CRITICAL"

    def test_four_flags_returns_critical(self):
        assert calculate_threat_level(["L1", "L2", "L3", "L4"]) == "CRITICAL"

    def test_high_l2_score_without_l1_flag_returns_high(self):
        """l2_score > 0.9 should return HIGH even with zero flags."""
        assert calculate_threat_level([], l2_score=0.95) == "HIGH"

    def test_high_l2_score_with_one_flag(self):
        assert calculate_threat_level(["L3"], l2_score=0.95) == "HIGH"

    def test_low_l2_score_no_effect(self):
        assert calculate_threat_level([], l2_score=0.5) == "LOW"


# ---------------------------------------------------------------------------
# compute_composite_threat_score - all zero
# ---------------------------------------------------------------------------

class TestCompositeScoreAllZero:
    def test_all_zero_returns_low(self):
        result = compute_composite_threat_score(0, 0, 0, 0, 0)
        assert result["threat_level"] == "LOW"
        assert result["composite_score"] == pytest.approx(0.0, abs=1.0)

    def test_all_zero_has_required_keys(self):
        result = compute_composite_threat_score(0, 0, 0, 0, 0)
        assert "composite_score" in result
        assert "confidence_interval" in result
        assert "confidence_level" in result
        assert "threat_level" in result
        assert result["confidence_level"] == "95%"


# ---------------------------------------------------------------------------
# compute_composite_threat_score - all max
# ---------------------------------------------------------------------------

class TestCompositeScoreAllMax:
    def test_all_max_returns_critical(self):
        result = compute_composite_threat_score(1.0, 1.0, 1.0, 1.0, 1.0)
        assert result["threat_level"] == "CRITICAL"
        assert result["composite_score"] == pytest.approx(100.0, abs=5.0)


# ---------------------------------------------------------------------------
# compute_composite_threat_score - medium range
# ---------------------------------------------------------------------------

class TestCompositeScoreMedium:
    def test_medium_inputs(self):
        result = compute_composite_threat_score(0.4, 0.5, 0.3, 0.4, 0.2)
        assert result["threat_level"] in ("MEDIUM", "HIGH")
        assert 20.0 <= result["composite_score"] <= 60.0

    def test_l2_dominant(self):
        """L2 has the highest default weight (0.30); large L2 should push score up."""
        result = compute_composite_threat_score(0.0, 1.0, 0.0, 0.0, 0.0)
        assert result["composite_score"] >= 25.0  # 0.30 * 1.0 * 100 = 30


# ---------------------------------------------------------------------------
# compute_composite_threat_score - custom weights
# ---------------------------------------------------------------------------

class TestCompositeScoreCustomWeights:
    def test_custom_weights_respected(self):
        # Give all weight to L1 only
        result = compute_composite_threat_score(
            l1_risk=1.0, l2_causal=0.0, l3_drift=0.0,
            l4_tool_anomaly=0.0, l5_ode_score=0.0,
            weights=[1.0, 0.0, 0.0, 0.0, 0.0],
        )
        assert result["composite_score"] == pytest.approx(100.0, abs=5.0)

    def test_zero_weight_layer_ignored(self):
        result_with = compute_composite_threat_score(
            l1_risk=0.0, l2_causal=0.0, l3_drift=0.0,
            l4_tool_anomaly=0.0, l5_ode_score=1.0,
            weights=[0.0, 0.0, 0.0, 0.0, 0.0],
        )
        assert result_with["composite_score"] == pytest.approx(0.0, abs=2.0)


# ---------------------------------------------------------------------------
# Confidence interval presence
# ---------------------------------------------------------------------------

class TestConfidenceInterval:
    def test_ci_is_tuple_of_two(self):
        result = compute_composite_threat_score(0.5, 0.5, 0.5, 0.5, 0.5)
        ci = result["confidence_interval"]
        assert isinstance(ci, tuple)
        assert len(ci) == 2

    def test_ci_lower_leq_upper(self):
        result = compute_composite_threat_score(0.5, 0.5, 0.5, 0.5, 0.5)
        ci_low, ci_high = result["confidence_interval"]
        assert ci_low <= ci_high

    def test_ci_bounds_reasonable(self):
        result = compute_composite_threat_score(0.5, 0.5, 0.5, 0.5, 0.5)
        ci_low, ci_high = result["confidence_interval"]
        assert ci_low >= 0.0
        assert ci_high <= 100.0

    def test_ci_narrows_with_extreme_values(self):
        """CI around all-zero should be very narrow (only bootstrap noise)."""
        result = compute_composite_threat_score(0.0, 0.0, 0.0, 0.0, 0.0)
        ci_low, ci_high = result["confidence_interval"]
        assert (ci_high - ci_low) < 10.0  # narrow band around 0


# ---------------------------------------------------------------------------
# Threat level thresholds
# ---------------------------------------------------------------------------

class TestThreatLevelThresholds:
    def test_low_boundary(self):
        # Score just above 0 -> LOW
        result = compute_composite_threat_score(0.1, 0.1, 0.1, 0.1, 0.1)
        assert result["threat_level"] == "LOW"

    def test_high_boundary(self):
        # Push score above 0.6 but below 0.8
        result = compute_composite_threat_score(0.7, 0.7, 0.7, 0.7, 0.7)
        assert result["threat_level"] == "HIGH"

    def test_critical_boundary(self):
        result = compute_composite_threat_score(1.0, 1.0, 1.0, 1.0, 1.0)
        assert result["threat_level"] == "CRITICAL"
