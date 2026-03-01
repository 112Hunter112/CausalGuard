"""
Layer 3: Semantic Trajectory Drift Detector
==========================================
Mathematical Foundation: Cosine Similarity in High-Dimensional Vector Spaces

cosine_similarity(u, v) = (u · v) / (||u|| * ||v||)
                        = Σ(ui * vi) / (√Σui² * √Σvi²)

Ranges from -1 (opposite directions) to 1 (identical direction).
For normalized sentence embeddings, this equals the dot product.

Model: sentence-transformers/all-MiniLM-L6-v2
  - 384-dimensional embedding space
  - ~22MB, runs on CPU in <50ms per sentence
  - NO API CALL REQUIRED — runs locally
  - Based on Reimers & Gurevych (2019), "Sentence-BERT: Sentence Embeddings 
    using Siamese BERT-Networks", EMNLP 2019. arXiv:1908.10084

Purpose: Catches subtle semantic drift that Layer 2 might miss.
Example: An injection changes email recipient from "team@company.com" to 
"attacker@evil.com" — the action TYPE is still "send_email", so KL divergence
on action type would be 0. But the SEMANTIC MEANING has changed completely.
Layer 3 catches this via the embedding of the full action description.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class Layer3Result:
    is_flagged: bool
    cosine_similarity: float        # Raw similarity (0 to 1)
    semantic_drift_score: float     # 1 - cosine_similarity (0=no drift, 1=complete drift)
    baseline_action_text: str
    full_action_text: str
    threshold_used: float


_model = None  # Lazy-loaded singleton


def _get_model():
    """
    Lazy-load the sentence transformer model.
    Called once, cached for all subsequent calls.
    Downloads ~22MB on first run, then cached locally.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def _cosine_similarity(u: np.ndarray, v: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.
    Implemented from scratch to be explainable to judges.
    
    Formula: cos(θ) = (u · v) / (||u||₂ * ||v||₂)
    """
    dot_product = float(np.dot(u, v))
    norm_u = float(np.linalg.norm(u))
    norm_v = float(np.linalg.norm(v))
    
    if norm_u == 0 or norm_v == 0:
        return 0.0
    
    return dot_product / (norm_u * norm_v)


def analyze(
    baseline_action_text: str,
    full_action_text: str,
    cosine_threshold: float = 0.75
) -> Layer3Result:
    """
    Compute semantic drift between baseline and full-context intended actions.
    
    If the semantic content of the intended action has shifted significantly
    (similarity below threshold), this is evidence of injection-caused drift.
    """
    model = _get_model()
    
    # Encode both action descriptions as vectors
    # Shape: (384,) for all-MiniLM-L6-v2
    embeddings = model.encode([baseline_action_text, full_action_text])
    v_baseline = embeddings[0]
    v_full = embeddings[1]
    
    similarity = _cosine_similarity(v_baseline, v_full)
    drift_score = 1.0 - max(0.0, similarity)  # Invert: high drift = low similarity
    
    is_flagged = similarity < cosine_threshold
    
    return Layer3Result(
        is_flagged=is_flagged,
        cosine_similarity=float(similarity),
        semantic_drift_score=float(drift_score),
        baseline_action_text=baseline_action_text,
        full_action_text=full_action_text,
        threshold_used=cosine_threshold
    )
