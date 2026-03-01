"""
Train Layer 5 (Neural ODE) on synthetic trajectory data from generate_training_data.py.

Loads data/normal_trajectories.npy (object array of (T, 4) arrays) and trains
the ODE in raw 4-dim space. Saves causalguard/checkpoints/layer5_trajectory.pt.

Run after: python scripts/generate_training_data.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from causalguard.layer5_neural_ode import (
    train_behavioral_ode_from_trajectories,
    save_layer5_trajectory_checkpoint,
)

DATA_PATH = ROOT / "data" / "normal_trajectories.npy"
CHECKPOINT_PATH = ROOT / "causalguard" / "checkpoints" / "layer5_trajectory.pt"
LATENT_DIM = 4


def main():
    if not DATA_PATH.exists():
        print(f"Missing {DATA_PATH}. Run first: python scripts/generate_training_data.py")
        sys.exit(1)

    trajectories = np.load(DATA_PATH, allow_pickle=True)
    observations_list = [trajectories[i] for i in range(len(trajectories))]
    print(f"Loaded {len(observations_list)} trajectories from {DATA_PATH}")

    ode = train_behavioral_ode_from_trajectories(
        observations_list,
        latent_dim=LATENT_DIM,
        hidden_dim=64,
        epochs=80,
        lr=1e-3,
    )
    save_layer5_trajectory_checkpoint(ode, CHECKPOINT_PATH)
    print(f"Saved trajectory-trained ODE to {CHECKPOINT_PATH}")
    print("Use load_layer5_trajectory_checkpoint() and analyze_session_from_trajectory() for inference.")


if __name__ == "__main__":
    main()
