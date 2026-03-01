"""
Train Layer 5 (Neural ODE Behavioral Dynamics)
===============================================
Run once to train the ODE on normal agent sessions and save the checkpoint.
After training, CausalGuard will use the checkpoint for Layer 5 anomaly scoring.

Research: Chen et al. (2018). Neural Ordinary Differential Equations. NeurIPS 2018.
  arXiv:1806.07366

Usage:
  python train_layer5.py
  # Checkpoint saved to causalguard/checkpoints/layer5_ode.pt
"""

import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from causalguard.layer5_neural_ode import (
    generate_normal_sessions,
    train_behavioral_ode,
    save_layer5_checkpoint,
    get_default_checkpoint_path,
    analyze_session,
    ensure_layer5_model,
)


def main():
    print("Layer 5: Neural ODE Behavioral Dynamics — Training")
    print("Research: Chen et al. NeurIPS 2018, arXiv:1806.07366")
    print()

    sessions = generate_normal_sessions(num_sessions=300, min_steps=2, max_steps=5)
    print(f"Generated {len(sessions)} normal sessions (2–5 steps each).")

    ode, encoder = train_behavioral_ode(
        sessions,
        latent_dim=32,
        embedding_dim=24,
        hidden_dim=64,
        epochs=100,
        lr=1e-3,
    )

    path = get_default_checkpoint_path()
    save_layer5_checkpoint(ode, encoder, path)
    print(f"Checkpoint saved to {path}")

    # Sanity: normal session should have LOW anomaly (score near 0)
    test_normal = [("email_draft", "read_document"), ("email_draft", "send_email")]
    result_normal = analyze_session(ode, encoder, test_normal)
    print(f"Sanity: normal session anomaly_score={result_normal.anomaly_score:.4f} (low = good, means 'normal behavior').")

    # Contrast: anomalous session (unexpected tool) should have HIGHER anomaly
    # Session that looks like email_draft but includes a tool never seen in that context
    test_anomalous = [("email_draft", "read_document"), ("email_draft", "log_exfil")]
    result_anomalous = analyze_session(ode, encoder, test_anomalous)
    print(f"Contrast: anomalous session (e.g. log_exfil) anomaly_score={result_anomalous.anomaly_score:.4f} (high = flagged as deviation).")
    print()
    print("Interpretation: Layer 5 uses (task_type, tool_name) only — no prompt/output text.")
    print("To use prompt/output you'd need real sessions with encoded prompts; current training is synthetic.")
    print("Done.")


if __name__ == "__main__":
    main()
