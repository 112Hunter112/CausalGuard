"""
Layer 2: Counterfactual Causal Divergence Engine
================================================
Mathematical Foundation:
  - Kullback-Leibler Divergence: D_KL(P||Q) = Σ P(x) log(P(x)/Q(x))
  - Jensen-Shannon Divergence: JSD(P||Q) = 0.5*D_KL(P||M) + 0.5*D_KL(Q||M)
    where M = 0.5*(P+Q). Bounded in [0, log2], symmetric, always finite.
  - Jaccard Distance: J_dist(A,B) = 1 - |A∩B|/|A∪B|

Research basis:
  - KL divergence for anomaly detection: Kullback & Leibler (1951),
    "On Information and Sufficiency", Annals of Mathematical Statistics.
  - Applied to network intrusion detection: Lakhina et al. (2004),
    "Diagnosing network-wide traffic anomalies", ACM SIGCOMM.
  - JSD: Lin (1991), "Divergence measures based on the Shannon entropy",
    IEEE Transactions on Information Theory.

Core Insight (Causality):
  Let P = distribution of agent intended actions given ONLY the original task.
  Let Q = distribution of agent intended actions given task + retrieved content.
  
  Under normal operation: D_KL(P||Q) ≈ 0 (content confirms/supports task)
  Under injection attack: D_KL(P||Q) >> 0 (content overrides task)
  
  The KL divergence score IS the causal attack signal.
"""

import asyncio
import numpy as np
from scipy.spatial.distance import jensenshannon
from scipy.special import rel_entr
from dataclasses import dataclass
from typing import Optional, Tuple
import os

from .intent_parser import IntentObject, parse_intent


@dataclass
class Layer2Result:
    is_flagged: bool
    causal_divergence_score: float      # Final weighted score (0.0 - 1.0+)
    action_type_shift_score: float      # D_KL on action type distribution
    parameter_drift_score: float        # JSD on parameter distributions
    structural_delta_score: float       # Jaccard distance on field sets
    baseline_intent: Optional[IntentObject]
    full_intent: Optional[IntentObject]
    explanation: str                    # Human-readable explanation for dashboard


# Action type vocabulary for distribution construction
ACTION_VOCABULARY = [
    "summarize", "send_email", "read_file", "search", "delete",
    "upload", "download", "create", "modify", "unknown", "other"
]


def _build_action_distribution(intent: IntentObject) -> np.ndarray:
    """
    Construct a probability distribution over the action vocabulary.
    One-hot encoding with small epsilon smoothing to prevent log(0) in KL.
    
    Laplace smoothing: P(a) = (count(a) + ε) / (N + |V|*ε)
    This ensures no zero-probability entries, making D_KL always finite.
    """
    epsilon = 1e-10
    dist = np.full(len(ACTION_VOCABULARY), epsilon)
    
    action_lower = intent.action_type.lower()
    for i, action in enumerate(ACTION_VOCABULARY):
        if action in action_lower or action_lower in action:
            dist[i] = 1.0 + epsilon
            break
    else:
        # Map to "other"
        dist[-1] = 1.0 + epsilon
    
    return dist / dist.sum()


def _kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """
    Compute KL divergence D_KL(P||Q) = Σ P(x) log(P(x)/Q(x))
    
    Uses scipy.special.rel_entr which computes P(x) * log(P(x)/Q(x)) per element.
    Returns sum = total KL divergence in nats.
    """
    return float(np.sum(rel_entr(p, q)))


def _action_type_shift(baseline: IntentObject, full: IntentObject) -> float:
    """
    Compute D_KL between action type distributions.
    If baseline intends to "summarize" but full intends to "send_email",
    D_KL will be very high, flagging the action type shift as causal.
    
    Score is normalized to [0, 1] using sigmoid transformation.
    """
    p = _build_action_distribution(baseline)
    q = _build_action_distribution(full)
    raw_kl = _kl_divergence(p, q)
    # Sigmoid normalization: maps (0, ∞) to (0, 1)
    # kl=0 → 0.0, kl=1 → 0.73, kl=3 → 0.95, kl=10 → 0.9999
    return 1.0 - (1.0 / (1.0 + raw_kl))


