from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import asyncio
import json
import sys
import os
import traceback
import warnings

# Suppress deprecation warning from huggingface_hub (used by sentence-transformers for Layer 3)
warnings.filterwarnings("ignore", message=".*resume_download.*", category=FutureWarning, module="huggingface_hub")

# Add parent directory to path to import causalguard modules
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
os.chdir(_root)

# Load .env from project root (CausalGuard thresholds)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

from causalguard.layer1_lexical import scan as l1_scan
from causalguard.layer2_counterfactual import analyze as l2_analyze
from causalguard.layer3_semantic import analyze as l3_analyze
from causalguard.layer4_tool_monitor import monitor_tool_calls, infer_task_type
from causalguard.layer6_taint import analyze as l6_analyze
from causalguard.purifier import purify
from causalguard.scoring import calculate_threat_level, compute_composite_threat_score
from causalguard.attack_taxonomy import build_attack_anatomy
from llm_client import LLMClient

# Optional Layer 5 (requires trained checkpoint)
try:
    from causalguard.layer5_neural_ode import ensure_layer5_model, analyze_session as l5_analyze_session
    _l5_model_cache = None
    def _get_l5_model():
        global _l5_model_cache
        if _l5_model_cache is None:
            _l5_model_cache = ensure_layer5_model(train_if_missing=False)
        return _l5_model_cache
except ImportError:
    _get_l5_model = lambda: None

app = Flask(__name__)
CORS(app)
_llm_instance = None

def _get_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMClient()
    return _llm_instance


