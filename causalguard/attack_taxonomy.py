"""
Attack Taxonomy (Log-To-Leak Four-Component Framework)
=======================================================
Research basis: Log-To-Leak (OpenReview 2025) — systematizes injection payloads
into: Trigger, Tool Binding, Justification, Pressure.

When CausalGuard flags an injection, we classify detected spans into these
components for forensic display to judges.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# Map Layer 1 categories to Log-To-Leak taxonomy components
CATEGORY_TO_COMPONENT = {
    "DIRECT_HIJACK": "Trigger",
    "ROLE_SWITCH": "Trigger",
    "CONTEXT_TERMINATION": "Trigger",
    "ENCODING_OBFUSCATION": "Trigger",
    "EXFILTRATION": "Tool Binding",
    "GOAL_HIJACK": "Pressure",
    "PRIVILEGE_ESCALATION": "Justification",
}


@dataclass
class AttackAnatomy:
    """Per-component list of (matched_text, layer_tag)."""
    trigger: List[Tuple[str, str]] = field(default_factory=list)
    tool_binding: List[Tuple[str, str]] = field(default_factory=list)
    justification: List[Tuple[str, str]] = field(default_factory=list)
    pressure: List[Tuple[str, str]] = field(default_factory=list)

    def to_dict(self):
        return {
            "Trigger": [{"text": t, "source": s} for t, s in self.trigger],
            "Tool Binding": [{"text": t, "source": s} for t, s in self.tool_binding],
            "Justification": [{"text": t, "source": s} for t, s in self.justification],
            "Pressure": [{"text": t, "source": s} for t, s in self.pressure],
        }


def build_attack_anatomy(
    l1_flagged_spans: List[Tuple[int, int, str, str]],
    l2_action_shift: bool = False,
    l2_full_intent_action: Optional[str] = None,
    l2_full_target: Optional[str] = None,
) -> AttackAnatomy:
    """
    Classify flagged spans and L2 evidence into Log-To-Leak components.
    l1_flagged_spans: list of (start, end, matched_text, category)
    """
    anatomy = AttackAnatomy()
    for _start, _end, text, category in l1_flagged_spans:
        component = CATEGORY_TO_COMPONENT.get(category, "Trigger")
        tag = f"L1: {category}"
        if component == "Trigger":
            anatomy.trigger.append((text, tag))
        elif component == "Tool Binding":
            anatomy.tool_binding.append((text, tag))
        elif component == "Justification":
            anatomy.justification.append((text, tag))
        elif component == "Pressure":
            anatomy.pressure.append((text, tag))

    if l2_action_shift and l2_full_intent_action:
        action_desc = l2_full_intent_action
        if l2_full_target:
            action_desc += f" (to={l2_full_target})"
        anatomy.tool_binding.append((action_desc, "L2: ACTION_SHIFT"))
    return anatomy