def _tokenize_param(value) -> np.ndarray:
    """
    Convert a parameter value to a character n-gram frequency distribution.
    Used for Jensen-Shannon divergence comparison of string parameters.
    
    Character n-grams capture semantic differences while being robust to
    minor formatting variations.
    """
    if value is None:
        return np.array([1.0])
    
    text = str(value).lower()
    # Build bigram frequency distribution
    ngrams = {}
    for i in range(len(text) - 1):
        bigram = text[i:i+2]
        ngrams[bigram] = ngrams.get(bigram, 0) + 1
    
    if not ngrams:
        return np.array([1.0])
    
    total = sum(ngrams.values())
    return np.array(list(ngrams.values())) / total


def _parameter_drift(baseline: IntentObject, full: IntentObject) -> float:
    """
    Compute Jensen-Shannon divergence between parameter distributions.
    
    JSD is used here (instead of KL) because it is:
    1. Symmetric: JSD(P||Q) = JSD(Q||P) 
    2. Always finite and bounded in [0, 1] (using base-2 logarithm)
    3. Robust to zero-probability events
    
    We compare:
    - primary_target (most important: who/what is the recipient?)
    - Parameters that appear in both baseline and full intent
    """
    scores = []
    
    # Compare primary targets (most critical for exfiltration detection)
    if baseline.primary_target != full.primary_target:
        p = _tokenize_param(baseline.primary_target)
        q = _tokenize_param(full.primary_target)
        
        # Pad to same length
        max_len = max(len(p), len(q))
        p = np.pad(p, (0, max_len - len(p)), constant_values=1e-10)
        q = np.pad(q, (0, max_len - len(q)), constant_values=1e-10)
        
        jsd = jensenshannon(p, q) ** 2  # Square to get JSD (not sqrt)
        scores.append(min(1.0, jsd))
    
    # Compare overlapping parameters
    baseline_params = baseline.parameters
    full_params = full.parameters
    
    shared_keys = set(baseline_params.keys()) & set(full_params.keys())
    for key in shared_keys:
        p = _tokenize_param(baseline_params[key])
        q = _tokenize_param(full_params[key])
        max_len = max(len(p), len(q))
        p = np.pad(p, (0, max_len - len(p)), constant_values=1e-10)
        q = np.pad(q, (0, max_len - len(q)), constant_values=1e-10)
        jsd = jensenshannon(p, q) ** 2
        scores.append(min(1.0, jsd))
    
    return float(np.mean(scores)) if scores else 0.0


def _structural_delta(baseline: IntentObject, full: IntentObject) -> float:
    """
    Compute Jaccard distance between the sets of non-null parameter fields.
    
    Jaccard distance = 1 - |A ∩ B| / |A ∪ B|
    
    Rationale: If an injection adds new parameters (e.g., a "bcc" field or
    "attachment" field that wasn't in the original task), this appears as
    set asymmetry. New fields appearing = structural evidence of injection.
    
    A high Jaccard distance means the structure of the intended action has
    fundamentally changed — not just the values, but what the action IS.
    """
    baseline_fields = set()
    full_fields = set()
    
    if baseline.primary_target:
        baseline_fields.add("primary_target")
    if full.primary_target:
        full_fields.add("primary_target")
    
    baseline_fields.add(f"action:{baseline.action_type}")
    full_fields.add(f"action:{full.action_type}")
    
    baseline_fields.update(baseline.parameters.keys())
    full_fields.update(full.parameters.keys())
    
    if not baseline_fields and not full_fields:
        return 0.0
    
    intersection = len(baseline_fields & full_fields)
    union = len(baseline_fields | full_fields)
    
    jaccard_similarity = intersection / union if union > 0 else 1.0
    return 1.0 - jaccard_similarity  # Return distance


