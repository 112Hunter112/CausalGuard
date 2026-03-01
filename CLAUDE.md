# CLAUDE.md - CausalGuard Project Context

## Project Overview
**CausalGuard** is an inference-time firewall designed to protect AI agents from **Indirect Prompt Injection (IPI)** attacks. It sits as a middleware between the agent and its data retrieval tools, intercepting content before it reaches the agent's context window.

## Core Architecture
CausalGuard uses a multi-layered defense strategy that deliberately avoids using generative AI for detection to prevent "attack-on-detector" scenarios.

### Detection Layers
1.  **Layer 1: Lexical Injection Boundary Scanner**
    - Uses **Deterministic Finite Automata (DFA)** to match known injection patterns (imperative hijacks, role-switching, etc.).
    - Linear time complexity O(n).
2.  **Layer 2: Counterfactual Causal Divergence Engine**
    - The mathematical core. It compares the agent's intended action *without* the retrieved content (baseline) vs. *with* the content (full context).
    - Uses **KL Divergence**, **Jensen-Shannon Divergence**, and **Jaccard Distance** to measure causal influence.
    - If the content significantly changes the agent's intent, it's flagged as an injection.
3.  **Layer 3: Semantic Trajectory Drift Detector**
    - Uses local **Sentence-BERT** embeddings and **Cosine Similarity** to detect subtle semantic shifts in the agent's plan that information-theoretic measures might miss.
4.  **Layer 4: Tool Invocation Anomaly Detector**
    - Monitors the *set* of tools invoked (Log-To-Leak defense). Expected tools per task type vs. actual invocations; unexpected tools are flagged.
    - Pure set-difference math; no trainable parameters. Research: Log-To-Leak (OpenReview 2025), MCPTox (arXiv 2508.14925).
5.  **Layer 5: Neural ODE Behavioral Dynamics**
    - Learns the continuous-time dynamics of normal agent behavior: dz/dt = f_θ(z, t) (Neural ODE). Trained offline on clean sessions; at inference, integrates the ODE and compares predicted trajectory to the observed (encoded) session. High mean L2 deviation = trajectory anomaly = injection or behavioral hijack.
    - Research: **Chen et al. (2018). Neural Ordinary Differential Equations. NeurIPS 2018 Best Paper.** arXiv:1806.07366. Latent-ODE style application to irregular time series (agent tool-call sequences). Implemented in `layer5_neural_ode.py`; optional dependency `torchdiffeq` (fallback: Euler integration). Train with `python train_layer5.py`; checkpoint at `causalguard/checkpoints/layer5_ode.pt`.

### Tool Registration Firewall (MCP Tool Poisoning)
- **Pre-execution scan** of tool descriptions using Layer 1 before the agent registers tools. Research: MCPTox, Systematic Analysis of MCP Security (arXiv 2512.08290).

### Attack Taxonomy (Log-To-Leak)
- When an injection is flagged, the report includes a **four-component anatomy**: Trigger, Tool Binding, Justification, Pressure (Log-To-Leak framework).

### Adaptive Attack Resistance
- **The Attacker Moves Second** (Nasr, Carlini et al. 2025): adaptive attacks (gradient, RL, search) broke 12 published defenses with >90% success. CausalGuard's layers have no trainable parameters to optimize against; the dashboard shows an "Adaptive Resistance" card explaining this.

### Purification
- **Purifier Module:** Surgically redacts flagged sentences from the content while preserving legitimate information, allowing the agent to continue its task safely.

## Tech Stack
- **Language:** Python 3.10+
- **LLM Support:** Google Gemini (Vertex AI), OpenAI
- **Mathematical Libraries:** `numpy`, `scipy`
- **NLP/Embeddings:** `sentence-transformers` (all-MiniLM-L6-v2)
- **UI:** `rich` (Terminal Dashboard)
- **Framework:** Custom middleware (Interceptors)

## Project Structure
- `causalguard/`: Core logic (layers 1–5, interceptor, purifier, dashboard, attack_taxonomy, tool_registration); `checkpoints/` for Layer 5 ODE model.
- `agent/`: The AI agent being protected; tracks tool invocations for Layer 4.
- `attacks/`: Sample malicious payloads including CVE-inspired (cve_2025_copilot_style.txt, supabase_style.txt).
- `web/`: Flask REST API for the frontend dashboard (streams attack_anatomy in decision).
- `frontend/`: React + Vite dashboard (Adaptive Resistance card, Attack Anatomy, Provenance Graph).
- `main.py`: Main entry point with menu (A/B/C/D).

## Running the Web Dashboard
1.  **Backend:** `python web/app.py` (runs on port 5000)
2.  **Frontend:** `cd frontend && npm install && npm run dev` (runs on port 5173)

## Terminal Demo
- `python main.py` (Two-act theatrical demo: unprotected vs. protected agent)

## Key Research Citations
- **InjecAgent** (ACL 2024): Benchmarking IPI in tool-calling agents.
- **Not what you've signed up for** (AISec 2023): Foundational IPI paper.
- **Spotlighting** (Microsoft Research): Prompt-based defense (which CausalGuard improves upon by being external).
- **Sentence-BERT** (EMNLP 2019): Semantic embeddings.
- **Log-To-Leak** (OpenReview 2025): Tool-invocation injection; four-component taxonomy (Trigger, Tool Binding, Justification, Pressure). Basis for Layer 4 and attack anatomy.
- **The Attacker Moves Second** (Nasr, Carlini et al. 2025, arXiv:2510.09023): Adaptive attacks broke 12 defenses; CausalGuard’s parameter-free design resists gradient/RL optimization.
- **DataSentinel** (IEEE S&P 2025): Minimax formulation; CausalGuard’s Layer 2 is non-trainable so there is nothing for an attacker to optimize against.
- **MCPTox** (arXiv 2508.14925): Tool poisoning benchmark; basis for Layer 4 and Tool Registration Firewall.
- **MCP Security SoK** (arXiv 2512.08290): MindGuard DDG; inspiration for Provenance Graph in frontend.
- **Chen et al. (2018). Neural Ordinary Differential Equations.** NeurIPS 2018 Best Paper. arXiv:1806.07366. Layer 5: continuous-depth dynamics f_θ(z,t); trajectory anomaly = mean L2 prediction error.
