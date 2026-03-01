"""Unit tests for Layer 5 Neural ODE Behavioral Dynamics."""
import pytest

torch = pytest.importorskip("torch")

from causalguard.layer5_neural_ode import (
    AgentDynamicsODE,
    EventEncoder,
    generate_normal_sessions,
    compute_trajectory_anomaly_score,
    analyze_session,
)


def test_agent_dynamics_ode_forward():
    ode = AgentDynamicsODE(latent_dim=8, hidden_dim=16)
    z = torch.randn(2, 8)
    t = torch.tensor(0.5)
    out = ode(t, z)
    assert out.shape == (2, 8)


def test_event_encoder_vocab_and_forward():
    sessions = [
        [("email_draft", "read_document"), ("email_draft", "send_email")],
        [("summarize", "read_document")],
    ]
    vocab = EventEncoder.build_vocab(sessions)
    assert ("email_draft", "read_document") in vocab
    assert ("summarize", "read_document") in vocab
    encoder = EventEncoder(vocab, latent_dim=8, embedding_dim=12)
    events = [("email_draft", "read_document"), ("email_draft", "send_email")]
    z = encoder(events)
    assert z.shape == (2, 8)


def test_generate_normal_sessions():
    sessions = generate_normal_sessions(num_sessions=20, min_steps=2, max_steps=4, seed=1)
    assert len(sessions) == 20
    for s in sessions:
        assert 1 <= len(s) <= 4
        for task, tool in s:
            assert isinstance(task, str) and isinstance(tool, str)


def test_compute_trajectory_anomaly_score():
    latent_dim = 8
    ode = AgentDynamicsODE(latent_dim=latent_dim, hidden_dim=16)
    T = 5
    observed = torch.randn(T, latent_dim) * 0.1
    score, details = compute_trajectory_anomaly_score(ode, observed)
    assert isinstance(score, float)
    assert score >= 0
    assert "mean_l2" in details and "steps" in details


def test_analyze_session_short():
    sessions = generate_normal_sessions(num_sessions=10, seed=2)
    vocab = EventEncoder.build_vocab(sessions)
    encoder = EventEncoder(vocab, latent_dim=8)
    ode = AgentDynamicsODE(latent_dim=8)
    result = analyze_session(ode, encoder, [("email_draft", "read_document")])
    assert not result.flagged
    assert result.anomaly_score == 0.0


def test_analyze_session_two_steps():
    sessions = [
        [("email_draft", "read_document"), ("email_draft", "send_email")],
    ]
    vocab = EventEncoder.build_vocab(sessions)
    encoder = EventEncoder(vocab, latent_dim=8)
    ode = AgentDynamicsODE(latent_dim=8)
    session = [("email_draft", "read_document"), ("email_draft", "send_email")]
    result = analyze_session(ode, encoder, session, threshold=10.0)
    assert isinstance(result.anomaly_score, float)
    assert result.details["steps"] == 2
