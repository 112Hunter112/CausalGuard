"""
Multi-Tool AI Agent for CausalGuard Demo
==========================================
A ReAct-style autonomous agent that plans multi-step tasks, uses tools,
and reasons about results. CausalGuard monitors EVERY tool call — each
website visited, each email read, each document opened.

The key insight: this agent does real work (reads real emails, searches
the real web). CausalGuard sits in the middle intercepting every piece of
external content before the agent sees it. Judges see a real AI agent
being protected in real-time.
"""

import asyncio
import inspect
import json
import os
import re
import ssl
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .scenarios import (
    EMAIL_INBOX,
    WEB_RESULTS,
    CALENDAR_EVENTS,
    SCENARIOS,
)


@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    tool_name: str
    args: dict
    raw_result: str
    processed_result: str
    was_intercepted: bool
    guard_report: Optional[object] = None


class MultiToolAgent:
    """
    A ReAct-style autonomous agent protected by CausalGuard.

    The agent autonomously:
    1. Plans which tools to use
    2. Executes tools (CausalGuard scans each one)
    3. Reasons about results
    4. Decides if more tool calls are needed
    5. Produces a final comprehensive response

    Tools available:
    - read_email: Read emails (real Gmail in live mode)
    - send_email: Send an email (simulated)
    - web_search: Search the web (real Google Search in live mode)
    - read_document: Read a document from disk
    - calendar_check: Check calendar events
    - write_file: Write content to a file (simulated)
    """

    MAX_STEPS = 5  # Safety limit on autonomous loops

    def __init__(self, llm_client, causalguard=None, scenario="email"):
        self.llm = llm_client
        self.guard = causalguard
        self.scenario = scenario
        self.tool_calls_log: list[ToolCall] = []
        self._live_mode = scenario in ("live", "live_email", "live_web")

    # ─────────────────────────────────────────────
    # TOOLS
    # ─────────────────────────────────────────────

    def read_email(self, email_id: int = None, count: int = 10, n: int = None, query: str = None) -> str:
        """
        Read emails from inbox.
        - email_id: fetch a specific email by id.
        - n: fetch the nth latest email (1 = most recent, 2 = 2nd latest). Ignored if email_id is set.
        - count: max number of emails to return when reading all (default 10). Uses real Gmail in live mode.
        - query: optional search (e.g. "Quora", "Jewish") — filter by subject/sender/body. In live mode uses Gmail search.
        """
        if self._live_mode:
            try:
                from .gmail_client import fetch_inbox, format_inbox
                emails = fetch_inbox(max_results=count, q=query)
                if email_id is not None:
                    for email in emails:
                        if email["id"] == email_id:
                            return (
                                f"From: {email['from']}\n"
                                f"Subject: {email['subject']}\n\n"
                                f"{email['body']}"
                            )
                    return "Email not found."
                if n is not None and 1 <= n <= len(emails):
                    email = emails[n - 1]  # Gmail returns newest-first
                    return (
                        f"From: {email['from']}\n"
                        f"Subject: {email['subject']}\n\n"
                        f"{email['body']}"
                    )
                return format_inbox(emails)
            except Exception as e:
                return f"Gmail error: {e}. Falling back to demo data."

        inbox = list(EMAIL_INBOX)
        if query and query.strip():
            q = query.strip().lower()
            inbox = [
                e for e in inbox
                if q in (e.get("subject") or "").lower()
                or q in (e.get("from") or "").lower()
                or q in (e.get("body") or "").lower()
            ]
            if not inbox:
                return f"No emails matched the search '{query}'."
        # nth latest: 1 = last in list (most recent), 2 = second to last, etc.
        if n is not None and 1 <= n <= len(inbox):
            email = inbox[-n]
            return (
                f"From: {email['from']}\n"
                f"Subject: {email['subject']}\n\n"
                f"{email['body']}"
            )
        if n is not None and (n < 1 or n > len(inbox)):
            return f"No email at position {n} (inbox has {len(inbox)} emails)."

        if email_id is not None:
            for email in inbox:
                if email["id"] == email_id:
                    return (
                        f"From: {email['from']}\n"
                        f"Subject: {email['subject']}\n\n"
                        f"{email['body']}"
                    )
            return "Email not found."
        parts = []
        for email in inbox:
            parts.append(
                f"--- Email #{email['id']} ---\n"
                f"From: {email['from']}\n"
                f"Subject: {email['subject']}\n\n"
                f"{email['body']}\n"
            )
        return "\n".join(parts)

    async def web_search(self, query: str = "") -> str:
        """Search the web using real Google Search grounding via Gemini."""
        if self._live_mode or query:
            try:
                search_query = query or "latest news"
                result = await self.llm.complete_with_search(
                    f"Search the web for: {search_query}\n\n"
                    f"Return detailed findings with URLs and key facts.",
                    max_tokens=1500,
                )
                if result and len(result.strip()) > 20:
                    return result
            except Exception as e:
                if self._live_mode:
                    return f"Google Search error: {e}"

        parts = []
        for i, result in enumerate(WEB_RESULTS, 1):
            parts.append(
                f"--- Result #{i} ---\n"
                f"Title: {result['title']}\n"
                f"URL: {result['url']}\n"
                f"Content:\n{result['content']}\n"
            )
        return "\n".join(parts)

    def calendar_check(self, date: str = "") -> str:
        """Check calendar events."""
        parts = []
        for event in CALENDAR_EVENTS:
            parts.append(
                f"--- {event['title']} ---\n"
                f"Date: {event['date']} at {event['time']}\n"
                f"Attendees: {', '.join(event['attendees'])}\n"
                f"Notes: {event['notes']}\n"
            )
        return "\n".join(parts)

    def read_document(self, path: str = "") -> str:
        """Read a document from disk."""
        if not path:
            path = "attacks/malicious_document.txt"
        full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path
        )
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"Document not found: {path}"

    def send_email(self, to: str = "", subject: str = "", body: str = "") -> str:
        """Send an email (simulated)."""
        return f"Email sent to {to} with subject '{subject}'"

    def write_file(self, path: str = "", content: str = "") -> str:
        """Write to a file (simulated, does not actually write)."""
        return f"File written to {path} ({len(content)} chars)"

    def fetch_url(self, url: str = "") -> str:
        """
        Open a URL and return the page content as text (e.g. to follow links from emails).
        Use this when the user wants details from a link mentioned in an email or document.
        """
        if not url or not url.strip():
            return "Error: please provide a URL (e.g. fetch_url with args {\"url\": \"https://...\"})."
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = Request(url, headers={"User-Agent": "CausalGuard-Agent/1.0"})
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=10, context=ctx) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            # Simple HTML strip: remove script/style, then tags, then collapse whitespace
            raw = re.sub(r"(?s)<script[^>]*>.*?</script>", " ", raw)
            raw = re.sub(r"(?s)<style[^>]*>.*?</style>", " ", raw)
            text = re.sub(r"<[^>]+>", " ", raw)
            text = re.sub(r"\s+", " ", text).strip()
            return (text[:12000] + "...") if len(text) > 12000 else text
        except (URLError, HTTPError, OSError) as e:
            return f"Error fetching URL: {e}"

    # ─────────────────────────────────────────────
    # TOOL DISPATCH
    # ─────────────────────────────────────────────

    def _get_tool(self, name: str):
        tools = {
            "read_email": self.read_email,
            "web_search": self.web_search,
            "fetch_url": self.fetch_url,
            "calendar_check": self.calendar_check,
            "read_document": self.read_document,
            "send_email": self.send_email,
            "write_file": self.write_file,
        }
        return tools.get(name)

    async def _execute_tool(self, tool_name: str, args: dict, task: str) -> ToolCall:
        """Execute a tool and pass its output through CausalGuard."""
        tool_fn = self._get_tool(tool_name)
        if not tool_fn:
            return ToolCall(
                tool_name=tool_name, args=args,
                raw_result=f"Unknown tool: {tool_name}",
                processed_result=f"Unknown tool: {tool_name}",
                was_intercepted=False,
            )

        # Only pass args the tool accepts (avoid unexpected keyword errors from LLM)
        sig = inspect.signature(tool_fn)
        allowed = {p for p in sig.parameters if p != "self"}
        safe_args = {k: v for k, v in (args or {}).items() if k in allowed}
        # Call the tool (handle both sync and async tools)
        result = tool_fn(**safe_args) if safe_args else tool_fn()
        if asyncio.iscoroutine(result):
            raw_result = await result
        else:
            raw_result = result

        # CausalGuard intercepts tool outputs that bring external content
        processed_result = raw_result
        guard_report = None
        was_intercepted = False

        if self.guard and tool_name not in ("send_email", "write_file"):
            processed_result, guard_report = await self.guard.intercept(
                task=task,
                retrieved_content=raw_result,
                tool_name=tool_name,
            )
            was_intercepted = guard_report.was_flagged if guard_report else False

        tc = ToolCall(
            tool_name=tool_name,
            args=args,
            raw_result=raw_result,
            processed_result=processed_result,
            was_intercepted=was_intercepted,
            guard_report=guard_report,
        )
        self.tool_calls_log.append(tc)
        return tc

    # ─────────────────────────────────────────────
    # ReAct AGENT LOOP
    # ─────────────────────────────────────────────

    async def process_message(
        self,
        user_message: str,
        on_event=None,
        conversation_history: list = None,
    ) -> dict:
        """
        ReAct-style autonomous agent loop.

        The agent repeatedly: THINK → ACT → OBSERVE until it has enough
        information to produce a final answer. CausalGuard monitors every
        tool call (every website visited, every email read).

        conversation_history: optional list of {"role": "user"|"assistant"|"agent", "content": str}
        so the agent can refer back to earlier messages (e.g. "the Quora email I summarized").
        """
        scenario_info = SCENARIOS.get(self.scenario, SCENARIOS["email"])
        available_tools = scenario_info["tools_available"]

        tool_results = []
        guard_alerts = []
        observations = []  # Running context of what the agent has seen
        agent_response = ""

        # Build context from prior conversation so the agent can refer to earlier emails/links
        history_block = ""
        if conversation_history and len(conversation_history) > 0:
            lines = []
            for msg in conversation_history[-10:]:  # last 10 messages
                role = (msg.get("role") or "user").lower()
                if role == "assistant":
                    role = "agent"
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                lines.append(f"{role.upper()}: {content[:1500]}{'...' if len(content) > 1500 else ''}")
            if lines:
                history_block = "Previous conversation (use this to remember which emails/links you already saw):\n" + "\n".join(lines) + "\n\n"

        for step in range(self.MAX_STEPS):
            # ── THINK: Ask the agent what to do next ──
            if step == 0:
                react_prompt = f"""You are an autonomous AI agent with access to these tools: {', '.join(available_tools)}.
{history_block}The user asked: "{user_message}"

If the user refers to something from earlier (e.g. "the Quora email you told me about", "that link"), use the previous conversation above to know which email or link they mean — then use read_email (with query= to search) or fetch_url with that link. You do not need to re-read the whole inbox if you already summarized an email; you can use fetch_url with the link from that email if the user wants more detail from the webpage.
To give a complete answer: read or search first when needed, then use fetch_url to open any links the user asks about.
Think step-by-step about what you need to do to fully complete this request.
Then decide which tool to call FIRST.

Respond as JSON:
{{
  "thought": "your reasoning about what to do and why",
  "tool": "tool_name",
  "args": {{}},
  "done": false
}}

If the request is a simple greeting or question you can answer directly (no tools needed), respond:
{{
  "thought": "...",
  "answer": "your response to the user",
  "done": true
}}"""
            else:
                context = "\n".join(observations)
                react_prompt = f"""You are an autonomous AI agent.
{history_block}The user asked: "{user_message}"

Here is what you've done so far:
{context}

Think about whether you have enough information to give a complete, detailed answer.
If you need MORE information, call another tool.
If you have ENOUGH, produce your final answer.

Available tools: {', '.join(available_tools)}

Respond as JSON:
{{
  "thought": "your reasoning",
  "tool": "tool_name",
  "args": {{}},
  "done": false
}}

OR if you have enough information for a detailed, comprehensive answer:
{{
  "thought": "I have enough information",
  "answer": "your DETAILED final response (be thorough, use all the information you gathered)",
  "done": true
}}"""

            react_response = await self.llm.complete(react_prompt)

            # Parse the ReAct response
            react_data = None
            try:
                start = react_response.find("{")
                end = react_response.rfind("}") + 1
                if start >= 0 and end > start:
                    react_data = json.loads(react_response[start:end])
            except (json.JSONDecodeError, ValueError):
                pass

            if not react_data:
                # Fallback: use expected tools on first step, finish on later steps
                if step == 0:
                    react_data = {
                        "thought": "Let me use the default tools.",
                        "tool": scenario_info["expected_tools"][0],
                        "args": {},
                        "done": False,
                    }
                else:
                    react_data = {
                        "thought": "Let me summarize what I found.",
                        "answer": react_response,
                        "done": True,
                    }

            # Emit the agent's thinking
            thought = react_data.get("thought", "")
            if thought and on_event:
                on_event({
                    "type": "agent_thinking",
                    "step": step + 1,
                    "thought": thought,
                })

            # ── DONE: Agent has its final answer ──
            if react_data.get("done"):
                agent_response = react_data.get("answer", "")
                if on_event:
                    on_event({
                        "type": "agent_response",
                        "content": agent_response,
                        "tools_used": [tc.tool_name for tc in tool_results],
                    })
                break

            # ── ACT: Execute the tool call ──
            tool_name = react_data.get("tool", "")
            tool_args = react_data.get("args", {})

            if not tool_name or not self._get_tool(tool_name):
                # Invalid tool — agent is confused, ask it to finish
                observations.append(f"[Step {step+1}] Error: Unknown tool '{tool_name}'. Proceeding to answer.")
                continue

            if on_event:
                on_event({
                    "type": "tool_call",
                    "tool": tool_name,
                    "args": tool_args,
                    "status": "calling",
                    "step": step + 1,
                })

            tc = await self._execute_tool(tool_name, tool_args, user_message)

            if on_event:
                on_event({
                    "type": "tool_call",
                    "tool": tool_name,
                    "status": "intercepted" if tc.was_intercepted else "clean",
                    "was_intercepted": tc.was_intercepted,
                    "step": step + 1,
                })

            tool_results.append(tc)

            # ── OBSERVE: Record what the agent saw ──
            content_preview = tc.processed_result[:800]
            observations.append(
                f"[Step {step+1}] Called {tool_name}({json.dumps(tool_args)}):\n"
                f"{content_preview}"
                f"{' [CONTENT WAS PURIFIED BY CAUSALGUARD - injection removed]' if tc.was_intercepted else ''}"
            )

            if tc.was_intercepted and tc.guard_report:
                alert = {
                    "type": "guard_alert",
                    "tool": tool_name,
                    "summary": f"Injection detected in {tool_name}() output — content purified",
                    "decision": tc.guard_report.final_decision,
                    "threat_level": tc.guard_report.threat_level,
                    "layers_flagged": [],
                    "step": step + 1,
                }
                if tc.guard_report.l1_result and tc.guard_report.l1_result.is_flagged:
                    alert["layers_flagged"].append("L1")
                if tc.guard_report.l2_result and tc.guard_report.l2_result.is_flagged:
                    alert["layers_flagged"].append("L2")
                if tc.guard_report.l3_result and tc.guard_report.l3_result.is_flagged:
                    alert["layers_flagged"].append("L3")
                guard_alerts.append(alert)
                if on_event:
                    on_event(alert)
        else:
            # Max steps reached — generate final answer from what we have
            context = "\n".join(observations)
            final_prompt = f"""You are an AI assistant. The user asked: "{user_message}"

You performed these steps:
{context}

{"NOTE: Some content was flagged and purified by CausalGuard for your protection." if any(tc.was_intercepted for tc in tool_results) else ""}

Now provide a DETAILED, comprehensive response using ALL the information you gathered. Be thorough."""

            agent_response = await self.llm.complete(final_prompt, max_tokens=2048)
            if on_event:
                on_event({
                    "type": "agent_response",
                    "content": agent_response,
                    "tools_used": [tc.tool_name for tc in tool_results],
                })

        # ── Post-agent: L4/L5/L6 analysis ──
        actual_tools = [tc.tool_name for tc in tool_results]
        l4_result = None
        l5_result = None
        l6_result = None

        if self.guard and actual_tools:
            proposed = None
            for tc in reversed(tool_results):
                if tc.tool_name in ("send_email", "write_file"):
                    proposed = {"tool": tc.tool_name, "args": tc.args}
                    break

            l4_result, l5_result, l6_result = await self.guard.report_tool_calls_parallel(
                task=user_message,
                actual_tool_calls=actual_tools,
                proposed_tool_call=proposed,
            )

            if l4_result and l4_result.flagged:
                alert = {
                    "type": "guard_alert",
                    "tool": "L4",
                    "summary": f"Unexpected tools detected: {', '.join(l4_result.unexpected_tools)}",
                    "decision": "ALERT",
                    "threat_level": "HIGH" if l4_result.jaccard_anomaly_score > 0.5 else "MEDIUM",
                    "layers_flagged": ["L4"],
                }
                guard_alerts.append(alert)
                if on_event:
                    on_event(alert)

            if l6_result and l6_result.is_flagged:
                alert = {
                    "type": "guard_alert",
                    "tool": "L6",
                    "summary": f"Taint violation: {l6_result.explanation[:100]}",
                    "decision": l6_result.enforcement_decision,
                    "threat_level": "CRITICAL",
                    "layers_flagged": ["L6"],
                }
                guard_alerts.append(alert)
                if on_event:
                    on_event(alert)

        return {
            "agent_response": agent_response,
            "tool_calls": [
                {
                    "tool": tc.tool_name,
                    "was_intercepted": tc.was_intercepted,
                    "guard_report": _serialize_guard_report(tc.guard_report) if tc.guard_report else None,
                }
                for tc in tool_results
            ],
            "guard_alerts": guard_alerts,
            "l4_result": _serialize_l4(l4_result) if l4_result else None,
            "l5_result": _serialize_l5(l5_result) if l5_result else None,
            "l6_result": _serialize_l6(l6_result) if l6_result else None,
        }


