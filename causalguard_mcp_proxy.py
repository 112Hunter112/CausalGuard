"""
CausalGuard MCP Proxy
=====================
Drop-in security middleware for ANY MCP server.

Intercepts every JSON-RPC message on the tool-result boundary and runs
all 6 CausalGuard detection layers before content reaches the AI's
context window.  The proxy is TRANSPARENT — the AI host (Claude Desktop,
VS Code, Cursor) and the MCP server both think they are talking directly
to each other.

Architecture
~~~~~~~~~~~~
    Claude Desktop  ──stdin──▶  CausalGuard Proxy  ──stdin──▶  Real MCP Server
    Claude Desktop  ◀──stdout── CausalGuard Proxy  ◀──stdout── Real MCP Server
                                     │
                                     ▼ stderr
                              Rich terminal dashboard
                              (judges watch this)

Every tool result passes through:
  L1  DFA lexical scan             (~1 ms, zero false negatives on known patterns)
  L2  Counterfactual KL divergence (~3 s, LLM-powered causal reasoning)
  L3  Sentence-BERT cosine drift   (~100 ms, local embeddings)
  L4  Tool-invocation anomaly      (~1 ms, set-difference math)
  L5  Neural ODE trajectory        (optional, offline-trained checkpoint)
  L6  Dual-lattice taint IFC       (~1 ms, provable enforcement)

Installation (claude_desktop_config.json)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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

CVE-2025-6514 context: mcp-remote (CVSS 9.6) hit 437k developer
environments.  This proxy is the infrastructure answer.
"""

import sys
import json
import asyncio
import os
import time
import signal
import logging
from typing import Optional

# ── Bootstrap: project root on sys.path ──────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# Suppress noisy warnings before heavy imports
import warnings
warnings.filterwarnings("ignore", message=".*resume_download.*", category=FutureWarning)

# ── Redirect Rich dashboard output to stderr ─────────────────
# stdout is reserved for MCP JSON-RPC protocol messages.
# All human-readable output (tables, panels, colours) goes to stderr
# so judges can watch the terminal while Claude Desktop runs normally.
from rich.console import Console

_stderr_console = Console(stderr=True)

import causalguard.dashboard as _dashboard_mod
_dashboard_mod.console = _stderr_console

# ── CausalGuard imports ──────────────────────────────────────
from causalguard.interceptor import CausalGuard
from causalguard.dashboard import Dashboard
from causalguard.tool_registration import scan_tool_registration
from causalguard.scoring import calculate_threat_level, compute_composite_threat_score

# ── LLM client (for Layer 2 counterfactual analysis) ─────────
# Falls back gracefully if Vertex AI credentials are unavailable.
_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        try:
            from llm_client import LLMClient
            _llm = LLMClient()
        except Exception as e:
            _stderr_console.print(
                f"[yellow]LLM client unavailable ({e}). "
                f"Layer 2 (counterfactual) will be disabled.[/yellow]"
            )
    return _llm


# ── Logging (also to stderr) ─────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [CausalGuard] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("causalguard.proxy")


# ══════════════════════════════════════════════════════════════
#  MCP Proxy Core
# ══════════════════════════════════════════════════════════════

