# CLAUDE.md - CausalGuard Project Context

## Project Overview
**CausalGuard** is an inference-time firewall designed to protect AI agents from **Indirect Prompt Injection (IPI)** attacks. It deploys as a **transparent MCP security proxy** between any AI host (Claude Desktop, VS Code, Cursor) and any MCP server, intercepting every tool result before it reaches the AI's context window. No changes to the AI host or MCP server required.

**CVE-2025-6514 context:** mcp-remote (CVSS 9.6) hit 437k developer environments via credential compromise and RCE through unvalidated OAuth metadata. CausalGuard is the infrastructure answer.

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
6.  **Layer 6: Dual-Lattice Taint Propagation (Information Flow Control)**
    - Labels every piece of data with a trust level (TRUSTED / UNTRUSTED) and propagates labels through a security lattice (join = least upper bound). Before any tool executes, the engine checks whether UNTRUSTED data flows into a sensitive sink (e.g. email recipient, file path, URL). If so, the tool call is **blocked with a policy violation** — provable enforcement, not probabilistic detection.
    - Research: **FIDES** (Costa et al. 2025, arXiv:2505.23643), **CaMeL** (Debenedetti et al. 2025, arXiv:2503.18813), **MVAR** (mvar-security/mvar, 2025), Denning & Denning (1977) CACM. Implemented in `layer6_taint.py`.

### Tool Output Integrity (Zero-Trust Tool Layer)
- **HMAC-signed tool returns:** When a tool produces output, sign it with HMAC-SHA256. CausalGuard verifies the signature before passing content to detection layers. Tampered content in transit → immediate BLOCK. Implemented in `tool_integrity.py`; set `CAUSALGUARD_HMAC_SECRET` in production.

### Composite Threat Score (CTS)
- **Scoring module** (`scoring.py`) provides `compute_composite_threat_score(l1_risk, l2_causal, l3_drift, l4_tool_anomaly, l5_ode_score)` with bootstrap 95% confidence interval and threat level (LOW/MEDIUM/HIGH/CRITICAL). Weights tunable from calibration.

### Tool Registration Firewall (MCP Tool Poisoning)
- **Pre-execution scan** of tool descriptions using Layer 1 before the agent registers tools. Research: MCPTox, Systematic Analysis of MCP Security (arXiv 2512.08290).

### Attack Taxonomy (Log-To-Leak)
- When an injection is flagged, the report includes a **four-component anatomy**: Trigger, Tool Binding, Justification, Pressure (Log-To-Leak framework).

### Adaptive Attack Resistance
- **The Attacker Moves Second** (Nasr, Carlini et al. 2025): adaptive attacks (gradient, RL, search) broke 12 published defenses with >90% success. CausalGuard's layers have no trainable parameters to optimize against; the dashboard shows an "Adaptive Resistance" card explaining this.

### Purification
- **Purifier Module:** Surgically redacts flagged sentences from the content while preserving legitimate information, allowing the agent to continue its task safely.

## Deployment Modes

### 1. MCP Proxy (for Claude Desktop / Cursor)
- Sits between the AI host and any MCP server; every tool result is run through all 6 layers before the AI sees it.
- **File:** `causalguard_mcp_proxy.py`
- **Usage:** `python causalguard_mcp_proxy.py [--fast] -- <server_command> [args...]`
- **Config:** Point Claude Desktop (or Cursor) at the proxy in `claude_desktop_config.json` instead of the real MCP server.
- Rich terminal dashboard on **stderr**; stdout is reserved for MCP JSON-RPC.
- The **web app does not run the MCP proxy** — it is a separate process. See **RUN_AND_DEMO.md** for full setup.

### 2. Web Dashboard (Session, Attack Lab, Benchmark)
- **Backend:** `python web/app.py` (port 5000)
- **Frontend:** `cd frontend && npm install && npm run dev` (port 5173) → open http://localhost:5173
- **Tabs:** **Session** (chat with protected agent + live defense panel), **Attack Lab** (paste content, run all 6 layers, custom payload simulator), **Benchmark** (InjecAgent ASR comparison).
- **Defense panel:** L1–L6 cards; when any layer flags, a **“Malicious content encountered”** banner appears; **Layer 5** shows a **trajectory deviation** bar (normal vs deviated); **Layer 6** shows **taint flow** (TRUSTED/UNTRUSTED pills with arrows). Sidebar includes a short **MCP** note pointing to RUN_AND_DEMO.md for protecting MCP tools.

### 3. Terminal Demo
- `python main.py` (Two-act: unprotected vs. protected agent)

