"""
Agent Tools
===========
Definitions for tools available to the agent.
Used for Tool Registration Firewall (MCP poisoning scan).
"""

# Tool name → description (scanned at registration for injection patterns)
TOOL_DESCRIPTIONS = {
    "read_document": "Read a document from disk. Returns file contents as string.",
    "send_email": "Send an email to a recipient. Parameters: recipient, subject, body.",
}
