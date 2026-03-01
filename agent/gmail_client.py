"""
Gmail Client for CausalGuard Live Demo
========================================
Reads real emails from the user's Gmail inbox using Application Default
Credentials (gcloud auth application-default login --scopes=...).
"""

import base64
import re
from html import unescape


def _get_gmail_service():
    """Build a Gmail API service using Application Default Credentials."""
    from google.auth import default
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    creds, _ = default(scopes=SCOPES)
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def _strip_html(html_text: str) -> str:
    """Minimal HTML → plain text conversion."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    # Collapse whitespace but keep newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_header(headers: list, name: str) -> str:
    """Extract a header value from a Gmail message headers list."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_body(payload: dict) -> str:
    """Recursively extract the best text body from a Gmail message payload."""
    mime = payload.get("mimeType", "")

    # Simple single-part message
    if "body" in payload and payload["body"].get("data"):
        raw = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        if "html" in mime:
            return _strip_html(raw)
        return raw

    # Multipart — prefer text/plain, fallback to text/html
    parts = payload.get("parts", [])
    plain = ""
    html = ""
    for part in parts:
        part_mime = part.get("mimeType", "")
        if part_mime == "text/plain" and part.get("body", {}).get("data"):
            plain = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        elif part_mime == "text/html" and part.get("body", {}).get("data"):
            html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        elif "multipart" in part_mime:
            nested = _extract_body(part)
            if nested:
                plain = plain or nested

    if plain:
        return plain
    if html:
        return _strip_html(html)
    return "(no readable body)"


def fetch_inbox(max_results: int = 10, q: str = None) -> list[dict]:
    """
    Fetch the most recent emails from the user's Gmail inbox.
    If q is provided, use Gmail search (e.g. "subject:quora", "from:quora", or plain text search).

    Returns a list of dicts: [{"id": int, "from": str, "subject": str, "body": str, "snippet": str}, ...]
    """
    service = _get_gmail_service()

    list_kw = dict(userId="me", maxResults=max_results, labelIds=["INBOX"])
    if q and q.strip():
        list_kw["q"] = q.strip()

    # List message IDs
    result = service.users().messages().list(**list_kw).execute()

    message_ids = [m["id"] for m in result.get("messages", [])]

    emails = []
    for i, msg_id in enumerate(message_ids, 1):
        msg = service.users().messages().get(
            userId="me",
            id=msg_id,
            format="full",
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])
        body = _extract_body(msg.get("payload", {}))

        emails.append({
            "id": i,
            "from": _get_header(headers, "From"),
            "subject": _get_header(headers, "Subject"),
            "body": body[:3000],  # Cap at 3000 chars for safety
            "snippet": msg.get("snippet", ""),
        })

    return emails


def format_inbox(emails: list[dict]) -> str:
    """Format a list of email dicts into a string for the agent."""
    parts = []
    for email in emails:
        parts.append(
            f"--- Email #{email['id']} ---\n"
            f"From: {email['from']}\n"
            f"Subject: {email['subject']}\n\n"
            f"{email['body']}\n"
        )
    return "\n".join(parts)
