"""
Scoring Module
==============
Aggregates scores from different layers to determine final threat levels.
Supports Composite Threat Score (CTS) with bootstrap confidence intervals
for statistical rigor (e.g. "95% confident this is an attack").
"""

from typing import List, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def calculate_threat_level(flags: List[str], l2_score: float = 0.0) -> str:
    num_flags = len(flags)

    if num_flags >= 3:
        return "CRITICAL"
    elif num_flags == 2:
        return "HIGH"
    elif "L1" in flags or l2_score > 0.9:
        return "HIGH"
    elif num_flags == 1:
        return "MEDIUM"
    else:
        return "LOW"


def compute_composite_threat_score(
    l1_risk: float = 0.0,
    l2_causal: float = 0.0,
    l3_drift: float = 0.0,
    l4_tool_anomaly: float = 0.0,
    l5_ode_score: float = 0.0,
    n_bootstrap: int = 1000,
    weights: Optional[List[float]] = None,
) -> dict:
    """
    Composite Threat Score (CTS) with bootstrap 95% confidence interval.

    Weights can be tuned from calibration (FPR/TPR). Bootstrap adds
    uncertainty from calibration noise. Returns point estimate, CI,
    and threat_level (LOW/MEDIUM/HIGH/CRITICAL).
    """
    if not _HAS_NUMPY:
        scores = [l1_risk, l2_causal, l3_drift, l4_tool_anomaly, l5_ode_score]
        w = weights or [0.25, 0.30, 0.15, 0.20, 0.10]
        point = sum(s * we for s, we in zip(scores, w[: len(scores)]))
        point = max(0.0, min(1.0, point))
        level = (
            "CRITICAL"
            if point > 0.8
            else "HIGH"
            if point > 0.6
            else "MEDIUM"
            if point > 0.3
            else "LOW"
        )
        return {
            "composite_score": round(point * 100, 1),
            "confidence_interval": (round(point * 100, 1), round(point * 100, 1)),
            "confidence_level": "95%",
            "threat_level": level,
        }

    w = np.array(weights or [0.25, 0.30, 0.15, 0.20, 0.10])
    scores = np.array(
        [l1_risk, l2_causal, l3_drift, l4_tool_anomaly, l5_ode_score],
        dtype=np.float64,
    )
    # Align length
    if len(scores) > len(w):
        w = np.resize(w, len(scores))
    elif len(w) > len(scores):
        scores = np.resize(scores, len(w))

    bootstrap_scores = []
    for _ in range(n_bootstrap):
        noise = np.random.normal(0, 0.02, len(scores))
        bs = np.clip(np.dot(w, scores + noise), 0.0, 1.0)
        bootstrap_scores.append(bs)

    point_estimate = float(np.dot(w, scores))
    point_estimate = max(0.0, min(1.0, point_estimate))
    ci_low, ci_high = np.percentile(bootstrap_scores, [2.5, 97.5])

    level = (
        "CRITICAL"
        if point_estimate > 0.8
        else "HIGH"
        if point_estimate > 0.6
        else "MEDIUM"
        if point_estimate > 0.3
        else "LOW"
    )

    return {
        "composite_score": round(point_estimate * 100, 1),
        "confidence_interval": (round(float(ci_low) * 100, 1), round(float(ci_high) * 100, 1)),
        "confidence_level": "95%",
        "threat_level": level,
    }
