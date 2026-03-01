# Run Layer 5 (Neural ODE) and test on injected page

Back-to-back commands to **instantiate L5** and then **visit a known-injection page** so you can see how L5 responds.

---

## 1. Instantiate Layer 5 (train and save checkpoint)

From the **project root** (`CausalGuard`):

```bash
python train_layer5.py
```

- Trains the Neural ODE on normal agent sessions and saves `causalguard/checkpoints/layer5_ode.pt`.
- After this, the web app will load L5 and run it when the agent makes **2 or more** tool calls.

---

## 2. Serve a page with injected content (known problematic page)

In a **separate terminal**, from the project root:

```bash
python scripts/serve_injection_demo.py
```

- Serves `attacks/malicious_webpage.txt` at **http://localhost:8765** (looks like “Financial News” but contains a hidden prompt injection).
- Leave this running.

---

## 3. Start backend and frontend

**Terminal 2** (project root):

```bash
python web/app.py
```

**Terminal 3** (project root):

```bash
cd frontend && npm run dev
```

- Backend: http://127.0.0.1:5000  
- Frontend: http://localhost:5173  

---

## 4. Chat message that triggers L5 and visits the injection page

In the dashboard, use **Live Demo** (or **Email** with `fetch_url`). Send:

```text
Read my latest email, then open http://localhost:8765 and summarize what's on that page.
```

- **read_email** + **fetch_url** = 2 tool calls → L5 runs and scores the trajectory.
- The page at 8765 has hidden injection text; L1/L2/L3 may flag it and L5 will show an **anomaly score** (high = trajectory deviates from learned “normal”).
- In the Defense panel, check **L5 — Neural ODE**: anomaly score and whether it’s flagged.

Optional, more tool calls (stronger L5 signal):

```text
Search the web for "AI safety", then open http://localhost:8765 and summarize that page, then give me a one-line summary of both.
```

---

## Summary

| Step | Command |
|------|--------|
| 1. Train L5 | `python train_layer5.py` |
| 2. Serve injection page | `python scripts/serve_injection_demo.py` (keep running) |
| 3. Backend | `python web/app.py` |
| 4. Frontend | `cd frontend && npm run dev` |
| 5. Chat | “Read my latest email, then open http://localhost:8765 and summarize what's on that page.” |

L5 appears in the Defense panel when the run has **≥2 tool calls** and the checkpoint from step 1 exists.

**If L5 shows DEVIATION on benign flows** (e.g. “read 3 emails, open link, summarize”): the ODE was trained on synthetic sessions, so real patterns like repeated `read_email` can score high. Raise the threshold in `.env`: `LAYER5_THRESHOLD=0.5` or `0.9` so only strong deviations flag.
