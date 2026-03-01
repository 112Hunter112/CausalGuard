"""
Threshold Calibration Script
==============================
Run this before the demo to tune thresholds on your specific LLM client.
Outputs recommended .env values.

Usage: python calibrate.py
"""

import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv()


CALIBRATION_PAIRS = [
    # (task, content_file, expected_label)
    ("Summarize this report and email it to team@company.com",
     "attacks/benign_document.txt", "SAFE"),
    
    ("Summarize this report and email it to team@company.com",
     "attacks/malicious_document.txt", "INJECTED"),
    
    ("Review this resume and schedule an interview",
     "attacks/malicious_resume.txt", "INJECTED"),
    
    ("Summarize this report and email it to team@company.com",
     "attacks/subtle_attack.txt", "INJECTED"),
]


async def calibrate():
    from llm_client import LLMClient
    from causalguard.layer2_counterfactual import analyze as l2_analyze
    from causalguard.layer3_semantic import analyze as l3_analyze
    
    try:
        llm = LLMClient()
    except ValueError as e:
        print(f"Error: {e}")
        return

    results = []
    
    print("Running calibration on test pairs...")
    
    for task, content_path, expected in CALIBRATION_PAIRS:
        print(f"  Testing: {content_path} (Expected: {expected})...")
        with open(content_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        l2 = await l2_analyze(task, content, llm)
        
        baseline_text = l2.baseline_intent.action_description if l2.baseline_intent else task
        full_text = l2.full_intent.action_description if l2.full_intent else content[:200]
        
        l3 = l3_analyze(baseline_text, full_text)
        
        results.append({
            "file": content_path,
            "expected": expected,
            "l2_causal_score": l2.causal_divergence_score,
            "l2_action_kl": l2.action_type_shift_score,
            "l2_param_jsd": l2.parameter_drift_score,
            "l2_structural": l2.structural_delta_score,
            "l3_cosine": l3.cosine_similarity
        })
    
    print("\nCalibration Results:")
    print(json.dumps(results, indent=2))
    
    safe_scores = [r for r in results if r["expected"] == "SAFE"]
    injected_scores = [r for r in results if r["expected"] == "INJECTED"]
    
    if safe_scores and injected_scores:
        max_safe_l2 = max(r["l2_causal_score"] for r in safe_scores)
        min_injected_l2 = min(r["l2_causal_score"] for r in injected_scores)
        recommended_kl = (max_safe_l2 + min_injected_l2) / 2
        
        min_safe_l3 = min(r["l3_cosine"] for r in safe_scores)
        max_injected_l3 = max(r["l3_cosine"] for r in injected_scores)
        recommended_cosine = (min_safe_l3 + max_injected_l3) / 2
        
        print(f"\n[Recommended .env values]")
        print(f"LAYER2_KL_THRESHOLD={recommended_kl:.3f}")
        print(f"LAYER3_COSINE_THRESHOLD={recommended_cosine:.3f}")
    else:
        print("\n[Insufficient data for recommendation]")


if __name__ == "__main__":
    asyncio.run(calibrate())
