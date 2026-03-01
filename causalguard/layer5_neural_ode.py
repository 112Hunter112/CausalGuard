"""
Layer 5: Neural ODE Behavioral Dynamics
========================================
Research basis:
  - Chen et al. (2018). Neural Ordinary Differential Equations. NeurIPS 2018 Best Paper.
    arXiv:1806.07366. The derivative of the hidden state is parameterized by a neural
    network: dh/dt = f_θ(h, t); output is computed with a black-box ODE solver.
  - Latent ODEs for irregularly-sampled time series (Rubanova et al., NeurIPS 2019).
  - Application: By learning the continuous dynamics of normal agent behavior, we
    detect when an injection causes the agent's trajectory to deviate from the
    learned normal manifold (reconstruction/prediction error = anomaly signal).

Mathematical formulation (Chen et al.):
  - Let h(t) ∈ ℝ^d be the hidden state at time t.
  - The Neural ODE defines: dh/dt = f_θ(h(t), t), with f_θ a neural network.
  - Given h(0) = h_0, we compute h(t_1), h(t_2), ... via an ODE solver (e.g. dopri5).
  - At inference: integrate from z_0 = observed_states[0]; compare predicted trajectory
    to observed_states. Anomaly score = mean L2 distance (reconstruction error).
    High score = behavioral trajectory has deviated from learned normal dynamics.

No generative AI in the security path: the ODE is trained offline on clean sessions
and used only as a continuous-time dynamics model for anomaly scoring.

Score interpretation:
  - LOW anomaly score (e.g. < 0.1): trajectory matches learned normal dynamics → normal.
  - HIGH anomaly score (e.g. > 0.15): trajectory deviates → possible injection or hijack.
Current state representation: (task_type, tool_name) only — no prompt or tool output text.
To use prompt/output you would need real session data and an encoder for prompts/outputs.
"""

from __future__ import annotations

import os
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Callable

import numpy as np
import torch
import torch.nn as nn

# Optional: use adjoint method for O(1) memory during training (torchdiffeq)
try:
    from torchdiffeq import odeint_adjoint as odeint
    _HAS_TORCHDIFFEQ = True
except ImportError:
    try:
        from torchdiffeq import odeint
        _HAS_TORCHDIFFEQ = True
    except ImportError:
        _HAS_TORCHDIFFEQ = False


# -----------------------------------------------------------------------------
# 1. Event encoder: map (task_type, tool_name) -> latent vector
# -----------------------------------------------------------------------------

class EventEncoder(nn.Module):
    """
    Maps a sequence of agent events (task_type, tool_name) to a sequence of
    latent vectors z_t ∈ ℝ^d. Used to obtain 'observed_states' for the ODE.
    Vocabulary is built from (task_type, tool_name) pairs; unknown pairs
    map to a learned UNK embedding.
    """

    PAD = "<PAD>"
    UNK = "<UNK>"

    def __init__(
        self,
        vocab: Dict[Tuple[str, str], int],
        latent_dim: int,
        embedding_dim: int = 24,
    ):
        super().__init__()
        self.vocab = vocab
        self.latent_dim = latent_dim
        self.embedding_dim = embedding_dim
        self.vocab_size = len(vocab) + 2  # +2 for PAD, UNK
        self.embed = nn.Embedding(self.vocab_size, embedding_dim, padding_idx=0)
        self.pad_idx = 0
        self.unk_idx = 1
        # Project embedding to latent_dim (observed state space)
        self.proj = nn.Linear(embedding_dim, latent_dim)

    def _key_to_idx(self, task_type: str, tool_name: str) -> int:
        key = (task_type.strip().lower(), tool_name.strip().lower())
        return self.vocab.get(key, self.unk_idx)

    def forward(self, events: List[Tuple[str, str]]) -> torch.Tensor:
        """
        events: list of (task_type, tool_name). Returns (T, latent_dim).
        """
        if not events:
            return torch.zeros(1, self.latent_dim)
        idx = torch.tensor(
            [self._key_to_idx(t, u) for t, u in events],
            dtype=torch.long,
        )
        emb = self.embed(idx)
        z = self.proj(emb)
        return z

    @classmethod
    def build_vocab(cls, sessions: List[List[Tuple[str, str]]]) -> Dict[Tuple[str, str], int]:
        """Build vocabulary from list of normal sessions."""
        keys = set()
        for session in sessions:
            for task_type, tool_name in session:
                keys.add((task_type.strip().lower(), tool_name.strip().lower()))
        return {k: i + 2 for i, k in enumerate(sorted(keys))}  # 0=PAD, 1=UNK


