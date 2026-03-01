"""
Layer 4: Tool Invocation Anomaly Detector
==========================================
Research basis: Log-To-Leak (OpenReview 2025), MCPTox (arXiv 2508.14925)

Log-To-Leak attacks covertly force agents to invoke malicious logging tools
to exfiltrate information while preserving task quality — invisible to
output-based detection. This layer monitors the SET of tools invoked:
unexpected_tools = actual_calls - expected_calls (pure set-difference math).

No trainable parameters. Resistant to gradient/RL adaptive attacks.
"""

from dataclasses import dataclass
from typing import List, Set


# Expected tool sets per task type (baseline profile)
# Extend this as you add more task types and tools.
TASK_TOOL_PROFILES = {
    "summarize": {"read_document"},
    "email_draft": {"read_document", "send_email"},
    "search": {"web_search"},
    "read_file": {"read_document"},
    "review_document": {"read_document"},
}


@dataclass
class Layer4Result:
    flagged: bool
    unexpected_tools: List[str]
    expected_tools: List[str]
    actual_tools: List[str]
    jaccard_anomaly_score: float
    task_type: str


def infer_task_type(task: str) -> str:
    """Infer task type from user instruction for profile lookup."""
    t = task.lower()
    if "email" in t and ("send" in t or "draft" in t):
        return "email_draft"
    if "search" in t or "look up" in t or "find" in t:
        return "search"
    if "summarize" in t or "summary" in t:
        return "summarize"
    if "review" in t or "read" in t:
        return "review_document"
    return "summarize"  # default


def monitor_tool_calls(
    task_type: str,
    actual_tool_calls: List[str],
    task: str = "",
) -> Layer4Result:
    """
    Compare actual tool invocations to the expected profile for this task type.
    Any tool not in the expected set is flagged (Log-To-Leak style attack).
    """
    if task and task_type == "summarize":
        task_type = infer_task_type(task)
    expected: Set[str] = TASK_TOOL_PROFILES.get(task_type, set())
    actual: Set[str] = set(actual_tool_calls)
    unexpected = actual - expected
    # Jaccard anomaly: fraction of actual calls that were unexpected
    jaccard_anomaly = len(unexpected) / len(actual) if actual else 0.0
    return Layer4Result(
        flagged=len(unexpected) > 0,
        unexpected_tools=sorted(unexpected),
        expected_tools=sorted(expected),
        actual_tools=sorted(actual),
        jaccard_anomaly_score=jaccard_anomaly,
        task_type=task_type,
    )
