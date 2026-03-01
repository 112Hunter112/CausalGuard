"""
CausalGuard Interceptor
========================
The main middleware component. Sits between the agent's tool calls and
the outside world. Orchestrates all three detection layers and the purifier.

This is what you show to judges in the demo — every line of terminal output
comes through here.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List
import os

from .layer1_lexical import scan as l1_scan, Layer1Result
from .layer2_counterfactual import analyze as l2_analyze, Layer2Result
from .layer3_semantic import analyze as l3_analyze, Layer3Result
from .layer4_tool_monitor import monitor_tool_calls, Layer4Result, infer_task_type
from .layer5_neural_ode import (
    analyze_session as l5_analyze_session,
    ensure_layer5_model,
    Layer5Result,
)
from .layer6_taint import analyze as l6_analyze, Layer6Result
from .purifier import purify, PurifierResult
from .dashboard import Dashboard
from .attack_taxonomy import build_attack_anatomy, AttackAnatomy
from .tool_registration import scan_tool_registration, ToolRegistrationResult


@dataclass
class GuardReport:
    """Complete forensic report from all CausalGuard layers."""
    tool_name: str
    original_content: str
    processed_content: str
    was_flagged: bool
    final_decision: str  # "PASS", "PURIFY", "BLOCK"
    l1_result: Optional[Layer1Result]
    l2_result: Optional[Layer2Result]
    l3_result: Optional[Layer3Result]
    purifier_result: Optional[PurifierResult]
    total_latency_ms: float
    threat_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    attack_anatomy: Optional[AttackAnatomy] = None
    l4_result: Optional[Layer4Result] = None
    l5_result: Optional[Layer5Result] = None
    l6_result: Optional[Layer6Result] = None


class CausalGuard:
    def __init__(self, llm_client, dashboard: Optional[Dashboard] = None):
        self.llm = llm_client
        self.dashboard = dashboard
        
        # Load thresholds from environment
        self.l2_kl_threshold = float(os.getenv("LAYER2_KL_THRESHOLD", "0.8"))
        self.l2_jsd_threshold = float(os.getenv("LAYER2_JSD_THRESHOLD", "0.6"))
        self.l2_jaccard_threshold = float(os.getenv("LAYER2_JACCARD_THRESHOLD", "0.5"))
        self.l3_cosine_threshold = float(os.getenv("LAYER3_COSINE_THRESHOLD", "0.75"))
        
        self.l1_enabled = os.getenv("LAYER1_ENABLED", "true").lower() == "true"
        self.l2_enabled = os.getenv("LAYER2_ENABLED", "true").lower() == "true"
        self.l3_enabled = os.getenv("LAYER3_ENABLED", "true").lower() == "true"
        self.l4_enabled = os.getenv("LAYER4_ENABLED", "true").lower() == "true"
        self.l5_enabled = os.getenv("LAYER5_ENABLED", "true").lower() == "true"
        self.l5_threshold = float(os.getenv("LAYER5_THRESHOLD", "0.15"))
        self.interception_log = []
        self.tool_registration_log: list[ToolRegistrationResult] = []
        self._l5_model: Optional[tuple] = None  # (ode, encoder) lazy-loaded

    def _l2_thresholds_for_task(
        self, task: str, tool_name: str, content_preview: str = ""
    ) -> Tuple[float, float, float, float]:
        """
        Use relaxed L2 thresholds when the user asked to read/summarise content.
        When content is a fetch_url error message (not real page content), use max relaxation.
        Returns (kl, jsd, jaccard, composite_threshold).
        """
        preview = (content_preview or "").strip()
        if (tool_name or "").lower() == "fetch_url" and preview.startswith("Error fetching URL"):
            return (0.995, 0.70, 0.55, 0.9)
        t = (task or "").lower()
        tool = (tool_name or "").lower()
        content_tools = ("read_email", "read_document", "read_file", "fetch_url", "web_search")
        is_content_tool = any(r in tool for r in content_tools)
        asks_summarise = "summar" in t or "summary" in t
        asks_details = "detail" in t or "info" in t or "webpage" in t or "web" in t or "page" in t
        asks_read = "read" in t or "check" in t or "inbox" in t or "email" in t or "link" in t or "open" in t
        if is_content_tool and (asks_summarise or asks_read or asks_details):
            # Strong relaxation: benign content often shifts action KL and composite; raise composite bar
            return (
                min(0.995, self.l2_kl_threshold * 1.5),
                min(0.70, self.l2_jsd_threshold * 1.3),
                min(0.55, self.l2_jaccard_threshold * 1.3),
                0.9,  # composite: only flag if causal_score > 0.9 (was 0.65)
            )
        return self.l2_kl_threshold, self.l2_jsd_threshold, self.l2_jaccard_threshold, 0.65

    def _l3_threshold_for_task(
        self, task: str, tool_name: str, content_preview: str = ""
    ) -> float:
        """
        For read/summarise/get-details tasks, only flag L3 when semantic drift is very large.
        When content is a fetch_url error message, use max relaxation (don't flag).
        """
        preview = (content_preview or "").strip()
        if (tool_name or "").lower() == "fetch_url" and preview.startswith("Error fetching URL"):
            return 0.45
        t = (task or "").lower()
        tool = (tool_name or "").lower()
        content_tools = ("read_email", "read_document", "read_file", "fetch_url", "web_search")
        is_content_tool = any(r in tool for r in content_tools)
        asks_summarise = "summar" in t or "summary" in t
        asks_details = "detail" in t or "info" in t or "webpage" in t or "web" in t or "page" in t
        asks_read = "read" in t or "check" in t or "inbox" in t or "email" in t or "link" in t or "open" in t
        if is_content_tool and (asks_summarise or asks_read or asks_details):
            # Flag only when similarity drops below 0.3 (very large drift); avoids FP on benign emails
            return max(0.28, self.l3_cosine_threshold - 0.45)
        return self.l3_cosine_threshold

    async def intercept(
        self,
        task: str,
        retrieved_content: str,
        tool_name: str = "unknown_tool",
        demo_pass_through: bool = False,
    ) -> Tuple[str, GuardReport]:
        """
        Main interception method. Called whenever the agent retrieves external content.

        demo_pass_through: If True and content is flagged, pass raw content through
        so the agent sees the injection and may attempt to follow it; L6 will then
        block the malicious action (e.g. send_email to attacker). Use only for the
        "email_attack_demo" scenario to show implicit following → block.
        """
        start_time = time.time()
        
        if self.dashboard:
            self.dashboard.show_intercept_start(tool_name, len(retrieved_content))
        
        l1_result = None
        l2_result = None
        l3_result = None
        purifier_result = None
        flags = []

        # ─────────────── PARALLEL: LAYER 1 + LAYER 2 ───────────────
        # L1 (CPU-bound DFA ~1ms) and L2 (IO-bound LLM ~3s) are independent.
        # Run them concurrently with asyncio.gather for wall-clock savings.

        async def _run_l1():
            if not self.l1_enabled:
                return None
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, l1_scan, retrieved_content)

        async def _run_l2():
            if not self.l2_enabled:
                return None
            preview = (retrieved_content or "")[:80]
            kl, jsd, jacc, composite = self._l2_thresholds_for_task(task, tool_name, preview)
            return await l2_analyze(
                task=task,
                retrieved_content=retrieved_content,
                llm_client=self.llm,
                kl_threshold=kl,
                jsd_threshold=jsd,
                jaccard_threshold=jacc,
                composite_threshold=composite,
            )

        l1_result, l2_result = await asyncio.gather(_run_l1(), _run_l2())

        # Show results (L1 first for dashboard ordering)
        if l1_result:
            if self.dashboard:
                self.dashboard.show_l1_result(l1_result)
            if l1_result.is_flagged:
                flags.append("L1")

        if l2_result:
            if self.dashboard:
                self.dashboard.show_l2_result(l2_result)
            if l2_result.is_flagged:
                flags.append("L2")

        # ─────────────── LAYER 3 (depends on L2 output) ───────────────
        if self.l3_enabled and l2_result:
            baseline_text = l2_result.baseline_intent.action_description if l2_result.baseline_intent else task
            full_text = l2_result.full_intent.action_description if l2_result.full_intent else retrieved_content[:200]
            preview = (retrieved_content or "")[:80]
            l3_cosine = self._l3_threshold_for_task(task, tool_name, preview)

            l3_result = l3_analyze(
                baseline_action_text=baseline_text,
                full_action_text=full_text,
                cosine_threshold=l3_cosine
            )
            if self.dashboard:
                self.dashboard.show_l3_result(l3_result)
            if l3_result.is_flagged:
                flags.append("L3")
        
        # ─────────────── DECISION ───────────────
        # Smart decision: L2/L3 are semantic layers that can false-positive on
        # benign content describing actions (code, logs, security articles).
        # L1 is a high-precision pattern layer. Require structural corroboration
        # for semantic-only flags at intercept time.
        has_l1 = "L1" in flags
        semantic_only = flags and not has_l1  # at intercept time, only L1/L2/L3 available
        if semantic_only:
            # Semantic-only: only purify if L2 has very high causal score
            if l2_result and l2_result.is_flagged and l2_result.causal_divergence_score > 0.90:
                pass  # keep flags, will purify
            else:
                flags = []  # clear flags — likely false positive

        if flags:
            # Injection detected — purify unless demo_pass_through (show AI following, then L6 blocks)
            if demo_pass_through:
                processed_content = retrieved_content
                purifier_result = None
                final_decision = "PASS_THROUGH_DEMO"
            else:
                purifier_result = purify(retrieved_content)
                processed_content = purifier_result.purified_content
                final_decision = "PURIFY"

            num_flags = len(flags)
            if num_flags == 3:
                threat_level = "CRITICAL"
            elif num_flags == 2:
                threat_level = "HIGH"
            elif "L1" in flags or (l2_result and l2_result.causal_divergence_score > 0.9):
                threat_level = "HIGH"
            else:
                threat_level = "MEDIUM"
        else:
            processed_content = retrieved_content
            final_decision = "PASS"
            threat_level = "LOW"
        
        # Attack anatomy (Log-To-Leak taxonomy) when flagged
        attack_anatomy = None
        if flags and (l1_result or l2_result):
            l1_spans = l1_result.flagged_spans if l1_result else []
            l2_shift = l2_result.is_flagged if l2_result else False
            l2_action = l2_result.full_intent.action_type if l2_result and l2_result.full_intent else None
            l2_target = l2_result.full_intent.primary_target if l2_result and l2_result.full_intent else None
            attack_anatomy = build_attack_anatomy(
                l1_spans, l2_action_shift=l2_shift,
                l2_full_intent_action=l2_action, l2_full_target=l2_target,
            )
            if self.dashboard:
                self.dashboard.show_attack_anatomy(attack_anatomy)

        if self.dashboard:
            self.dashboard.show_decision(final_decision, threat_level, flags, purifier_result)

        latency = (time.time() - start_time) * 1000

        report = GuardReport(
            tool_name=tool_name,
            original_content=retrieved_content,
            processed_content=processed_content,
            was_flagged=len(flags) > 0,
            final_decision=final_decision,
            l1_result=l1_result,
            l2_result=l2_result,
            l3_result=l3_result,
            purifier_result=purifier_result,
            total_latency_ms=latency,
            threat_level=threat_level,
            attack_anatomy=attack_anatomy,
            l4_result=None,
        )

        self.interception_log.append(report)
        return processed_content, report

    def scan_tool_registration(self, tool_name: str, tool_description: str) -> ToolRegistrationResult:
        """MCP Tool Poisoning Scanner: scan tool description before agent uses it."""
        result = scan_tool_registration(tool_name, tool_description)
        self.tool_registration_log.append(result)
        if self.dashboard:
            self.dashboard.show_tool_registration(result)
        return result

    def report_tool_calls(self, task: str, actual_tool_calls: list[str]) -> Optional[Layer4Result]:
        """Layer 4: Check for unexpected tool invocations (Log-To-Leak). Call after agent run.
        Also runs Layer 5 (Neural ODE behavioral dynamics) if enabled and model is available."""
        if not self.l4_enabled:
            return None
        task_type = infer_task_type(task)
        l4_result = monitor_tool_calls(task_type, actual_tool_calls, task=task)
        if self.interception_log:
            self.interception_log[-1].l4_result = l4_result
        if self.dashboard:
            self.dashboard.show_l4_result(l4_result)

        # Layer 5: Neural ODE trajectory anomaly (optional, requires trained checkpoint)
        if self.l5_enabled and len(actual_tool_calls) >= 2:
            if self._l5_model is None:
                self._l5_model = ensure_layer5_model(train_if_missing=False)
            if self._l5_model is not None:
                ode, encoder = self._l5_model
                session = [(task_type, t) for t in actual_tool_calls]
                l5_result = l5_analyze_session(
                    ode, encoder, session, threshold=self.l5_threshold
                )
                if self.interception_log:
                    self.interception_log[-1].l5_result = l5_result
                if self.dashboard:
                    self.dashboard.show_l5_result(l5_result)
        return l4_result

    async def report_tool_calls_parallel(
        self,
        task: str,
        actual_tool_calls: list[str],
        proposed_tool_call: Optional[dict] = None,
    ) -> tuple:
        """Run L4, L5, L6 in parallel using asyncio.gather.
        Returns (l4_result, l5_result, l6_result)."""

        task_type = infer_task_type(task)

        async def _run_l4():
            if not self.l4_enabled:
                return None
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: monitor_tool_calls(task_type, actual_tool_calls, task=task)
            )

        async def _run_l5():
            if not self.l5_enabled or len(actual_tool_calls) < 2:
                return None
            if self._l5_model is None:
                self._l5_model = ensure_layer5_model(train_if_missing=False)
            if self._l5_model is None:
                return None
            ode, encoder = self._l5_model
            session = [(task_type, t) for t in actual_tool_calls]
            return l5_analyze_session(ode, encoder, session, threshold=self.l5_threshold)

        async def _run_l6():
            if proposed_tool_call is None:
                return None
            last_content = ""
            if self.interception_log:
                last_content = self.interception_log[-1].original_content
            return l6_analyze(task, last_content, proposed_tool_call)

        l4_result, l5_result, l6_result = await asyncio.gather(
            _run_l4(), _run_l5(), _run_l6()
        )

        # Update last report and show dashboard
        if self.interception_log:
            if l4_result:
                self.interception_log[-1].l4_result = l4_result
            if l5_result:
                self.interception_log[-1].l5_result = l5_result
            if l6_result:
                self.interception_log[-1].l6_result = l6_result

        if self.dashboard:
            if l4_result:
                self.dashboard.show_l4_result(l4_result)
            if l5_result:
                self.dashboard.show_l5_result(l5_result)
            if l6_result:
                self.dashboard.show_l6_result(l6_result)

        return l4_result, l5_result, l6_result

    async def check_sink_before_execute(
        self, task: str, tool_name: str, args: dict
    ) -> Tuple[bool, Optional[Layer6Result]]:
        """
        Run L6 on a proposed send_email/write_file before executing.
        Returns (allow, l6_result). If not allow, the agent should not execute the tool.
        """
        proposed = {"tool": tool_name, "args": args or {}}
        last_content = ""
        if self.interception_log:
            last_content = self.interception_log[-1].original_content
        loop = asyncio.get_running_loop()
        l6_result = await loop.run_in_executor(
            None,
            lambda: l6_analyze(task, last_content, proposed),
        )
        allow = not l6_result.is_flagged
        return allow, l6_result
