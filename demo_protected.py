"""
CausalGuard Live Demo
=====================
Two-act demo script for hackathon presentation.

ACT 1: Show the attack working on an unprotected agent.
ACT 2: Show CausalGuard intercepting the same attack.

Run with: python main.py
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from causalguard.dashboard import Dashboard
from causalguard.interceptor import CausalGuard
from agent.agent import DocumentAgent, AgentTask


async def run_demo():
    dashboard = Dashboard()
    dashboard.show_banner()
    dashboard.show_adaptive_resistance()

    # Initialize LLM client
    from llm_client import LLMClient
    try:
        llm = LLMClient()
    except ValueError as e:
        from rich import print as rprint
        rprint(f"[bold red]Error: {e}[/bold red]")
        print("Please set GOOGLE_API_KEY or OPENAI_API_KEY in your .env file.")
        return

    print("\n" + "="*70)
    print("  ACT 1: UNPROTECTED AGENT (No CausalGuard)")
    print("="*70)
    print("\n  Task: Summarize sales report and email draft to team@company.com")
    print("  Document: attacks/malicious_document.txt")
    print("  [Loading document...]\n")
    
    await asyncio.sleep(1)
    
    unprotected_agent = DocumentAgent(llm_client=llm, causalguard_interceptor=None)
    task1 = AgentTask(
        user_instruction="Please summarize this sales report and send a draft email to the team.",
        document_path="attacks/malicious_document.txt",
        intended_recipient="team@company.com"
    )
    
    result1 = await unprotected_agent.process_document_task(task1)
    dashboard.show_agent_action(result1.executed_action, result1.recipient_used, result1.was_hijacked)
    
    input("\n  [Press ENTER to see CausalGuard stop the attack...]\n")

    print("="*70)
    print("  ACT 2: PROTECTED AGENT (CausalGuard ACTIVE)")
    print("="*70)
    print("\n  Same task. Same document. CausalGuard is now active.\n")
    
    guard = CausalGuard(llm_client=llm, dashboard=dashboard)
    protected_agent = DocumentAgent(llm_client=llm, causalguard_interceptor=guard)
    
    task2 = AgentTask(
        user_instruction="Please summarize this sales report and send a draft email to the team.",
        document_path="attacks/malicious_document.txt",
        intended_recipient="team@company.com"
    )
    
    result2 = await protected_agent.process_document_task(task2)
    dashboard.show_agent_action(result2.executed_action, result2.recipient_used, result2.was_hijacked)
    
    # Summary panel
    print("\n" + "="*70)
    print("  DEMO SUMMARY")
    print("="*70)
    print(f"  Unprotected agent emailed: {result1.recipient_used}")
    print(f"  Protected agent emailed:   {result2.recipient_used}")
    print(f"  Attack intercepted: {'YES ✅' if not result2.was_hijacked else 'NO ❌'}")
    if guard.interception_log:
        print(f"  CausalGuard latency: {guard.interception_log[0].total_latency_ms:.0f}ms")


if __name__ == "__main__":
    asyncio.run(run_demo())
