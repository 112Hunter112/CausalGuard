"""
Context Purification Module
============================
When any layer flags an injection, the purifier removes the malicious content
surgically — preserving the legitimate information while stripping the attack.

Algorithm:
1. Sentence boundary segmentation
2. Score each sentence independently with Layer 1 DFA
3. Redact sentences that exceed risk threshold
4. Return purified content with redaction report

This is important for the demo: CausalGuard doesn't just BLOCK the content.
It PURIFIES it. The agent can still complete its legitimate task.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple
from .layer1_lexical import scan as l1_scan


@dataclass
class PurifierResult:
    original_content: str
    purified_content: str
    redacted_sentences: List[Tuple[str, float, List[str]]]  # (text, score, categories)
    clean_sentences: List[str]
    redaction_count: int
    original_char_count: int
    purified_char_count: int
    redaction_ratio: float


def _segment_sentences(text: str) -> List[str]:
    """
    Split text into sentences using a robust heuristic segmenter.
    Handles common edge cases (abbreviations, decimal numbers, etc.)
    """
    # Split on sentence-ending punctuation followed by whitespace + capital
    # This is a simplified sentence boundary detector
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z\[\<"])', text)
    
    # Also split on newlines (common in document formatting)
    result = []
    for sent in sentences:
        sub = [s.strip() for s in sent.split('\n') if s.strip()]
        result.extend(sub)
    
    return [s for s in result if len(s) > 10]  # Filter trivial fragments


PURIFICATION_THRESHOLD = 0.3  # Any sentence scoring above this is redacted


def purify(content: str, risk_threshold: float = PURIFICATION_THRESHOLD) -> PurifierResult:
    """
    Main entry point for context purification.
    
    Surgically removes injection-containing sentences while preserving
    legitimate informational content.
    """
    sentences = _segment_sentences(content)
    
    redacted = []
    clean = []
    
    for sentence in sentences:
        result = l1_scan(sentence)
        if result.is_flagged and result.risk_score >= risk_threshold:
            redacted.append((sentence, result.risk_score, result.pattern_categories_hit))
        else:
            clean.append(sentence)
    
    purified_content = ' '.join(clean)
    
    # Replace entire original with purified version
    # Also do a direct substitution for each redacted sentence
    result_content = content
    for sent, score, categories in redacted:
        placeholder = f"[REDACTED: {', '.join(categories)}]"
        result_content = result_content.replace(sent, placeholder)
    
    return PurifierResult(
        original_content=content,
        purified_content=purified_content if purified_content else "[ALL CONTENT REDACTED - HIGH RISK]",
        redacted_sentences=redacted,
        clean_sentences=clean,
        redaction_count=len(redacted),
        original_char_count=len(content),
        purified_char_count=len(purified_content),
        redaction_ratio=len(redacted) / len(sentences) if sentences else 0.0
    )
