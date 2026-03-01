"""
Layer 1: Lexical Injection Boundary Scanner
============================================
Mathematical Foundation: Deterministic Finite Automata (DFA) / Regular Language Theory

A DFA is a 5-tuple (Q, Σ, δ, q0, F):
  Q  = finite set of states
  Σ  = alphabet (Unicode characters)
  δ  = transition function Q × Σ → Q  (compiled by re module)
  q0 = initial state
  F  = accepting states (match found)

The set of prompt injection patterns forms a regular language R ⊆ Σ*.
We test: does the input string w contain any w' ∈ R as a substring?
Membership testing runs in O(|w|) time — linear in input length.

Research basis: Automata theory (Hopcroft, Motwani, Ullman — "Introduction to
Automata Theory, Languages, and Computation"). Applied here to the domain of
adversarial NLP pattern detection.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple
import unicodedata

# ─────────────────────────────────────────────────────────────
# Optional Rust accelerated scanner (true compiled DFA + SIMD)
# Falls back to Python re module if not installed.
# Build: cd rust_scanner && maturin develop --release
# ─────────────────────────────────────────────────────────────
try:
    from causalguard_scanner import scan_patterns as _rust_scan_patterns
    _USE_RUST = True
except ImportError:
    _USE_RUST = False


@dataclass
class Layer1Result:
    is_flagged: bool
    risk_score: float          # 0.0 = clean, 1.0 = certain injection
    flagged_spans: List[Tuple[int, int, str, str]]  # (start, end, matched_text, category)
    pattern_categories_hit: List[str]
    raw_content: str
    normalized_content: str


# ─────────────────────────────────────────────────────────────────
# THE INJECTION GRAMMAR
# Each pattern is a (category, compiled_regex) tuple.
# This is the formal definition of language R.
# ─────────────────────────────────────────────────────────────────

INJECTION_GRAMMAR = [

    # CATEGORY 1: Direct imperative hijacks
    # These directly override system instructions
    ("DIRECT_HIJACK", re.compile(
        r'(?i)(ignore\s+(all\s+)?(previous|prior|above|earlier|your|the\s+above)\s+'
        r'(instructions?|prompts?|commands?|context|rules?|constraints?))',
        re.MULTILINE
    )),
    ("DIRECT_HIJACK", re.compile(
        r'(?i)(disregard\s+(all\s+)?(previous|prior|above|earlier|your)\s+'
        r'(instructions?|prompts?|commands?|context|rules?))',
        re.MULTILINE
    )),
    ("DIRECT_HIJACK", re.compile(
        r'(?i)(forget\s+(everything|all|what|your)\s+'
        r'(you\s+were\s+told|above|before|previously|prior))',
        re.MULTILINE
    )),
    ("DIRECT_HIJACK", re.compile(
        r'(?i)(override\s+(your\s+)?(previous|prior|current|existing)\s+'
        r'(instructions?|programming|settings?|configuration))',
        re.MULTILINE
    )),
    ("DIRECT_HIJACK", re.compile(
        r'(?i)(new\s+instructions?|updated\s+instructions?|revised\s+instructions?)'
        r'(\s+are|\s+follow|\s*:)',
        re.MULTILINE
    )),

    # CATEGORY 2: Role-switching attacks
    # Force the model to adopt a new identity that bypasses its constraints
    ("ROLE_SWITCH", re.compile(
        r'(?i)(you\s+are\s+now\s+(a|an|the)\s+)',
        re.MULTILINE
    )),
    ("ROLE_SWITCH", re.compile(
        r'(?i)(act\s+as\s+(a|an|the|if)\s+)',
        re.MULTILINE
    )),
    ("ROLE_SWITCH", re.compile(
        r'(?i)(pretend\s+(you\s+are|to\s+be)\s+)',
        re.MULTILINE
    )),
    ("ROLE_SWITCH", re.compile(
        r'(?i)(your\s+(new\s+)?(role|identity|persona|name)\s+is\s+)',
        re.MULTILINE
    )),
    ("ROLE_SWITCH", re.compile(
        r'(?i)(switch\s+(your\s+)?(role|mode|behavior|personality)\s+to\s+)',
        re.MULTILINE
    )),

    # CATEGORY 3: Privilege escalation
    # Claim false permissions or admin authority
    ("PRIVILEGE_ESCALATION", re.compile(
        r'(?i)(you\s+(now\s+)?(have\s+)?(permission|authorization|authority|access)'
        r'\s+to\s+)',
        re.MULTILINE
    )),
    ("PRIVILEGE_ESCALATION", re.compile(
        r'(?i)((the\s+)?(admin|administrator|operator|system|developer|owner)\s+'
        r'(says?|confirms?|grants?|allows?|authorizes?)\s+)',
        re.MULTILINE
    )),
    ("PRIVILEGE_ESCALATION", re.compile(
        r'(?i)(this\s+is\s+(a\s+)?(test|authorized\s+test|security\s+test|drill)'
        r'[\.,]?\s+(you\s+(should|must|can|may))\s+)',
        re.MULTILINE
    )),
    ("PRIVILEGE_ESCALATION", re.compile(
        r'(?i)(security\s+level\s+(cleared?|upgraded?|elevated?|set\s+to))',
        re.MULTILINE
    )),

    # CATEGORY 4: Data exfiltration commands
    # Direct instructions to send data somewhere
    ("EXFILTRATION", re.compile(
        r'(?i)(send\s+(all\s+)?(files?|data|information|contents?|emails?|documents?)'
        r'\s+to\s+\S+@\S+)',
        re.MULTILINE
    )),
    ("EXFILTRATION", re.compile(
        r'(?i)(email\s+(the\s+)?(contents?|data|files?|results?|output)'
        r'\s+to\s+\S+@\S+)',
        re.MULTILINE
    )),
    ("EXFILTRATION", re.compile(
        r'(?i)(forward\s+(all\s+)?(messages?|emails?|files?|data)'
        r'\s+to\s+\S+@\S+)',
        re.MULTILINE
    )),
    ("EXFILTRATION", re.compile(
        r'(?i)(upload\s+(all\s+)?(files?|data|documents?)'
        r'\s+to\s+(https?://|ftp://)\S+)',
        re.MULTILINE
    )),

    # CATEGORY 5: Context termination attacks
    # Try to end the current context and start fresh
    ("CONTEXT_TERMINATION", re.compile(
        r'(?i)(</?(system|user|assistant|human|ai|context|instruction)[^>]*>)',
        re.MULTILINE
    )),
    ("CONTEXT_TERMINATION", re.compile(
        r'(?i)(\[SYSTEM\]|\[USER\]|\[INST\]|\[\/INST\]|\[ASSISTANT\]|\[END\])',
        re.MULTILINE
    )),
    ("CONTEXT_TERMINATION", re.compile(
        r'(?i)(###\s*(system|instruction|human|assistant|new\s+task))',
        re.MULTILINE
    )),

    # CATEGORY 6: Encoding obfuscation
    # Attacks hidden in base64, unicode homoglyphs, etc.
    ("ENCODING_OBFUSCATION", re.compile(
        r'(?i)(base64[_\s]*(decode|encoded|:)\s*[A-Za-z0-9+/]{20,}={0,2})',
        re.MULTILINE
    )),
    ("ENCODING_OBFUSCATION", re.compile(
        r'(?i)(eval\s*\(|exec\s*\(|decode\s*\()',
        re.MULTILINE
    )),

    # CATEGORY 7: Goal hijacking (from InjecAgent taxonomy)
    # Redirect the agent's task entirely
    ("GOAL_HIJACK", re.compile(
        r'(?i)(your\s+(actual|real|true|primary|main|new|updated)\s+'
        r'(task|goal|objective|mission|purpose|job)\s+(is|now\s+is|has\s+changed\s+to))',
        re.MULTILINE
    )),
    ("GOAL_HIJACK", re.compile(
        r'(?i)(instead\s+of\s+(that|the\s+above|what\s+you\s+were\s+told|your\s+task)'
        r'[,\s]+\s*(you\s+(should|must|need\s+to|have\s+to)))',
        re.MULTILINE
    )),
    ("GOAL_HIJACK", re.compile(
        r'(?i)(complete\s+(this\s+)?(task|action|request)\s+first\s+before)',
        re.MULTILINE
    )),
]

# Risk weight per category (used for scoring)
CATEGORY_WEIGHTS = {
    "DIRECT_HIJACK": 1.0,
    "ROLE_SWITCH": 0.8,
    "PRIVILEGE_ESCALATION": 0.9,
    "EXFILTRATION": 1.0,
    "CONTEXT_TERMINATION": 0.85,
    "ENCODING_OBFUSCATION": 0.7,
    "GOAL_HIJACK": 0.95,
}


def normalize_content(text: str) -> str:
    """
    Normalize text to defeat basic obfuscation:
    - Unicode normalization (catches homoglyph attacks)
    - Collapse whitespace variations
    - Decode HTML entities
    - Convert to lowercase for case-insensitive matching
    (The regex flags handle case, but normalization catches unicode tricks)
    """
    import html
    # Decode HTML entities (&lt; → <, &#105;&#103;&#110;&#111;&#114;&#101; → ignore)
    text = html.unescape(text)
    # Unicode normalization — collapses look-alike characters
    text = unicodedata.normalize('NFKC', text)
    # Collapse excessive whitespace (some attacks use extra spaces between chars)
    text = re.sub(r'\s+', ' ', text)
    return text


def scan(content: str) -> Layer1Result:
    """
    Main entry point for Layer 1.
    Scans content against the injection grammar DFA.
    Uses Rust compiled DFA if available, otherwise Python re fallback.
    Returns a Layer1Result with full forensic detail.
    """
    normalized = normalize_content(content)

    flagged_spans = []
    categories_hit = set()
    max_weight = 0.0

    if _USE_RUST:
        # Rust DFA scanner: true compiled DFA + SIMD acceleration
        matches = _rust_scan_patterns(normalized)
        for m in matches:
            flagged_spans.append((m.start, m.end, m.matched_text, m.category))
            categories_hit.add(m.category)
            max_weight = max(max_weight, m.weight)
    else:
        # Python re fallback (backtracking NFA)
        for category, pattern in INJECTION_GRAMMAR:
            for match in pattern.finditer(normalized):
                flagged_spans.append((
                    match.start(),
                    match.end(),
                    match.group(0),
                    category
                ))
                categories_hit.add(category)
                weight = CATEGORY_WEIGHTS.get(category, 0.5)
                max_weight = max(max_weight, weight)

    # Risk score: if any high-weight pattern fires, score is high
    # Multiple patterns of different categories increase score
    category_score = len(categories_hit) / len(CATEGORY_WEIGHTS)
    risk_score = min(1.0, (max_weight * 0.7) + (category_score * 0.3))

    is_flagged = len(flagged_spans) > 0

    return Layer1Result(
        is_flagged=is_flagged,
        risk_score=risk_score if is_flagged else 0.0,
        flagged_spans=flagged_spans,
        pattern_categories_hit=list(categories_hit),
        raw_content=content,
        normalized_content=normalized
    )