## Tech Stack
- **Language:** Python 3.10+, **Rust** (optional, Layer 1 DFA via PyO3)
- **Agent LLM:** Claude Sonnet 4.6 via Vertex AI (`anthropic[vertex]`, extended thinking)
- **Web Search:** Gemini 2.5 Pro via Vertex AI (Google Search grounding)
- **Auth:** gcloud CLI credentials (no API keys)
- **Mathematical Libraries:** `numpy`, `scipy`
- **NLP/Embeddings:** `sentence-transformers` (all-MiniLM-L6-v2)
- **Terminal UI:** `rich` (Terminal Dashboard)
- **Web Backend:** Flask + SSE streaming (`web/app.py`)
- **Web Frontend:** React 18 + Vite (`frontend/`)
- **Concurrency:** `asyncio.gather` for parallel L1+L2 and L4+L5+L6
- **MCP Protocol:** JSON-RPC 2.0 over stdio (transparent proxy)
- **Framework:** Custom middleware (Interceptors)

## Project Structure
- `causalguard/`: Core logic (layers 1–6, interceptor, purifier, dashboard, attack_taxonomy, tool_registration, tool_integrity); `checkpoints/` for Layer 5 ODE model.
- `agent/`: The AI agent being protected; tracks tool invocations for Layer 4.
- `attacks/`: Sample malicious payloads including CVE-inspired (cve_2025_copilot_style.txt, supabase_style.txt).
- `web/`: Flask REST API (`web/app.py`):
  - **`/api/analyze`** (POST): Attack Lab — `task` + `content`; streams **all 6 layers** (L1 DFA, L2 counterfactual, L3 semantic, L4 tool anomaly, L5 Neural ODE if checkpoint present, L6 taint), then **decision** with `composite_threat_score`, `attack_anatomy`, purification. L1/L2 run in parallel; L4 uses simulated tools from L2 full intent; L6 uses proposed tool call derived from L2 full intent.
  - **`/api/chat`** (POST): Session — `message`, `scenario` (email | web_research | document | multi_tool | live | live_web), `history`; runs **MultiToolAgent** with **CausalGuard** interceptor, streams agent events and guard reports.
  - **`/api/scenarios`** (GET): Returns **SCENARIOS** from `agent/scenarios.py` for the frontend.
- `agent/`: **MultiToolAgent** (`multi_tool_agent.py`) — real LLM agent with tools (read_email, send_email, web_search, read_document, calendar_check, write_file); **scenarios** (`scenarios.py`) — EMAIL_INBOX, WEB_RESULTS, CALENDAR_EVENTS, DOCUMENT_SCENARIOS, SCENARIOS registry.
- `rust_scanner/`: Optional Rust + PyO3 Layer 1 DFA scanner (`Cargo.toml`, `src/lib.rs`, `pyproject.toml`). Build: `cd rust_scanner && maturin develop --release`. True compiled DFA + SIMD; Python fallback if not installed.
- `frontend/`: React + Vite product-style UI (cool grays, single blue accent; no amber/AI-slop). Three tabs: **Session** (chat + defense panel with L1–L6, “Malicious content encountered” banner when flagged, Layer 5 trajectory deviation bar, Layer 6 taint flow), **Attack Lab** (scenarios + Analyze + Result + custom payload), **Benchmark** (InjecAgent). Sidebar: CausalGuard branding, New session, Scenarios list, Session / Attack Lab / Benchmark, and **MCP** note (see RUN_AND_DEMO.md).
- `RUN_AND_DEMO.md`: **How to run** (backend, frontend, env) and **how to demo** (including “visiting multiple websites” via Attack Lab scenarios and Session → Live Web). Optional **MCP proxy** instructions for Claude Desktop / Cursor.
- `main.py`: Main entry point with menu (A/B/C/D).

## Running the Web Dashboard
1.  **Backend:** `python web/app.py` (runs on port 5000)
2.  **Frontend:** `cd frontend && npm install && npm run dev` (runs on port 5173)
3.  Open **http://localhost:5173**. For full run instructions and demo script (including MCP proxy and “visiting multiple websites”), see **RUN_AND_DEMO.md**.

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
- **FIDES** (Costa et al. 2025, arXiv:2505.23643): Securing AI Agents with IFC; formal taint-tracking for provable guarantees. Basis for Layer 6.
- **CaMeL** (Debenedetti et al. 2025, arXiv:2503.18813): Defeating Prompt Injections by Design; capability-based enforcement. Layer 6 implements a lightweight runtime analogue.
- **MVAR** (mvar-security/mvar, 2025): IFC for LLM Agent Runtimes; dual-lattice with cryptographic provenance.
- **OWASP LLM Top 10:2025**: LLM01 Prompt Injection; CausalGuard maps to LLM01, LLM02, LLM06, LLM08, LLM09 (EU AI Act compliance).
