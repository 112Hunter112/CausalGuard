"""
Tool Output Integrity (Zero-Trust Tool Layer)
==============================================
Research: Cryptographic protocols and authenticated channels — MACs, digital
signatures, or attestation — disrupt communication and supply-chain-based
injection. (ACL Anthology, agent security survey.)

When a tool produces output, we sign it with HMAC-SHA256. CausalGuard verifies
the signature before passing content to detection layers. If the signature
doesn't match, the content was tampered in transit — immediate BLOCK.

No dependency on generative AI. Constant-time comparison to prevent timing attacks.
"""

import hmac
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple


TOOL_SECRET = os.getenv("CAUSALGUARD_HMAC_SECRET", "dev-secret-change-in-prod")


def sign_tool_output(tool_name: str, content: str, timestamp: Optional[float] = None) -> str:
    """Sign tool output with HMAC-SHA256."""
    if timestamp is None:
        timestamp = time.time()
    message = json.dumps(
        {"tool": tool_name, "content": content, "ts": timestamp},
        sort_keys=True,
    )
    return hmac.new(
        TOOL_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_tool_output(
    tool_name: str,
    content: str,
    timestamp: float,
    signature: str,
) -> bool:
    """Constant-time HMAC verification (timing-attack resistant)."""
    expected = sign_tool_output(tool_name, content, timestamp)
    return hmac.compare_digest(expected, signature)


@dataclass
class SignedToolOutput:
    tool_name: str
    content: str
    timestamp: float
    signature: str

    def verify(self) -> bool:
        return verify_tool_output(
            self.tool_name, self.content, self.timestamp, self.signature
        )


def wrap_tool_output(tool_name: str, content: str) -> dict:
    """Produce a signed payload for transport. Call after tool execution."""
    ts = time.time()
    sig = sign_tool_output(tool_name, content, ts)
    return {
        "tool": tool_name,
        "content": content,
        "timestamp": ts,
        "signature": sig,
    }


def unwrap_and_verify(payload: dict) -> Tuple[bool, str]:
    """
    Verify signature and return (ok, content). If not ok, content is empty
    and caller should BLOCK without passing to detection layers.
    """
    try:
        tool = payload.get("tool", "")
        content = payload.get("content", "")
        ts = payload.get("timestamp", 0)
        sig = payload.get("signature", "")
        if not all([tool, sig]):
            return False, ""
        if verify_tool_output(tool, content, ts, sig):
            return True, content
    except (TypeError, KeyError):
        pass
    return False, ""