# -----------------------------------------------------------------------------
# 2. Agent dynamics ODE: f_θ(z, t) -> dz/dt
# -----------------------------------------------------------------------------

class AgentDynamicsODE(nn.Module):
    """
    Neural ODE defining the continuous-time dynamics of normal agent behavior:
        dz/dt = f_θ(z, t)

    f_θ is a MLP that takes (z, t) and outputs the time derivative.
    Research: Chen et al. (2018), NeurIPS. "Instead of specifying a discrete
    sequence of hidden layers, we parameterize the derivative of the hidden
    state using a neural network."
    """

    def __init__(self, latent_dim: int = 32, hidden_dim: int = 64):
        super().__init__()
        self.latent_dim = latent_dim
        self.net = nn.Sequential(
            nn.Linear(latent_dim + 1, hidden_dim),  # +1 for time t
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, latent_dim),
        )

    def forward(self, t: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """
        t: scalar or (batch,) tensor. z: (batch, latent_dim).
        Returns dz/dt with shape (batch, latent_dim).
        """
        if t.dim() == 0:
            t_vec = t.expand(z.size(0), 1)
        else:
            t_vec = t.view(-1, 1).expand(z.size(0), 1)
        inp = torch.cat([z, t_vec], dim=-1)
        return self.net(inp)


# -----------------------------------------------------------------------------
# 3. ODE integration (with fallback when torchdiffeq not installed)
# -----------------------------------------------------------------------------

def _odeint_euler(func: nn.Module, y0: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
    """Simple Euler integration for inference when torchdiffeq is not available."""
    device = y0.device
    t = t.to(device)
    out = [y0]
    y = y0
    for i in range(len(t) - 1):
        dt = (t[i + 1] - t[i]).item()
        dy = func(t[i], y)
        y = y + dt * dy
        out.append(y)
    return torch.stack(out, dim=0)


def integrate_ode(
    model: AgentDynamicsODE,
    z0: torch.Tensor,
    t_span: torch.Tensor,
) -> torch.Tensor:
    """
    Integrate dz/dt = model(t, z) from z(0) = z0 at times t_span.
    Returns tensor of shape (len(t_span), batch, latent_dim).
    """
    if _HAS_TORCHDIFFEQ:
        return odeint(model, z0, t_span, method="dopri5", rtol=1e-4, atol=1e-5)
    return _odeint_euler(model, z0, t_span)


# -----------------------------------------------------------------------------
# 4. Anomaly score: L2 deviation of predicted trajectory from observed
# -----------------------------------------------------------------------------

def compute_trajectory_anomaly_score(
    model: AgentDynamicsODE,
    observed_states: torch.Tensor,
    t_span: Optional[torch.Tensor] = None,
    device: Optional[torch.device] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Integrate the learned ODE from z_0 = observed_states[0] and compare the
    predicted trajectory to observed_states at each time step.

    Anomaly score = mean L2 distance between predicted and observed states.
    High score = agent behavior has deviated from learned normal dynamics.

    Args:
        model: Trained AgentDynamicsODE.
        observed_states: (T, d) or (T, 1, d) — sequence of observed latent states.
        t_span: Time points (0, 1, ..., T-1) if None.
        device: Device for computation.

    Returns:
        anomaly_score: Mean L2 error (scalar).
        details: Dict with per-step errors and max error for dashboard.
    """
    if device is None:
        device = next(model.parameters()).device
    model = model.to(device)
    observed_states = observed_states.to(device)
    if observed_states.dim() == 3:
        observed_states = observed_states.squeeze(1)
    T, d = observed_states.shape
    if T < 2:
        return 0.0, {"mean_l2": 0.0, "max_l2": 0.0, "steps": T}

    if t_span is None:
        t_span = torch.linspace(0.0, float(T - 1), T, device=device)
    else:
        t_span = t_span.to(device)

    z0 = observed_states[0:1]
    with torch.no_grad():
        predicted = integrate_ode(model, z0, t_span)
    if predicted.dim() == 3:
        predicted = predicted.squeeze(1)
    # predicted: (T, d), observed_states: (T, d)
    errors = torch.norm(predicted - observed_states, dim=-1)
    mean_l2 = errors.mean().item()
    max_l2 = errors.max().item()

    return mean_l2, {
        "mean_l2": mean_l2,
        "max_l2": max_l2,
        "steps": T,
        "final_error": errors[-1].item(),
    }


# -----------------------------------------------------------------------------
# 5. Training on normal sessions
# -----------------------------------------------------------------------------

def generate_normal_sessions(
    num_sessions: int = 200,
    min_steps: int = 2,
    max_steps: int = 5,
    seed: int = 42,
) -> List[List[Tuple[str, str]]]:
    """
    Generate synthetic normal sessions from task-type and tool profiles.
    Each session is a list of (task_type, tool_name) for a single agent run.
    """
    random.seed(seed)
    # From layer4: task_type -> set of tools
    profiles = [
        ("summarize", ["read_document"]),
        ("email_draft", ["read_document", "send_email"]),
        ("search", ["web_search"]),
        ("review_document", ["read_document"]),
    ]
    sessions = []
    for _ in range(num_sessions):
        task_type, tools = random.choice(profiles)
        n_steps = random.randint(min_steps, min(max_steps, len(tools) + 1))
        if n_steps == 1:
            session = [(task_type, tools[0])]
        else:
            order = list(tools)
            random.shuffle(order)
            session = [(task_type, t) for t in order[:n_steps]]
        sessions.append(session)
    return sessions


def train_behavioral_ode(
    sessions: List[List[Tuple[str, str]]],
    latent_dim: int = 32,
    embedding_dim: int = 24,
    hidden_dim: int = 64,
    epochs: int = 80,
    lr: float = 1e-3,
    device: Optional[torch.device] = None,
    on_epoch_done: Optional[Callable[[int, int, float], None]] = None,
) -> Tuple[AgentDynamicsODE, EventEncoder]:
    """
    Train the Neural ODE on normal sessions. Minimizes mean squared error
    between ODE-predicted trajectory and observed (encoded) trajectory.
    on_epoch_done: optional callback(epoch_1based, total_epochs, avg_loss) for progress.
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    vocab = EventEncoder.build_vocab(sessions)
    encoder = EventEncoder(vocab, latent_dim, embedding_dim).to(device)
    ode = AgentDynamicsODE(latent_dim=latent_dim, hidden_dim=hidden_dim).to(device)
    optim = torch.optim.Adam(list(encoder.parameters()) + list(ode.parameters()), lr=lr)

    for epoch in range(epochs):
        total_loss = 0.0
        n_batch = 0
        random.shuffle(sessions)
        for session in sessions:
            if len(session) < 2:
                continue
            optim.zero_grad()
            obs = encoder(session)
            T = obs.size(0)
            t_span = torch.linspace(0.0, float(T - 1), T, device=device)
            z0 = obs[0:1]
            pred = integrate_ode(ode, z0, t_span)
            if pred.dim() == 3:
                pred = pred.squeeze(1)
            loss = torch.nn.functional.mse_loss(pred, obs)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(encoder.parameters()) + list(ode.parameters()), 1.0
            )
            optim.step()
            total_loss += loss.item()
            n_batch += 1
        avg_loss = total_loss / n_batch if n_batch > 0 else 0.0
        if on_epoch_done:
            on_epoch_done(epoch + 1, epochs, avg_loss)
        elif (epoch + 1) % 20 == 0 and n_batch > 0:
            print(f"  Layer 5 train epoch {epoch+1}/{epochs} loss={avg_loss:.6f}")
    return ode, encoder


def train_behavioral_ode_from_trajectories(
    observations_list: List[np.ndarray],
    latent_dim: int = 4,
    hidden_dim: int = 64,
    epochs: int = 80,
    lr: float = 1e-3,
    device: Optional[torch.device] = None,
) -> AgentDynamicsODE:
    """
    Train the Neural ODE on raw (T, d) trajectory arrays (e.g. from
    generate_training_data.py). No encoder: observed state = latent state.
    Use latent_dim=4 to match [tool_encoded, param_count_norm, payload_norm, delay_norm].
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    ode = AgentDynamicsODE(latent_dim=latent_dim, hidden_dim=hidden_dim).to(device)
    optim = torch.optim.Adam(ode.parameters(), lr=lr)

    for epoch in range(epochs):
        total_loss = 0.0
        n_batch = 0
        random.shuffle(observations_list)
        for obs in observations_list:
            if obs.shape[0] < 2 or obs.shape[1] != latent_dim:
                continue
            obs_t = torch.from_numpy(obs.astype(np.float32)).to(device)
            T = obs_t.size(0)
            t_span = torch.linspace(0.0, float(T - 1), T, device=device)
            z0 = obs_t[0:1]
            optim.zero_grad()
            pred = integrate_ode(ode, z0, t_span)
            if pred.dim() == 3:
                pred = pred.squeeze(1)
            loss = torch.nn.functional.mse_loss(pred, obs_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(ode.parameters(), 1.0)
            optim.step()
            total_loss += loss.item()
            n_batch += 1
        if (epoch + 1) % 20 == 0 and n_batch > 0:
            print(f"  Layer 5 (trajectory) epoch {epoch+1}/{epochs} loss={total_loss/n_batch:.6f}")
    return ode


# -----------------------------------------------------------------------------
# 6. Save / load for deployment
# -----------------------------------------------------------------------------

def save_layer5_checkpoint(
    ode: AgentDynamicsODE,
    encoder: EventEncoder,
    path: str | Path,
) -> None:
    """Save ODE and encoder (and encoder vocab) to disk. Vocab saved as (key, idx) for exact index alignment."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vocab_serialized = [[list(k), v] for k, v in sorted(encoder.vocab.items(), key=lambda x: x[1])]
    state = {
        "ode": ode.state_dict(),
        "encoder": encoder.state_dict(),
        "encoder_vocab": vocab_serialized,
        "latent_dim": ode.latent_dim,
        "encoder_embedding_dim": encoder.embedding_dim,
    }
    torch.save(state, path)


def load_layer5_checkpoint(
    path: str | Path,
    device: Optional[torch.device] = None,
) -> Tuple[AgentDynamicsODE, EventEncoder]:
    """Load ODE and encoder from checkpoint."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    state = torch.load(path, map_location=device, weights_only=True)
    vocab_serialized = state["encoder_vocab"]
    vocab = {tuple(item[0]): item[1] for item in vocab_serialized}
    latent_dim = state["latent_dim"]
    embedding_dim = state.get("encoder_embedding_dim", 24)
    encoder = EventEncoder(vocab, latent_dim, embedding_dim)
    encoder.load_state_dict(state["encoder"])
    encoder = encoder.to(device)
    ode = AgentDynamicsODE(latent_dim=latent_dim)
    ode.load_state_dict(state["ode"])
    ode = ode.to(device)
    return ode, encoder


def save_layer5_trajectory_checkpoint(ode: AgentDynamicsODE, path: str | Path) -> None:
    """Save ODE-only checkpoint (for trajectory-trained model, no encoder)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"ode": ode.state_dict(), "latent_dim": ode.latent_dim}, path)