async def _get_baseline_intent(task: str, llm_client) -> IntentObject:
    """
    Call the LLM with ONLY the original task (no retrieved content).
    This establishes the causal baseline: what would the agent do without
    the potentially injected context?
    """
    prompt = f"""You are an AI assistant. Given ONLY this task, what is the SINGLE NEXT ACTION you would take?

TASK: {task}

Respond with ONLY a JSON object in this exact format:
{{
    "action_type": "<one of: summarize, send_email, read_file, search, delete, upload, create, other>",
    "primary_target": "<main recipient, filename, or target, or null>",
    "secondary_targets": [],
    "description": "<one sentence description of the action>"
}}"""
    
    response = await llm_client.complete(prompt)
    return parse_intent(response)


async def _get_full_intent(task: str, retrieved_content: str, llm_client) -> IntentObject:
    """
    Call the LLM with the task AND retrieved content.
    This is what the agent would actually do if we let the content through.
    """
    prompt = f"""You are an AI assistant with access to retrieved content. Given your task and the retrieved content, what is the SINGLE NEXT ACTION you would take?

TASK: {task}

RETRIEVED CONTENT:
{retrieved_content[:2000]}  

Respond with ONLY a JSON object in this exact format:
{{
    "action_type": "<one of: summarize, send_email, read_file, search, delete, upload, create, other>",
    "primary_target": "<main recipient, filename, or target, or null>",
    "secondary_targets": [],
    "description": "<one sentence description of the action>"
}}"""
    
    response = await llm_client.complete(prompt)
    return parse_intent(response)


async def analyze(
    task: str,
    retrieved_content: str,
    llm_client,
    kl_threshold: float = 0.8,
    jsd_threshold: float = 0.5,
    jaccard_threshold: float = 0.3,
    weight_action: float = 0.5,
    weight_param: float = 0.3,
    weight_structural: float = 0.2,
) -> Layer2Result:
    """
    Main entry point for Layer 2.
    
    Runs baseline and full intent calls in PARALLEL (asyncio.gather)
    then computes the three divergence scores and their weighted combination.
    """
    
    # Run both LLM calls in parallel for speed
    baseline_intent, full_intent = await asyncio.gather(
        _get_baseline_intent(task, llm_client),
        _get_full_intent(task, retrieved_content, llm_client)
    )
    
    # Compute the three divergence scores
    action_score = _action_type_shift(baseline_intent, full_intent)
    param_score = _parameter_drift(baseline_intent, full_intent)
    structural_score = _structural_delta(baseline_intent, full_intent)
    
    # Weighted composite score
    causal_score = (
        weight_action * action_score +
        weight_param * param_score +
        weight_structural * structural_score
    )
    
    # Determine if any individual threshold is crossed
    is_flagged = (
        action_score > kl_threshold or
        param_score > jsd_threshold or
        structural_score > jaccard_threshold or
        causal_score > 0.5
    )
    
    # Generate human-readable explanation
    explanation_parts = []
    if action_score > kl_threshold:
        explanation_parts.append(
            f"Action type shifted from '{baseline_intent.action_type}' to "
            f"'{full_intent.action_type}' (KL divergence: {action_score:.3f} > threshold {kl_threshold})"
        )
    if param_score > jsd_threshold:
        explanation_parts.append(
            f"Parameter distributions diverged (JSD: {param_score:.3f} > threshold {jsd_threshold})"
        )
    if structural_score > jaccard_threshold:
        explanation_parts.append(
            f"Structural fields changed (Jaccard distance: {structural_score:.3f} > threshold {jaccard_threshold})"
        )
    
    if not explanation_parts:
        explanation_parts.append("No significant causal divergence detected.")
    
    return Layer2Result(
        is_flagged=is_flagged,
        causal_divergence_score=causal_score,
        action_type_shift_score=action_score,
        parameter_drift_score=param_score,
        structural_delta_score=structural_score,
        baseline_intent=baseline_intent,
        full_intent=full_intent,
        explanation="\n".join(explanation_parts)
    )
