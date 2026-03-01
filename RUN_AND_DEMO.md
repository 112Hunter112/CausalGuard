# How to Run CausalGuard & Demo (Including “Visiting Multiple Websites”)

## 1. Run the app

### Backend (Flask API, port 5000)

```bash
cd CausalGuard
# Optional: copy .env.example to .env and set GOOGLE_APPLICATION_CREDENTIALS or OPENAI_API_KEY
python web/app.py
```

Leave this terminal open. You should see something like: `Running on http://127.0.0.1:5000`.

### Frontend (Vite, port 5173)

```bash
cd CausalGuard/frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser. The frontend talks to the backend at `http://localhost:5000`.

### Environment (optional)

- **Vertex AI (Gemini):** set `GOOGLE_APPLICATION_CREDENTIALS` or use gcloud default credentials so Layer 2 and the agent work.
- **OpenAI:** set `OPENAI_API_KEY` if you use the OpenAI client.
- See `.env.example` for other knobs (e.g. `LAYER5_ENABLED`, `LAYER5_THRESHOLD`).

---

## 2. MCP proxy (optional — for Claude Desktop / Cursor)

CausalGuard can also protect **any MCP server** (e.g. filesystem, browser, custom tools) via a **transparent proxy**. The proxy runs as a separate process; the **web dashboard does not run the MCP proxy**. Use the proxy when you want to protect tools used by Claude Desktop or Cursor.

### What the MCP proxy does

- Sits between the AI host (Claude Desktop, Cursor) and the real MCP server.
- Every tool result from the MCP server is sent through CausalGuard (all 6 layers) before the AI sees it.
- Judges can watch the Rich terminal dashboard on **stderr** while the AI uses tools.

### How to run the MCP proxy

From the project root:

```bash
# Protect the official filesystem MCP server (example)
python causalguard_mcp_proxy.py -- npx -y @modelcontextprotocol/server-filesystem C:\Users\You\Documents

# Or protect another server (replace the part after --)
python causalguard_mcp_proxy.py -- python -m some_mcp_server
```

Then point Claude Desktop (or Cursor) at the proxy instead of the real server. Example `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "filesystem-protected": {
      "command": "python",
      "args": [
        "C:/path/to/CausalGuard/causalguard_mcp_proxy.py",
        "--",
        "npx", "-y", "@modelcontextprotocol/server-filesystem",
        "C:/Users/you/Documents"
      ]
    }
  }
}
```

The **web app** (Session, Attack Lab, Benchmark) does **not** use this proxy; it uses the Flask backend and the in-app agent. Use the proxy when demoing “Claude Desktop + MCP tools protected by CausalGuard.”

---

## 3. Demo: “Visiting multiple websites” and malicious content

The agent “visits” external content when it calls tools like **web_search** or **read_document**. The demo shows CausalGuard reacting when that content is benign vs when it’s malicious (e.g. a hijack hidden in a “web page” or document).

### Option A: Attack Lab (paste content from “multiple websites”)

Simulates several “pages” or documents; one is malicious.

1. Open **http://localhost:5173** → **Attack Lab**.
2. **Benign “website”:**
   - Select **“Benign Document”** (e.g. sales report).
   - Click **Analyze**.
   - In the right panel you should see **PASS** and **PROTECTED**; Defense status shows layers as expected (no deviation / no violation).
3. **Malicious “website”:**
   - Select **“Hidden Web Injection”** (fake news page with hidden instructions in the HTML).
   - Click **Analyze**.
   - You should see **PURIFY** or **BLOCK**, **THREAT DETECTED**, and which layers fired (e.g. L1, L2, L6). The **Layer 5** card shows trajectory **deviation** if the model is loaded; **Layer 6** shows **taint** (e.g. UNTRUSTED → BLOCK).
4. **Other “sites”:**
   - Repeat with **“Direct Hijack”**, **“Subtle Drift”**, **“Malicious Resume”** to show different attack shapes and how the 6 layers and taint graph respond.

This is your “visiting multiple websites” demo: each scenario is like a different page or document; the Defense panel and (below) the Layer 5/6 visualizations show deviation and taint when malicious content is encountered.

### Option B: Session + Live Web (real search / “visiting” the web)

1. Open **Session** → choose **Live Web** (or **Live Gmail** for email).
2. Send a request that triggers tools, e.g.:
   - “Search the web for the latest AI safety news and summarize.”
   - “Read my latest emails and summarize them.”
3. As the agent runs, the **Defense status** panel updates per tool call. If any tool returns malicious content (in a real scenario), you’d see **THREAT DETECTED**, **Malicious content encountered**, and which layers fired.
4. The **Layer 5** section shows trajectory **deviation** (Neural ODE) when the session is analyzed; **Layer 6** shows the **taint graph** (which data is TRUSTED vs UNTRUSTED and whether the action is allowed).

### What to point out to judges

- **Multiple “websites” / documents:** Attack Lab scenarios = different pages or docs; Session + Live Web = real tool use (search, read email).
- **When malicious content is encountered:** The status switches to **THREAT DETECTED**, the **“Malicious content encountered”** banner appears, and the Layer 5 deviation bar and Layer 6 taint flow show **where** the anomaly and policy violation are.
- **Layer 5 (Neural ODE):** Bar or chart shows “normal trajectory” vs “deviated” (anomaly score vs threshold).
- **Layer 6 (Taint):** Taint graph shows TRUSTED vs UNTRUSTED flow; when content is malicious, UNTRUSTED flows toward a sensitive action and is blocked.

---

## 4. Quick reference

| What you want to do              | Command / place                          |
|----------------------------------|------------------------------------------|
| Run web dashboard + agent        | `python web/app.py` + `cd frontend && npm run dev` |
| Run MCP proxy (Claude/Cursor)    | `python causalguard_mcp_proxy.py -- <real MCP server command>` |
| Demo “multiple websites”        | Attack Lab: switch scenarios (Benign vs Hidden Web Injection, etc.) |
| Demo live “visiting” the web     | Session → Live Web → ask for search/summary |
| See deviation when malicious    | Defense panel → Layer 5 (trajectory deviation) |
| See taint when malicious        | Defense panel → Layer 6 (taint graph + BLOCK) |
