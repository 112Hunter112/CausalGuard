"""
Layer 6: Dual-Lattice Taint Propagation Engine (Information Flow Control)
=========================================================================
Mathematical Foundation: Information Flow Control (IFC) via Security Lattices

A security lattice is a partially ordered set (L, ⊑) where:
  L = {TRUSTED, UNTRUSTED}
  TRUSTED ⊑ UNTRUSTED  (TRUSTED is the bottom element ⊥)

Label propagation rule (join operation):
  label(f(x₁,...,xₙ)) = label(x₁) ⊔ ... ⊔ label(xₙ)
  i.e., the output label is the least upper bound of input labels.
  Conservative/sound: if ANY input is UNTRUSTED, the output is UNTRUSTED.

Sink policy enforcement:
  For each tool call t(args):
    For each arg aᵢ that maps to a sensitive sink sᵢ:
      If label(aᵢ) = UNTRUSTED AND sᵢ ∈ RESTRICTED_SINKS:
        BLOCK tool call with PolicyViolation

Research basis:
  - FIDES: Costa et al. (2025). Securing AI Agents with IFC. arXiv:2505.23643
  - CaMeL: Debenedetti et al. (2025). Defeating Prompt Injections by Design. arXiv:2503.18813
  - MVAR: IFC for LLM Agent Runtimes (GitHub: mvar-security/mvar, 2025)
  - Denning & Denning (1977). Certification of Programs for Secure Information Flow. CACM.
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import time


class TrustLabel(IntEnum):
    """
    The security lattice L = {TRUSTED=0, UNTRUSTED=1}.
    Join via max(): label_a ⊔ label_b = max(label_a, label_b)
    """
    TRUSTED = 0
    UNTRUSTED = 1

    def join(self, other: "TrustLabel") -> "TrustLabel":
        """Lattice join (least upper bound)."""
        return TrustLabel(max(self.value, other.value))

    def __str__(self) -> str:
        return "TRUSTED" if self == TrustLabel.TRUSTED else "UNTRUSTED"


@dataclass
class TaintedValue:
    """A value annotated with its trust label and provenance chain."""
    value: Any
    label: TrustLabel
    provenance: str
    created_at: float = field(default_factory=time.time)
    derived_from: List[str] = field(default_factory=list)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            raw = str(self.value).encode("utf-8", errors="replace")
            self.content_hash = hashlib.sha256(raw).hexdigest()[:16]


# Sensitive sinks — parameters that must not receive UNTRUSTED data
RESTRICTED_SINKS = {
    "send_email": {"recipient", "to", "cc", "bcc"},
    "write_file": {"path", "filename", "destination"},
    "http_request": {"url", "endpoint", "host"},
    "execute_code": {"code", "command", "script"},
    "database_query": {"query", "sql"},
    "api_call": {"endpoint", "url", "target"},
    "upload_file": {"destination", "url", "target"},
}

TRUSTED_SOURCES = {"user_query", "system_config", "operator_task"}


@dataclass
class PolicyViolation:
    tool_name: str
    parameter: str
    tainted_value: "TaintedValue"
    policy_rule: str
    blocked: bool = True


@dataclass
class Layer6Result:
    is_flagged: bool
    policy_violations: List[PolicyViolation]
    taint_graph: Dict[str, TaintedValue]
    context_label: TrustLabel
    enforcement_decision: str  # "ALLOW", "BLOCK", "QUARANTINE"
    explanation: str


class TaintTracker:
    """Maintains taint state across an agent session."""

    def __init__(self) -> None:
        self.taint_graph: Dict[str, TaintedValue] = {}
        self.context_label: TrustLabel = TrustLabel.TRUSTED
        self.violation_log: List[PolicyViolation] = []

    def label_user_input(self, name: str, value: str) -> TaintedValue:
        """User queries are TRUSTED."""
        tv = TaintedValue(value=value, label=TrustLabel.TRUSTED, provenance=f"user_input:{name}")
        self.taint_graph[name] = tv
        return tv

    def label_retrieved_content(
        self, name: str, value: str, source_url: str = ""
    ) -> TaintedValue:
        """All externally retrieved content is UNTRUSTED by default."""
        tv = TaintedValue(
            value=value,
            label=TrustLabel.UNTRUSTED,
            provenance=f"external:{source_url or name}",
        )
        self.taint_graph[name] = tv
        self.context_label = self.context_label.join(TrustLabel.UNTRUSTED)
        return tv

    def propagate(
        self,
        output_name: str,
        output_value: Any,
        input_names: List[str],
    ) -> TaintedValue:
        """
        Propagate labels: output_label = JOIN(label(input₁), ..., label(inputₙ)).
        """
        input_labels: List[TrustLabel] = []
        parent_provenances: List[str] = []

        for name in input_names:
            if name in self.taint_graph:
                input_labels.append(self.taint_graph[name].label)
                parent_provenances.append(self.taint_graph[name].provenance)

        result_label = TrustLabel.TRUSTED
        for lbl in input_labels:
            result_label = result_label.join(lbl)

        tv = TaintedValue(
            value=output_value,
            label=result_label,
            provenance=f"derived:{output_name}",
            derived_from=parent_provenances,
        )
        self.taint_graph[output_name] = tv
        return tv

    def check_tool_call(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Tuple[bool, List[PolicyViolation]]:
        """Enforce sink policies before a tool call executes."""
        violations: List[PolicyViolation] = []
        restricted_params = RESTRICTED_SINKS.get(tool_name.lower(), set())

        for param_name, param_value in args.items():
            tainted: Optional[TaintedValue] = None

            for key, tv in self.taint_graph.items():
                if str(tv.value) == str(param_value) or key == param_name:
                    tainted = tv
                    break

            if tainted is None:
                tainted = TaintedValue(
                    value=param_value,
                    label=self.context_label,
                    provenance=f"context_derived:{param_name}",
                )

            if (
                param_name.lower() in restricted_params
                and tainted.label == TrustLabel.UNTRUSTED
            ):
                violation = PolicyViolation(
                    tool_name=tool_name,
                    parameter=param_name,
                    tainted_value=tainted,
                    policy_rule=(
                        f"UNTRUSTED data cannot flow to sink '{param_name}' of '{tool_name}'"
                    ),
                )
                violations.append(violation)
                self.violation_log.append(violation)

        return len(violations) == 0, violations


def analyze(
    user_task: str,
    retrieved_content: str,
    proposed_tool_call: Dict[str, Any],
    source_url: str = "",
) -> Layer6Result:
    """
    Main entry point for Layer 6. Full taint analysis on a proposed tool call.
    Only retrieved content that was actually fetched is treated as UNTRUSTED;
    when none was retrieved (e.g. user said "send email to X" with no prior read),
    context stays TRUSTED so user-intended recipients are allowed.
    """
    tracker = TaintTracker()

    tracker.label_user_input("user_task", user_task)
    # Only label retrieved content when there was actual external content; empty => no UNTRUSTED source
    if (retrieved_content or "").strip():
        tracker.label_retrieved_content(
            "retrieved_content", retrieved_content, source_url
        )
        tracker.propagate(
            output_name="llm_decision",
            output_value=str(proposed_tool_call),
            input_names=["user_task", "retrieved_content"],
        )
    else:
        tracker.propagate(
            output_name="llm_decision",
            output_value=str(proposed_tool_call),
            input_names=["user_task"],
        )

    tool_name = proposed_tool_call.get("tool", "unknown")
    tool_args = proposed_tool_call.get("args", {})
    safe, violations = tracker.check_tool_call(tool_name, tool_args)

    if violations:
        decision = "BLOCK"
        content_preview = (retrieved_content[:50] + "...") if len(retrieved_content) > 50 else retrieved_content
        explanation = (
            f"POLICY VIOLATION: UNTRUSTED data from '{content_preview}' "
            f"attempting to flow into restricted sink(s): "
            f"{', '.join(v.parameter for v in violations)} of {tool_name}(). "
            f"Context integrity label: {tracker.context_label}. "
            "Provable security — this tool call cannot execute regardless of LLM behavior."
        )
    else:
        decision = "ALLOW"
        explanation = f"No policy violations. Context label: {tracker.context_label}."

    return Layer6Result(
        is_flagged=len(violations) > 0,
        policy_violations=violations,
        taint_graph=tracker.taint_graph,
        context_label=tracker.context_label,
        enforcement_decision=decision,
        explanation=explanation,
    )
