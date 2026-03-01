from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import asyncio
import json
import sys
import os

# Add parent directory to path to import causalguard modules
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
os.chdir(_root)

# Load .env from project root (GOOGLE_API_KEY or OPENAI_API_KEY for Layer 2)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from causalguard.layer1_lexical import scan as l1_scan
from causalguard.layer2_counterfactual import analyze as l2_analyze
from causalguard.layer3_semantic import analyze as l3_analyze
from causalguard.purifier import purify
from causalguard.scoring import calculate_threat_level
from causalguard.attack_taxonomy import build_attack_anatomy
from llm_client import LLMClient

app = Flask(__name__)
CORS(app)
llm = LLMClient()

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    task = data.get('task', '')
    content = data.get('content', '')

    def generate():
        # Layer 1
        l1_result = l1_scan(content)
        yield f"data: {json.dumps({'layer': 1, 'flagged': l1_result.is_flagged, 'risk_score': round(l1_result.risk_score, 4), 'categories': l1_result.pattern_categories_hit, 'spans': [(s[0], s[1], s[2], s[3]) for s in l1_result.flagged_spans[:10]]})}\n\n"

        # Layer 2
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            l2_result = loop.run_until_complete(l2_analyze(task, content, llm))
        finally:
            loop.close()

        yield f"data: {json.dumps({'layer': 2, 'flagged': l2_result.is_flagged, 'causal_score': round(l2_result.causal_divergence_score, 4), 'action_kl': round(l2_result.action_type_shift_score, 4), 'param_jsd': round(l2_result.parameter_drift_score, 4), 'structural_jaccard': round(l2_result.structural_delta_score, 4), 'baseline_action': l2_result.baseline_intent.action_type if l2_result.baseline_intent else 'unknown', 'baseline_target': l2_result.baseline_intent.primary_target if l2_result.baseline_intent else None, 'full_action': l2_result.full_intent.action_type if l2_result.full_intent else 'unknown', 'full_target': l2_result.full_intent.primary_target if l2_result.full_intent else None})}\n\n"

        # Layer 3
        baseline_text = l2_result.baseline_intent.action_description if l2_result.baseline_intent else task
        full_text = l2_result.full_intent.action_description if l2_result.full_intent else content[:200]
        l3_result = l3_analyze(baseline_text, full_text)

        yield f"data: {json.dumps({'layer': 3, 'flagged': l3_result.is_flagged, 'cosine_similarity': round(l3_result.cosine_similarity, 4), 'drift_score': round(l3_result.semantic_drift_score, 4)})}\n\n"

        # Final Decision
        flags = []
        if l1_result.is_flagged: flags.append("L1")
        if l2_result.is_flagged: flags.append("L2")
        if l3_result.is_flagged: flags.append("L3")

        threat_level = calculate_threat_level(flags, l2_result.causal_divergence_score)

        purifier_result = None
        processed_content = content
        if flags:
            purifier_result = purify(content)
            processed_content = purifier_result.purified_content
            decision = "PURIFY"
        else:
            decision = "PASS"

        # Attack anatomy (Log-To-Leak taxonomy)
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
            'redacted_count': len(purifier_result.redacted_sentences) if purifier_result else 0,
            'redacted_sentences': [s[0] for s in purifier_result.redacted_sentences] if purifier_result else [],
            'purified_content': processed_content,
            'attack_anatomy': attack_anatomy,
        }
        yield f"data: {json.dumps(payload)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