def _llm_configured():
    """Return True if Vertex project is set so LLM can be used."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT_ID") or os.getenv("GCP_PROJECT")
    return bool(project)


# ─────────────────────────────────────────────────────────────
# /api/analyze — Attack Lab (paste content, run all 6 layers)
# ─────────────────────────────────────────────────────────────

@app.route('/api/analyze', methods=['POST'])
def analyze():
    if not _llm_configured():
        return jsonify({
            "error": "LLM not configured",
            "message": "Set GOOGLE_CLOUD_PROJECT (or VERTEX_PROJECT_ID) in .env. Copy .env.example to .env and add your GCP project ID.",
        }), 503

    data = request.json
    task = data.get('task', '')
    content = data.get('content', '')

    def generate():
        # ── L1 + L2 in parallel ──
        llm = _get_llm()
        loop = asyncio.new_event_loop()

        async def _parallel_l1_l2():
            async def _l1():
                return await loop.run_in_executor(None, l1_scan, content)
            return await asyncio.gather(_l1(), l2_analyze(task, content, llm))

        try:
            l1_result, l2_result = loop.run_until_complete(_parallel_l1_l2())
        finally:
            loop.close()

        # Stream L1
        yield f"data: {json.dumps({'layer': 1, 'flagged': l1_result.is_flagged, 'risk_score': round(l1_result.risk_score, 4), 'categories': l1_result.pattern_categories_hit, 'spans': [(s[0], s[1], s[2], s[3]) for s in l1_result.flagged_spans[:10]]})}\n\n"

        # Stream L2
        yield f"data: {json.dumps({'layer': 2, 'flagged': l2_result.is_flagged, 'causal_score': round(l2_result.causal_divergence_score, 4), 'action_kl': round(l2_result.action_type_shift_score, 4), 'param_jsd': round(l2_result.parameter_drift_score, 4), 'structural_jaccard': round(l2_result.structural_delta_score, 4), 'baseline_action': l2_result.baseline_intent.action_type if l2_result.baseline_intent else 'unknown', 'baseline_target': l2_result.baseline_intent.primary_target if l2_result.baseline_intent else None, 'full_action': l2_result.full_intent.action_type if l2_result.full_intent else 'unknown', 'full_target': l2_result.full_intent.primary_target if l2_result.full_intent else None})}\n\n"

        # ── L3 (depends on L2) ──
        baseline_text = l2_result.baseline_intent.action_description if l2_result.baseline_intent else task
        full_text = l2_result.full_intent.action_description if l2_result.full_intent else content[:200]
        l3_result = l3_analyze(baseline_text, full_text)
        yield f"data: {json.dumps({'layer': 3, 'flagged': l3_result.is_flagged, 'cosine_similarity': round(l3_result.cosine_similarity, 4), 'drift_score': round(l3_result.semantic_drift_score, 4)})}\n\n"

        # ── L4: Tool Invocation Anomaly ──
        task_type = infer_task_type(task)
        # Simulate expected tools based on task type (must match what L4 expects)
        _TASK_TYPE_TOOLS = {
            "email": ["read_email"],
            "search": ["web_search"],
            "summarize": ["read_document"],
            "file_op": ["read_document"],
        }
        simulated_tools = _TASK_TYPE_TOOLS.get(task_type, ["read_document"])
        # If L2 detected a side-effect action, add it (this IS suspicious)
        if l2_result and l2_result.full_intent:
            fa = (l2_result.full_intent.action_type or "").lower()
            if "email" in fa and "send_email" not in simulated_tools:
                simulated_tools.append("send_email")
            elif "upload" in fa and "upload_file" not in simulated_tools:
                simulated_tools.append("upload_file")
            elif ("write" in fa or "file" in fa) and "write_file" not in simulated_tools:
                if fa not in ("read_file", "read_document"):
                    simulated_tools.append("write_file")
        l4_result = monitor_tool_calls(task_type, simulated_tools, task=task)
        yield f"data: {json.dumps({'layer': 4, 'flagged': l4_result.flagged, 'unexpected_tools': l4_result.unexpected_tools, 'expected_tools': l4_result.expected_tools, 'actual_tools': l4_result.actual_tools, 'jaccard_anomaly': round(l4_result.jaccard_anomaly_score, 4), 'task_type': l4_result.task_type})}\n\n"

        # ── L5: Neural ODE ──
        l5_data = {'layer': 5, 'available': False}
        l5_model = _get_l5_model()
        if l5_model is not None and len(simulated_tools) >= 2:
            ode, encoder = l5_model
            session = [(task_type, t) for t in simulated_tools]
            l5_result = l5_analyze_session(ode, encoder, session)
            l5_data = {
                'layer': 5, 'available': True,
                'flagged': l5_result.flagged,
                'anomaly_score': round(l5_result.anomaly_score, 4),
                'threshold': l5_result.threshold,
            }
        yield f"data: {json.dumps(l5_data)}\n\n"

        # ── L6: Taint Propagation ──
        proposed = {"tool": "unknown", "args": {}}
        if l2_result and l2_result.full_intent:
            fi = l2_result.full_intent
            proposed = {
                "tool": fi.action_type.replace(" ", "_"),
                "args": {"recipient": fi.primary_target or "", **(fi.parameters or {})},
            }
        l6_result = l6_analyze(task, content, proposed)
        yield f"data: {json.dumps({'layer': 6, 'flagged': l6_result.is_flagged, 'enforcement_decision': l6_result.enforcement_decision, 'context_label': str(l6_result.context_label), 'explanation': l6_result.explanation, 'violations': [{'tool': v.tool_name, 'parameter': v.parameter, 'policy_rule': v.policy_rule, 'taint_label': str(v.tainted_value.label), 'provenance': v.tainted_value.provenance} for v in l6_result.policy_violations], 'taint_graph': {name: {'label': str(tv.label), 'provenance': tv.provenance} for name, tv in l6_result.taint_graph.items()}})}\n\n"

        # ── Decision ──
        # Collect all layer flags for reporting
        flags = []
        if l1_result.is_flagged: flags.append("L1")
        if l2_result.is_flagged: flags.append("L2")
        if l3_result.is_flagged: flags.append("L3")
        if l4_result.flagged: flags.append("L4")
        if l5_data.get('available') and l5_data.get('flagged'): flags.append("L5")
        if l6_result.is_flagged: flags.append("L6")

        # Smart decision: require structural corroboration for semantic-only flags.
        # L2/L3 are LLM-dependent semantic checks that can false-positive on benign
        # content describing actions (code with email_service.send(), logs with
        # "sending alert", security articles about injection, etc.).
        # L1/L4/L5/L6 are pattern/structural checks with very low false positive rates.
        structural_flags = {"L1", "L4", "L5", "L6"}
        has_structural = bool(structural_flags & set(flags))
        semantic_only = flags and not has_structural
        if semantic_only:
            # Semantic-only: only purify if L2 causal score is very high
            if l2_result.is_flagged and l2_result.causal_divergence_score > 0.90:
                pass  # keep flags, will purify
            else:
                flags = []  # clear flags — likely false positive

        threat_level = calculate_threat_level(flags, l2_result.causal_divergence_score)

        # Composite Threat Score
        cts = compute_composite_threat_score(
            l1_risk=l1_result.risk_score,
            l2_causal=l2_result.causal_divergence_score,
            l3_drift=l3_result.semantic_drift_score,
            l4_tool_anomaly=l4_result.jaccard_anomaly_score,
            l5_ode_score=l5_data.get('anomaly_score', 0.0) if l5_data.get('available') else 0.0,
        )

        purifier_result = None
        processed_content = content
        if flags:
            purifier_result = purify(content)
            processed_content = purifier_result.purified_content
            decision = "PURIFY"
        else:
            decision = "PASS"

        attack_anatomy = None
        if flags:
            anatomy = build_attack_anatomy(
                l1_result.flagged_spans,
                l2_action_shift=l2_result.is_flagged,
                l2_full_intent_action=l2_result.full_intent.action_type if l2_result.full_intent else None,
                l2_full_target=l2_result.full_intent.primary_target if l2_result.full_intent else None,
            )
            attack_anatomy = anatomy.to_dict()

        payload = {
            'layer': 'decision',
            'decision': decision,
            'threat_level': threat_level,
            'flags': flags,
            'composite_threat_score': cts,
            'redacted_count': len(purifier_result.redacted_sentences) if purifier_result else 0,
            'redacted_sentences': [s[0] for s in purifier_result.redacted_sentences] if purifier_result else [],
            'purified_content': processed_content,
            'attack_anatomy': attack_anatomy,
        }
        yield f"data: {json.dumps(payload)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


# ─────────────────────────────────────────────────────────────
# /api/chat — Agent Demo (chatbot with real LLM agent)
# ─────────────────────────────────────────────────────────────

@app.route('/api/chat', methods=['POST'])
def chat():
    if not _llm_configured():
        return jsonify({
            "error": "LLM not configured",
            "message": "Set GOOGLE_CLOUD_PROJECT (or VERTEX_PROJECT_ID) in .env. Copy .env.example to .env and add your GCP project ID.",
        }), 503

    data = request.json
    message = data.get('message', '')
    scenario = data.get('scenario', 'email')
    history = data.get('history', [])

    def generate():
        from causalguard.interceptor import CausalGuard
        from agent.multi_tool_agent import MultiToolAgent

        llm = _get_llm()
        guard = CausalGuard(llm_client=llm)
        agent = MultiToolAgent(llm_client=llm, causalguard=guard, scenario=scenario)

        # Run agent
        loop = asyncio.new_event_loop()

        collected_events = []
        def collect_event(event):
            collected_events.append(event)

        try:
            result = loop.run_until_complete(
                agent.process_message(
                    message,
                    on_event=collect_event,
                    conversation_history=history or [],
                )
            )
        except Exception as e:
            collected_events.append({
                "type": "error",
                "message": str(e),
            })
            result = {"agent_response": f"Error: {e}", "tool_calls": [], "guard_alerts": []}
        finally:
            loop.close()

        # Stream all collected events
        for event in collected_events:
            yield f"data: {json.dumps(event)}\n\n"

        # Stream guard reports from tool calls
        for tc in result.get("tool_calls", []):
            if tc.get("guard_report"):
                yield f"data: {json.dumps({'type': 'guard_report', 'tool': tc['tool'], **tc['guard_report']})}\n\n"

        # Stream L4/L5/L6 results
        if result.get("l4_result"):
            yield f"data: {json.dumps({'type': 'layer_result', 'layer': 4, **result['l4_result']})}\n\n"
        if result.get("l5_result"):
            yield f"data: {json.dumps({'type': 'layer_result', 'layer': 5, **result['l5_result']})}\n\n"
        else:
            # So the UI can show why L5 didn't run (need 2+ tools or no checkpoint)
            n_tools = len(result.get("tool_calls") or [])
            reason = "need_2_tools" if n_tools < 2 else "no_checkpoint"
            yield f"data: {json.dumps({'type': 'layer_result', 'layer': 5, 'available': False, 'reason': reason})}\n\n"
        if result.get("l6_result"):
            yield f"data: {json.dumps({'type': 'layer_result', 'layer': 6, **result['l6_result']})}\n\n"

        # Final response
        yield f"data: {json.dumps({'type': 'done', 'agent_response': result['agent_response'], 'tools_used': [tc['tool'] for tc in result.get('tool_calls', [])]})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


# ─────────────────────────────────────────────────────────────
# /api/scenarios — List available demo scenarios
# ─────────────────────────────────────────────────────────────

@app.route('/api/scenarios', methods=['GET'])
def get_scenarios():
    from agent.scenarios import SCENARIOS
    return jsonify(SCENARIOS)


# ─────────────────────────────────────────────────────────────
# /demo/* — Serve poisoned pages for multi-step attack demos
# These simulate real websites that an agent would visit when
# following links found in emails or spreadsheets.
# ─────────────────────────────────────────────────────────────

@app.route('/demo/q3-regional-update')
def demo_q3_regional():
    """Poisoned 'accounting update' page linked from the Excel spreadsheet."""
    html_path = os.path.join(_root, "attacks", "q3_regional_update.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html"}
    except FileNotFoundError:
        return "Page not found", 404

@app.route('/demo/vendor-portal')
def demo_vendor_portal():
    """Poisoned 'vendor portal' page linked from a phishing email."""
    html_path = os.path.join(_root, "attacks", "vendor_portal.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html"}
    except FileNotFoundError:
        return "Page not found", 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=(port == 5000))
