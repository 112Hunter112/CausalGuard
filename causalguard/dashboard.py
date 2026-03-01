"""
Terminal Dashboard
==================
Beautiful, informative terminal output for the demo using the Rich library.
Every number is shown. Every decision is explained.
This is what judges watch during the demo.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
import time


console = Console()


class Dashboard:
    
    def show_banner(self):
        console.print(Panel.fit(
            "[bold cyan]CausalGuard[/bold cyan] [white]v1.0 — Inference-Time Firewall[/white]\n"
            "[dim]Mathematical defense against Indirect Prompt Injection[/dim]\n"
            "[dim]Layers: DFA Lexical Scanner | KL Divergence Engine | Semantic Drift Detector[/dim]",
            border_style="cyan"
        ))
    
    def show_intercept_start(self, tool_name: str, content_length: int):
        console.print()
        console.rule(f"[bold yellow]⚡ INTERCEPTED: {tool_name}() → {content_length} chars[/bold yellow]")
    
    def show_l1_result(self, result):
        status = "[bold red]⛔ FLAGGED[/bold red]" if result.is_flagged else "[bold green]✓ CLEAN[/bold green]"
        
        table = Table(title="Layer 1: Lexical DFA Scanner", show_header=True, header_style="bold blue")
        table.add_column("Status", style="bold")
        table.add_column("Risk Score", justify="right")
        table.add_column("Categories Hit")
        table.add_column("Matches Found")
        
        categories = ", ".join(result.pattern_categories_hit) if result.pattern_categories_hit else "none"
        matches = str(len(result.flagged_spans))
        
        table.add_row(status, f"{result.risk_score:.3f}", categories, matches)
        console.print(table)
        
        if result.flagged_spans:
            for start, end, text, cat in result.flagged_spans[:3]:
                console.print(f"  [red]  ↳ [{cat}] '{text[:60]}...' (pos {start}-{end})[/red]")
    
    def show_l2_result(self, result):
        status = "[bold red]⛔ INJECTED[/bold red]" if result.is_flagged else "[bold green]✓ SAFE[/bold green]"
        
        table = Table(title="Layer 2: Counterfactual KL Divergence Engine", show_header=True, header_style="bold magenta")
        table.add_column("Status")
        table.add_column("Causal Score", justify="right")
        table.add_column("Action KL Div", justify="right")
        table.add_column("Param JSD", justify="right")
        table.add_column("Field Jaccard", justify="right")
        
        table.add_row(
            status,
            f"[bold]{result.causal_divergence_score:.4f}[/bold]",
            f"{result.action_type_shift_score:.4f}",
            f"{result.parameter_drift_score:.4f}",
            f"{result.structural_delta_score:.4f}"
        )
        console.print(table)
        
        if result.baseline_intent and result.full_intent:
            console.print(f"  [cyan]Baseline intent:[/cyan] {result.baseline_intent.action_type} → "
                         f"{result.baseline_intent.primary_target or 'N/A'}")
            console.print(f"  [yellow]Full context intent:[/yellow] {result.full_intent.action_type} → "
                         f"{result.full_intent.primary_target or 'N/A'}")
        
        if result.is_flagged:
            console.print(f"  [red]  ↳ {result.explanation}[/red]")
    
    def show_l3_result(self, result):
        status = "[bold red]⛔ DRIFTED[/bold red]" if result.is_flagged else "[bold green]✓ STABLE[/bold green]"
        
        table = Table(title="Layer 3: Semantic Trajectory (Sentence-BERT Cosine Similarity)", 
                     show_header=True, header_style="bold yellow")
        table.add_column("Status")
        table.add_column("Cosine Similarity", justify="right")
        table.add_column("Semantic Drift Score", justify="right")
        table.add_column("Threshold", justify="right")
        
        table.add_row(
            status,
            f"{result.cosine_similarity:.4f}",
            f"{result.semantic_drift_score:.4f}",
            f"{result.threshold_used:.2f}"
        )
        console.print(table)
    
    def show_decision(self, decision: str, threat_level: str, flags: list, purifier_result=None):
        console.print()
        
        colors = {
            "PASS": "bold green",
            "PURIFY": "bold yellow",
            "BLOCK": "bold red"
        }
        threat_colors = {
            "LOW": "green",
            "MEDIUM": "yellow",
            "HIGH": "red",
            "CRITICAL": "bold red on white"
        }
        
        decision_text = Text()
        decision_text.append("\n  DECISION: ", style="bold white")
        decision_text.append(decision, style=colors.get(decision, "white"))
        decision_text.append("  |  THREAT LEVEL: ", style="bold white")
        decision_text.append(threat_level, style=threat_colors.get(threat_level, "white"))
        decision_text.append(f"  |  FLAGS: {', '.join(flags) if flags else 'NONE'}\n", style="bold white")
        
        border = "red" if decision != "PASS" else "green"
        console.print(Panel(decision_text, border_style=border))
        
        if purifier_result and purifier_result.redaction_count > 0:
            console.print(f"  [yellow]🔪 Purifier: Redacted {purifier_result.redaction_count} sentences "
                         f"({purifier_result.redaction_ratio*100:.1f}% of content)[/yellow]")
            for sent, score, cats in purifier_result.redacted_sentences[:3]:
                console.print(f"  [red strike]  ↳ '{sent[:70]}...'[/red strike]")
            console.print(f"  [green]  ✓ {len(purifier_result.clean_sentences)} clean sentences forwarded to agent[/green]")
        
        console.print()
    
    def show_agent_action(self, action: str, recipient: str, hijacked: bool):
        if hijacked:
            console.print(Panel(
                f"[bold red]⚠️  AGENT HIJACKED (UNPROTECTED)[/bold red]\n"
                f"Executed: {action}\n"
                f"Email sent to: [bold red]{recipient}[/bold red]",
                border_style="red"
            ))
        else:
            console.print(Panel(
                f"[bold green]✅ TASK COMPLETED SAFELY[/bold green]\n"
                f"Executed: {action}\n"
                f"Email sent to: [bold green]{recipient}[/bold green]",
                border_style="green"
            ))

    def show_attack_anatomy(self, anatomy):
        """Log-To-Leak taxonomy: Trigger, Tool Binding, Justification, Pressure."""
        from .attack_taxonomy import AttackAnatomy
        if not anatomy or not isinstance(anatomy, AttackAnatomy):
            return
        console.print()
        table = Table(title="ATTACK ANATOMY DETECTED (Log-To-Leak)", show_header=True, header_style="bold red")
        table.add_column("Component")
        table.add_column("Detected")
        for label, items in [
            ("Trigger", anatomy.trigger),
            ("Tool Binding", anatomy.tool_binding),
            ("Justification", anatomy.justification),
            ("Pressure", anatomy.pressure),
        ]:
            if items:
                for text, tag in items:
                    table.add_row(label, f"{text[:55]}... [{tag}]" if len(text) > 55 else f"{text} [{tag}]")
        if any([anatomy.trigger, anatomy.tool_binding, anatomy.justification, anatomy.pressure]):
            console.print(table)
        console.print()

    def show_tool_registration(self, result):
        """Tool Registration Firewall (MCP poisoning scan)."""
        status = "[bold green]✓ APPROVED[/bold green]" if result.approved else "[bold red]⛔ REJECTED[/bold red]"
        console.print(f"  [dim]Tool registration:[/dim] {result.tool_name} → {status}")
        if not result.approved and result.reason:
            console.print(f"    [red]Reason: {', '.join(result.reason)}[/red]")

    def show_l4_result(self, result):
        """Layer 4: Tool invocation anomaly (Log-To-Leak)."""
        status = "[bold red]⛔ UNEXPECTED TOOLS[/bold red]" if result.flagged else "[bold green]✓ EXPECTED[/bold green]"
        table = Table(title="Layer 4: Tool Invocation Anomaly", show_header=True, header_style="bold cyan")
        table.add_column("Status")
        table.add_column("Expected", style="dim")
        table.add_column("Actual")
        table.add_column("Unexpected")
        table.add_column("Jaccard anomaly", justify="right")
        table.add_row(
            status,
            ", ".join(result.expected_tools) or "—",
            ", ".join(result.actual_tools) or "—",
            ", ".join(result.unexpected_tools) or "none",
            f"{result.jaccard_anomaly_score:.3f}",
        )
        console.print(table)
        if result.flagged:
            console.print(f"  [red]  ↳ Log-To-Leak style: unexpected tool(s) invoked[/red]")
        console.print()

    def show_l5_result(self, result):
        """Layer 5: Neural ODE behavioral trajectory anomaly (Chen et al. NeurIPS 2018)."""
        status = "[bold red]⛔ TRAJECTORY DEVIATION[/bold red]" if result.flagged else "[bold green]✓ NORMAL DYNAMICS[/bold green]"
        table = Table(
            title="Layer 5: Neural ODE Behavioral Dynamics",
            show_header=True,
            header_style="bold green",
        )
        table.add_column("Status")
        table.add_column("Anomaly Score (mean L2)", justify="right")
        table.add_column("Threshold", justify="right")
        table.add_column("Steps", justify="right")
        table.add_row(
            status,
            f"{result.anomaly_score:.4f}",
            f"{result.threshold:.3f}",
            str(result.details.get("steps", "—")),
        )
        console.print(table)
        if result.flagged:
            console.print(
                f"  [red]  ↳ Agent trajectory deviated from learned normal dynamics (Chen et al. NeurIPS 2018)[/red]"
            )
        console.print()

    def show_adaptive_resistance(self):
        """Static card: why CausalGuard resists adaptive attacks (The Attacker Moves Second)."""
        console.print(Panel(
            "[bold]Adaptive Attack Resistance[/bold] (The Attacker Moves Second, Nasr et al. 2025)\n"
            "[dim]L1 DFA:[/dim] No parameters → cannot be gradient-attacked\n"
            "[dim]L2 KL:[/dim] Analytical, not learned → resistant to gradient/RL optimization\n"
            "[dim]L3 Cosine:[/dim] Frozen embedding model → no fine-tuning surface\n"
            "[dim]Contrast:[/dim] AI-based detectors have ~millions of tunable parameters.",
            title="Why CausalGuard Resists Adaptive Attacks",
            border_style="blue",
        ))