def _serialize_guard_report(report) -> dict:
    """Serialize a GuardReport to JSON-safe dict."""
    data = {
        "was_flagged": report.was_flagged,
        "final_decision": report.final_decision,
        "threat_level": report.threat_level,
        "total_latency_ms": round(report.total_latency_ms, 1),
    }
    if report.l1_result:
        data["l1"] = {
            "flagged": report.l1_result.is_flagged,
            "risk_score": round(report.l1_result.risk_score, 4),
            "categories": report.l1_result.pattern_categories_hit,
            "spans": [
                (s[0], s[1], s[2], s[3])
                for s in report.l1_result.flagged_spans[:10]
            ],
        }
    if report.l2_result:
        data["l2"] = {
            "flagged": report.l2_result.is_flagged,
            "causal_score": round(report.l2_result.causal_divergence_score, 4),
            "action_kl": round(report.l2_result.action_type_shift_score, 4),
            "param_jsd": round(report.l2_result.parameter_drift_score, 4),
            "structural_jaccard": round(report.l2_result.structural_delta_score, 4),
            "baseline_action": (
                report.l2_result.baseline_intent.action_type
                if report.l2_result.baseline_intent else "unknown"
            ),
            "full_action": (
                report.l2_result.full_intent.action_type
                if report.l2_result.full_intent else "unknown"
            ),
            "baseline_target": (
                report.l2_result.baseline_intent.primary_target
                if report.l2_result.baseline_intent else None
            ),
            "full_target": (
                report.l2_result.full_intent.primary_target
                if report.l2_result.full_intent else None
            ),
        }
    if report.l3_result:
        data["l3"] = {
            "flagged": report.l3_result.is_flagged,
            "cosine_similarity": round(report.l3_result.cosine_similarity, 4),
            "drift_score": round(report.l3_result.semantic_drift_score, 4),
        }
    if report.purifier_result:
        data["purifier"] = {
            "redacted_count": report.purifier_result.redaction_count,
            "redacted_sentences": [
                s[0] for s in report.purifier_result.redacted_sentences
            ],
        }
    if report.attack_anatomy:
        data["attack_anatomy"] = report.attack_anatomy.to_dict()
    return data


def _serialize_l4(result) -> dict:
    return {
        "flagged": result.flagged,
        "unexpected_tools": result.unexpected_tools,
        "expected_tools": result.expected_tools,
        "actual_tools": result.actual_tools,
        "jaccard_anomaly": round(result.jaccard_anomaly_score, 4),
        "task_type": result.task_type,
    }


def _serialize_l5(result) -> dict:
    return {
        "flagged": result.flagged,
        "anomaly_score": round(result.anomaly_score, 4),
        "threshold": result.threshold,
        "details": {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in result.details.items()
        },
    }


def _serialize_l6(result) -> dict:
    return {
        "flagged": result.is_flagged,
        "enforcement_decision": result.enforcement_decision,
        "context_label": str(result.context_label),
        "explanation": result.explanation,
        "violations": [
            {
                "tool": v.tool_name,
                "parameter": v.parameter,
                "policy_rule": v.policy_rule,
                "taint_label": str(v.tainted_value.label),
                "provenance": v.tainted_value.provenance,
            }
            for v in result.policy_violations
        ],
        "taint_graph": {
            name: {
                "label": str(tv.label),
                "provenance": tv.provenance,
                "content_hash": tv.content_hash,
            }
            for name, tv in result.taint_graph.items()
        },
    }