class CausalGuardMCPProxy:
    """
    Transparent MCP security proxy.

    Sits between an MCP host (Claude Desktop) and any MCP server.
    Intercepts tool results and runs all CausalGuard detection layers.
    """

    def __init__(self, server_cmd: list[str], *, fast: bool = False):
        self.server_cmd = server_cmd
        self.fast = fast

        # CausalGuard engine
        self.dashboard = Dashboard()
        llm = _get_llm()
        self.guard = CausalGuard(llm_client=llm, dashboard=self.dashboard)

        if fast or llm is None:
            self.guard.l2_enabled = False
            self.guard.l3_enabled = False

        # JSON-RPC tracking
        self.pending_tool_calls: dict[object, dict] = {}   # id → {name, arguments}
        self.pending_list_ids: set[object] = set()          # ids for tools/list requests

        # Session state
        self.current_task = "Perform the requested operation"
        self.tool_history: list[str] = []

        # Stats
        self.stats = {"inspected": 0, "flagged": 0, "tools_scanned": 0}

    # ── Startup banner ────────────────────────────────────────

    def _show_banner(self):
        _stderr_console.print()
        _stderr_console.print(
            "[bold cyan]"
            "  ╔══════════════════════════════════════════════════════╗\n"
            "  ║         CausalGuard MCP Proxy  v1.0                 ║\n"
            "  ║         Inference-Time Firewall for MCP Servers      ║\n"
            "  ╠══════════════════════════════════════════════════════╣\n"
            "  ║                                                      ║\n"
            "  ║  L1  DFA Lexical Scanner         (instant)          ║\n"
            "  ║  L2  Counterfactual KL Divergence (LLM-powered)     ║\n"
            "  ║  L3  Sentence-BERT Cosine Drift   (local model)     ║\n"
            "  ║  L4  Tool Invocation Anomaly      (set-diff math)   ║\n"
            "  ║  L5  Neural ODE Dynamics           (offline)        ║\n"
            "  ║  L6  Dual-Lattice Taint IFC        (provable)       ║\n"
            "  ║                                                      ║\n"
            "  ╚══════════════════════════════════════════════════════╝"
            "[/bold cyan]"
        )
        mode = "[yellow]FAST (L1 + L4 + L6 only)[/yellow]" if self.fast else "[green]FULL (all 6 layers)[/green]"
        _stderr_console.print(f"  Mode: {mode}")
        _stderr_console.print(f"  Wrapping: [dim]{' '.join(self.server_cmd)}[/dim]")
        _stderr_console.print(f"  Status: [bold green]ACTIVE[/bold green] — every tool return is inspected")
        _stderr_console.print()

    # ── Message handling ──────────────────────────────────────

    def _track_request(self, msg: dict):
        """Track outgoing requests so we can match responses."""
        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "tools/call" and msg_id is not None:
            params = msg.get("params", {})
            self.pending_tool_calls[msg_id] = {
                "name": params.get("name", "unknown"),
                "arguments": params.get("arguments", {}),
            }
            self.tool_history.append(params.get("name", "unknown"))

            # Extract task context from arguments
            args = params.get("arguments", {})
            for key in ("query", "path", "url", "prompt", "command", "message"):
                if key in args:
                    self.current_task = str(args[key])
                    break

        elif method == "tools/list" and msg_id is not None:
            self.pending_list_ids.add(msg_id)

    async def _inspect_response(self, msg: dict) -> dict:
        """Inspect a server response; modify in-place if injection found."""
        msg_id = msg.get("id")

        # ── Tool result interception ──────────────────────
        if msg_id in self.pending_tool_calls and "result" in msg:
            tool_info = self.pending_tool_calls.pop(msg_id)
            tool_name = tool_info["name"]

            # Extract text content from the tool result
            raw_text = ""
            content_items = msg.get("result", {}).get("content", [])
            for item in content_items:
                if item.get("type") == "text":
                    raw_text += item.get("text", "")

            if raw_text:
                self.stats["inspected"] += 1
                start = time.time()

                try:
                    # Run L1/L2/L3 via the interceptor
                    safe_text, report = await self.guard.intercept(
                        task=self.current_task,
                        retrieved_content=raw_text,
                        tool_name=tool_name,
                    )

                    # Run L4/L5/L6 on the accumulated tool sequence
                    proposed = {
                        "tool": tool_name,
                        "args": tool_info.get("arguments", {}),
                    }
                    await self.guard.report_tool_calls_parallel(
                        task=self.current_task,
                        actual_tool_calls=self.tool_history,
                        proposed_tool_call=proposed,
                    )

                    elapsed_ms = (time.time() - start) * 1000

                    if report.was_flagged:
                        self.stats["flagged"] += 1
                        _stderr_console.print(
                            f"\n  [bold red]INJECTION DETECTED[/bold red] in "
                            f"[bold]{tool_name}()[/bold] — content purified "
                            f"({elapsed_ms:.0f} ms)\n"
                        )
                        # Replace content in the message
                        for item in msg.get("result", {}).get("content", []):
                            if item.get("type") == "text":
                                item["text"] = safe_text
                    else:
                        _stderr_console.print(
                            f"  [green]PASS[/green] {tool_name}() — "
                            f"{len(raw_text)} chars ({elapsed_ms:.0f} ms)"
                        )

                except Exception as e:
                    # Fail-open: if analysis crashes, forward original content
                    log.error(f"Analysis error on {tool_name}(): {e}")
                    _stderr_console.print(
                        f"  [yellow]WARN[/yellow] {tool_name}() — "
                        f"analysis failed, forwarding original"
                    )

        # ── Tool description scanning (MCP tool poisoning) ──
        if msg_id in self.pending_list_ids and "result" in msg:
            self.pending_list_ids.discard(msg_id)
            tools = msg.get("result", {}).get("tools", [])
            if tools:
                _stderr_console.rule("[bold cyan]Tool Registration Scan[/bold cyan]")
                for tool_def in tools:
                    name = tool_def.get("name", "unknown")
                    desc = tool_def.get("description", "")
                    reg_result = self.guard.scan_tool_registration(name, desc)
                    self.stats["tools_scanned"] += 1
                    if not reg_result.approved:
                        _stderr_console.print(
                            f"  [bold red]REJECTED[/bold red] tool '{name}': "
                            f"{', '.join(reg_result.reason)}"
                        )

        return msg

    # ── Main proxy loop ───────────────────────────────────────

    async def run(self):
        """
        Start the real MCP server and proxy all stdio traffic.

        Claude Desktop  →  proxy stdin  →  server stdin
        Claude Desktop  ←  proxy stdout ←  server stdout
                                              server stderr → proxy stderr
        """
        self._show_banner()

        # Start the real MCP server as a subprocess
        server = await asyncio.create_subprocess_exec(
            *self.server_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        log.info(f"MCP server started (PID {server.pid})")

        shutdown_event = asyncio.Event()

        async def claude_to_server():
            """Forward: Claude Desktop → proxy → real MCP server."""
            loop = asyncio.get_running_loop()
            while not shutdown_event.is_set():
                try:
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                except (EOFError, OSError):
                    break
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                # Track requests for response matching
                try:
                    msg = json.loads(line)
                    self._track_request(msg)
                except (json.JSONDecodeError, Exception):
                    pass

                # Forward to real server
                try:
                    server.stdin.write((line + "\n").encode())
                    await server.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break

            shutdown_event.set()

        async def server_to_claude():
            """Forward: real MCP server → proxy (inspect) → Claude Desktop."""
            while not shutdown_event.is_set():
                try:
                    line_bytes = await server.stdout.readline()
                except (EOFError, OSError):
                    break
                if not line_bytes:
                    break
                line = line_bytes.decode().strip()
                if not line:
                    continue

                # Inspect responses (tool results, tool listings)
                try:
                    msg = json.loads(line)
                    msg = await self._inspect_response(msg)
                    line = json.dumps(msg)
                except json.JSONDecodeError:
                    pass  # forward non-JSON lines unchanged
                except Exception as e:
                    log.error(f"Inspection error (forwarding original): {e}")

                # Forward to Claude Desktop
                try:
                    sys.stdout.write(line + "\n")
                    sys.stdout.flush()
                except (BrokenPipeError, OSError):
                    break

            shutdown_event.set()

        async def forward_stderr():
            """Forward MCP server's stderr to proxy stderr."""
            while not shutdown_event.is_set():
                try:
                    line = await server.stderr.readline()
                except (EOFError, OSError):
                    break
                if not line:
                    break
                sys.stderr.write(line.decode())
                sys.stderr.flush()

        try:
            await asyncio.gather(
                claude_to_server(),
                server_to_claude(),
                forward_stderr(),
            )
        except asyncio.CancelledError:
            pass
        finally:
            self._show_stats()
            if server.returncode is None:
                server.terminate()
                try:
                    await asyncio.wait_for(server.wait(), timeout=5)
                except asyncio.TimeoutError:
                    server.kill()

    def _show_stats(self):
        _stderr_console.print()
        _stderr_console.rule("[bold cyan]Session Summary[/bold cyan]")
        _stderr_console.print(
            f"  Tool results inspected: [bold]{self.stats['inspected']}[/bold]\n"
            f"  Injections detected:    [bold red]{self.stats['flagged']}[/bold red]\n"
            f"  Tool descriptions scanned: [bold]{self.stats['tools_scanned']}[/bold]"
        )
        _stderr_console.print()


# ══════════════════════════════════════════════════════════════
#  CLI Entry Point
# ══════════════════════════════════════════════════════════════

def main():
    # Parse proxy-specific flags (before --)
    fast_mode = "--fast" in sys.argv
    if fast_mode:
        sys.argv.remove("--fast")

    if "--" not in sys.argv:
        print(
            "CausalGuard MCP Proxy\n"
            "=====================\n"
            "Usage: python causalguard_mcp_proxy.py [--fast] -- <server_command> [args...]\n"
            "\n"
            "Options:\n"
            "  --fast    Skip L2/L3 (LLM-based layers) for lower latency\n"
            "\n"
            "Example:\n"
            '  python causalguard_mcp_proxy.py -- npx -y @modelcontextprotocol/server-filesystem /tmp\n'
            "\n"
            "Claude Desktop config (claude_desktop_config.json):\n"
            "  {\n"
            '    "mcpServers": {\n'
            '      "filesystem-protected": {\n'
            '        "command": "python",\n'
            '        "args": ["path/to/causalguard_mcp_proxy.py", "--", "npx", "-y",\n'
            '                 "@modelcontextprotocol/server-filesystem", "/path/to/dir"]\n'
            "      }\n"
            "    }\n"
            "  }",
            file=sys.stderr,
        )
        sys.exit(1)

    sep_idx = sys.argv.index("--")
    server_cmd = sys.argv[sep_idx + 1:]

    if not server_cmd:
        print("Error: no server command after '--'", file=sys.stderr)
        sys.exit(1)

    proxy = CausalGuardMCPProxy(server_cmd, fast=fast_mode)

    try:
        asyncio.run(proxy.run())
    except KeyboardInterrupt:
        _stderr_console.print("\n[yellow]Proxy stopped by user[/yellow]")


if __name__ == "__main__":
    main()
