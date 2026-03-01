"""
Tool Registration Firewall (MCP Tool Poisoning Scanner)
=======================================================
Research basis: MCPTox (arXiv 2508.14925), Systematic Analysis of MCP Security
(arXiv 2512.08290). Tool poisoning embeds malicious instructions in tool
descriptions; agents trust metadata and execute hidden rules.

We run Layer 1 (lexical scan) on tool descriptions before the agent uses them.
"""

from dataclasses import dataclass
from typing import List

from .layer1_lexical import scan as l1_scan, Layer1Result


@dataclass
class ToolRegistrationResult:
    tool_name: str
    approved: bool
    reason: List[str]  # pattern_categories_hit if rejected
    risk_score: float


def scan_tool_registration(tool_name: str, tool_description: str) -> ToolRegistrationResult:
    """
    Scan a tool's description for injection patterns before the agent registers it.
    Returns approved=False if Layer 1 flags the description.
    """
    result: Layer1Result = l1_scan(tool_description)
    return ToolRegistrationResult(
        tool_name=tool_name,
        approved=not result.is_flagged,
        reason=result.pattern_categories_hit if result.is_flagged else [],
        risk_score=result.risk_score,
    )
