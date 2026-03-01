use pyo3::prelude::*;
use regex::Regex;
use std::sync::LazyLock;

// ─────────────────────────────────────────────────────────────
// Pattern definition: mirrors causalguard/layer1_lexical.py
// ─────────────────────────────────────────────────────────────

struct PatternDef {
    category: &'static str,
    regex: Regex,
    weight: f64,
}

static PATTERNS: LazyLock<Vec<PatternDef>> = LazyLock::new(|| {
    vec![
        // CATEGORY 1: Direct imperative hijacks (weight 1.0)
        PatternDef {
            category: "DIRECT_HIJACK",
            regex: Regex::new(r"(?i)(ignore\s+(all\s+)?(previous|prior|above|earlier|your|the\s+above)\s+(instructions?|prompts?|commands?|context|rules?|constraints?))").unwrap(),
            weight: 1.0,
        },
        PatternDef {
            category: "DIRECT_HIJACK",
            regex: Regex::new(r"(?i)(disregard\s+(all\s+)?(previous|prior|above|earlier|your)\s+(instructions?|prompts?|commands?|context|rules?))").unwrap(),
            weight: 1.0,
        },
        PatternDef {
            category: "DIRECT_HIJACK",
            regex: Regex::new(r"(?i)(forget\s+(everything|all|what|your)\s+(you\s+were\s+told|above|before|previously|prior))").unwrap(),
            weight: 1.0,
        },
        PatternDef {
            category: "DIRECT_HIJACK",
            regex: Regex::new(r"(?i)(override\s+(your\s+)?(previous|prior|current|existing)\s+(instructions?|programming|settings?|configuration))").unwrap(),
            weight: 1.0,
        },
        PatternDef {
            category: "DIRECT_HIJACK",
            regex: Regex::new(r"(?i)(new\s+instructions?|updated\s+instructions?|revised\s+instructions?)(\s+are|\s+follow|\s*:)").unwrap(),
            weight: 1.0,
        },

        // CATEGORY 2: Role-switching attacks (weight 0.8)
        PatternDef {
            category: "ROLE_SWITCH",
            regex: Regex::new(r"(?i)(you\s+are\s+now\s+(a|an|the)\s+)").unwrap(),
            weight: 0.8,
        },
        PatternDef {
            category: "ROLE_SWITCH",
            regex: Regex::new(r"(?i)(act\s+as\s+(a|an|the|if)\s+)").unwrap(),
            weight: 0.8,
        },
        PatternDef {
            category: "ROLE_SWITCH",
            regex: Regex::new(r"(?i)(pretend\s+(you\s+are|to\s+be)\s+)").unwrap(),
            weight: 0.8,
        },
        PatternDef {
            category: "ROLE_SWITCH",
            regex: Regex::new(r"(?i)(your\s+(new\s+)?(role|identity|persona|name)\s+is\s+)").unwrap(),
            weight: 0.8,
        },
        PatternDef {
            category: "ROLE_SWITCH",
            regex: Regex::new(r"(?i)(switch\s+(your\s+)?(role|mode|behavior|personality)\s+to\s+)").unwrap(),
            weight: 0.8,
        },

        // CATEGORY 3: Privilege escalation (weight 0.9)
        PatternDef {
            category: "PRIVILEGE_ESCALATION",
            regex: Regex::new(r"(?i)(you\s+(now\s+)?(have\s+)?(permission|authorization|authority|access)\s+to\s+)").unwrap(),
            weight: 0.9,
        },
        PatternDef {
            category: "PRIVILEGE_ESCALATION",
            regex: Regex::new(r"(?i)((the\s+)?(admin|administrator|operator|system|developer|owner)\s+(says?|confirms?|grants?|allows?|authorizes?)\s+)").unwrap(),
            weight: 0.9,
        },
        PatternDef {
            category: "PRIVILEGE_ESCALATION",
            regex: Regex::new(r"(?i)(this\s+is\s+(a\s+)?(test|authorized\s+test|security\s+test|drill)[\.,]?\s+(you\s+(should|must|can|may))\s+)").unwrap(),
            weight: 0.9,
        },
        PatternDef {
            category: "PRIVILEGE_ESCALATION",
            regex: Regex::new(r"(?i)(security\s+level\s+(cleared?|upgraded?|elevated?|set\s+to))").unwrap(),
            weight: 0.9,
        },

        // CATEGORY 4: Data exfiltration commands (weight 1.0)
        PatternDef {
            category: "EXFILTRATION",
            regex: Regex::new(r"(?i)(send\s+(all\s+)?(files?|data|information|contents?|emails?|documents?)\s+to\s+\S+@\S+)").unwrap(),
            weight: 1.0,
        },
        PatternDef {
            category: "EXFILTRATION",
            regex: Regex::new(r"(?i)(email\s+(the\s+)?(contents?|data|files?|results?|output)\s+to\s+\S+@\S+)").unwrap(),
            weight: 1.0,
        },
        PatternDef {
            category: "EXFILTRATION",
            regex: Regex::new(r"(?i)(forward\s+(all\s+)?(messages?|emails?|files?|data)\s+to\s+\S+@\S+)").unwrap(),
            weight: 1.0,
        },
        PatternDef {
            category: "EXFILTRATION",
            regex: Regex::new(r"(?i)(upload\s+(all\s+)?(files?|data|documents?)\s+to\s+(https?://|ftp://)\S+)").unwrap(),
            weight: 1.0,
        },

        // CATEGORY 5: Context termination attacks (weight 0.85)
        PatternDef {
            category: "CONTEXT_TERMINATION",
            regex: Regex::new(r"(?i)(</?(system|user|assistant|human|ai|context|instruction)[^>]*>)").unwrap(),
            weight: 0.85,
        },
        PatternDef {
            category: "CONTEXT_TERMINATION",
            regex: Regex::new(r"(?i)(\[SYSTEM\]|\[USER\]|\[INST\]|\[/INST\]|\[ASSISTANT\]|\[END\])").unwrap(),
            weight: 0.85,
        },
        PatternDef {
            category: "CONTEXT_TERMINATION",
            regex: Regex::new(r"(?i)(###\s*(system|instruction|human|assistant|new\s+task))").unwrap(),
            weight: 0.85,
        },

        // CATEGORY 6: Encoding obfuscation (weight 0.7)
        PatternDef {
            category: "ENCODING_OBFUSCATION",
            regex: Regex::new(r"(?i)(base64[_\s]*(decode|encoded|:)\s*[A-Za-z0-9+/]{20,}={0,2})").unwrap(),
            weight: 0.7,
        },
        PatternDef {
            category: "ENCODING_OBFUSCATION",
            regex: Regex::new(r"(?i)(eval\s*\(|exec\s*\(|decode\s*\()").unwrap(),
            weight: 0.7,
        },

        // CATEGORY 7: Goal hijacking (weight 0.95)
        PatternDef {
            category: "GOAL_HIJACK",
            regex: Regex::new(r"(?i)(your\s+(actual|real|true|primary|main|new|updated)\s+(task|goal|objective|mission|purpose|job)\s+(is|now\s+is|has\s+changed\s+to))").unwrap(),
            weight: 0.95,
        },
        PatternDef {
            category: "GOAL_HIJACK",
            regex: Regex::new(r"(?i)(instead\s+of\s+(that|the\s+above|what\s+you\s+were\s+told|your\s+task)[,\s]+\s*(you\s+(should|must|need\s+to|have\s+to)))").unwrap(),
            weight: 0.95,
        },
        PatternDef {
            category: "GOAL_HIJACK",
            regex: Regex::new(r"(?i)(complete\s+(this\s+)?(task|action|request)\s+first\s+before)").unwrap(),
            weight: 0.95,
        },
    ]
});

// ─────────────────────────────────────────────────────────────
// Python-exposed types and functions
// ─────────────────────────────────────────────────────────────

#[pyclass]
#[derive(Clone)]
struct ScanMatch {
    #[pyo3(get)]
    start: usize,
    #[pyo3(get)]
    end: usize,
    #[pyo3(get)]
    matched_text: String,
    #[pyo3(get)]
    category: String,
    #[pyo3(get)]
    weight: f64,
}

/// Scan normalized text against all 27 injection patterns.
/// Returns a Vec of ScanMatch with position, category, and weight.
#[pyfunction]
fn scan_patterns(normalized_text: &str) -> Vec<ScanMatch> {
    let mut results = Vec::new();
    for pat in PATTERNS.iter() {
        for m in pat.regex.find_iter(normalized_text) {
            results.push(ScanMatch {
                start: m.start(),
                end: m.end(),
                matched_text: m.as_str().to_string(),
                category: pat.category.to_string(),
                weight: pat.weight,
            });
        }
    }
    results
}

/// Python module definition
#[pymodule]
fn causalguard_scanner(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(scan_patterns, m)?)?;
    m.add_class::<ScanMatch>()?;
    Ok(())
}