def load_layer5_trajectory_checkpoint(
    path: str | Path,
    device: Optional[torch.device] = None,
) -> AgentDynamicsODE:
    """Load ODE-only checkpoint from trajectory training."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    state = torch.load(path, map_location=device, weights_only=True)
    latent_dim = state["latent_dim"]
    ode = AgentDynamicsODE(latent_dim=latent_dim)
    ode.load_state_dict(state["ode"])
    return ode.to(device)


# -----------------------------------------------------------------------------
# 7. Public API: analyze a session and return Layer5 result
# -----------------------------------------------------------------------------

@dataclass
class Layer5Result:
    flagged: bool
    anomaly_score: float
    threshold: float
    details: Dict[str, float]
    trajectory_errors: Optional[List[float]] = None


# Default threshold (tune via calibration on normal vs injected sessions)
DEFAULT_L5_THRESHOLD = 0.15


def analyze_session_from_trajectory(
    ode: AgentDynamicsODE,
    trajectory: np.ndarray | torch.Tensor,
    threshold: float = DEFAULT_L5_THRESHOLD,
    device: Optional[torch.device] = None,
) -> Layer5Result:
    """
    Run Layer 5 on a raw (T, d) trajectory (e.g. from encode_tool_call / session_to_trajectory).
    Use with trajectory-trained ODE (load_layer5_trajectory_checkpoint). No encoder.
    """
    if device is None:
        device = next(ode.parameters()).device
    if isinstance(trajectory, np.ndarray):
        obs = torch.from_numpy(trajectory.astype(np.float32)).to(device)
    else:
        obs = trajectory.to(device)
    if obs.dim() == 3:
        obs = obs.squeeze(1)
    if obs.size(0) < 2:
        return Layer5Result(
            flagged=False,
            anomaly_score=0.0,
            threshold=threshold,
            details={"steps": obs.size(0)},
        )
    ode.eval()
    score, details = compute_trajectory_anomaly_score(ode, obs, device=device)
    return Layer5Result(
        flagged=score > threshold,
        anomaly_score=score,
        threshold=threshold,
        details=details,
    )


def analyze_session(
    ode: AgentDynamicsODE,
    encoder: EventEncoder,
    session: List[Tuple[str, str]],
    threshold: float = DEFAULT_L5_THRESHOLD,
    device: Optional[torch.device] = None,
) -> Layer5Result:
    """
    Run Layer 5 on a single session (sequence of (task_type, tool_name)).
    Returns Layer5Result with anomaly score and flag.
    """
    if device is None:
        device = next(ode.parameters()).device
    if len(session) < 2:
        return Layer5Result(
            flagged=False,
            anomaly_score=0.0,
            threshold=threshold,
            details={"steps": len(session)},
        )
    encoder.eval()
    ode.eval()
    with torch.no_grad():
        observed = encoder(session)
    score, details = compute_trajectory_anomaly_score(ode, observed, device=device)
    flagged = score > threshold
    return Layer5Result(
        flagged=flagged,
        anomaly_score=score,
        threshold=threshold,
        details=details,
    )


def get_default_checkpoint_path() -> Path:
    """Default path for Layer 5 checkpoint (under causalguard or cwd)."""
    base = Path(__file__).resolve().parent
    return base / "checkpoints" / "layer5_ode.pt"


def ensure_layer5_model(
    checkpoint_path: Optional[str | Path] = None,
    train_if_missing: bool = True,
    device: Optional[torch.device] = None,
) -> Optional[Tuple[AgentDynamicsODE, EventEncoder]]:
    """
    Load Layer 5 model from checkpoint. If missing and train_if_missing=True,
    train on generated normal sessions and save.
    """
    path = Path(checkpoint_path) if checkpoint_path else get_default_checkpoint_path()
    if path.exists():
        return load_layer5_checkpoint(path, device)
    if not train_if_missing:
        return None
    sessions = generate_normal_sessions(num_sessions=200)
    ode, encoder = train_behavioral_ode(sessions, device=device)
    save_layer5_checkpoint(ode, encoder, path)
    return ode, encoder
