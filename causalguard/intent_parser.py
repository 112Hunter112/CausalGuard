"""
Intent Parser
=============
Parses LLM output into a structured IntentObject for mathematical comparison.
The agent is prompted to output its intended action as JSON.
This module parses that JSON into a typed dataclass.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class IntentObject:
    """
    Represents the agent's intended next action as a structured object.
    All fields are comparable for divergence calculation.
    """
    action_type: str                    # e.g., "send_email", "read_file", "summarize"
    primary_target: Optional[str]       # e.g., recipient email, filename, URL
    secondary_targets: List[str]        # e.g., CC recipients, additional files
    parameters: Dict[str, Any]          # All other key-value parameters
    action_description: str             # Natural language description of the action
    raw_output: str                     # Original LLM output for Layer 3


def _extract_json_object(text: str) -> Optional[str]:
    """Extract the first complete {...} object, supporting nested braces."""
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    quote = None
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c in ('"', "'") and not in_string:
            in_string = True
            quote = c
            continue
        if c == quote:
            in_string = False
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_intent(llm_output: str) -> IntentObject:
    """
    Attempt to parse LLM output as structured JSON intent.
    Falls back to heuristic extraction if JSON parsing fails.
    """
    # Try JSON parsing first (support nested objects)
    json_str = _extract_json_object(llm_output)
    if json_str:
        try:
            data = json.loads(json_str)
            st = data.get("secondary_targets", [])
            if not isinstance(st, list):
                st = [st] if st is not None else []
            return IntentObject(
                action_type=(data.get("action_type") or "unknown").lower().strip(),
                primary_target=data.get("primary_target") or data.get("recipient") or data.get("target"),
                secondary_targets=st,
                parameters={k: v for k, v in data.items()
                           if k not in ("action_type", "primary_target", "secondary_targets", "description", "recipient", "target")},
                action_description=data.get("description", llm_output[:200]),
                raw_output=llm_output
            )
        except json.JSONDecodeError:
            pass

    # Heuristic fallback
    action_type = "unknown"
    primary_target = None
    
    # Detect action type from keywords
    output_lower = llm_output.lower()
    if any(w in output_lower for w in ["send_email", "send email", "email"]):
        action_type = "send_email"
    elif any(w in output_lower for w in ["read_file", "read file", "open file"]):
        action_type = "read_file"
    elif any(w in output_lower for w in ["summarize", "summary"]):
        action_type = "summarize"
    elif any(w in output_lower for w in ["delete", "remove"]):
        action_type = "delete"
    elif any(w in output_lower for w in ["upload", "post to", "send to"]):
        action_type = "upload"
    elif any(w in output_lower for w in ["search", "look up", "find"]):
        action_type = "search"
    
    # Extract email address if present
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', llm_output)
    if email_match:
        primary_target = email_match.group(0)
    
    # Extract URL if present
    url_match = re.search(r'https?://\S+', llm_output)
    if url_match and not primary_target:
        primary_target = url_match.group(0)

    return IntentObject(
        action_type=action_type,
        primary_target=primary_target,
        secondary_targets=[],
        parameters={},
        action_description=llm_output[:300],
        raw_output=llm_output
    )
