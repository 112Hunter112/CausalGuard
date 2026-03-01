"""Unit tests for Layer 4 Tool Invocation Anomaly Detector."""
import pytest
from causalguard.layer4_tool_monitor import monitor_tool_calls, infer_task_type, TASK_TOOL_PROFILES


def test_expected_tools_pass():
    r = monitor_tool_calls("email_draft", ["read_document", "send_email"])
    assert not r.flagged
    assert r.unexpected_tools == []
    assert r.jaccard_anomaly_score == 0.0


def test_unexpected_tool_flagged():
    r = monitor_tool_calls("summarize", ["read_document", "log_interactions"])
    assert r.flagged
    assert "log_interactions" in r.unexpected_tools
    assert r.jaccard_anomaly_score > 0


def test_infer_task_type_email():
    assert infer_task_type("Summarize and send email to team@company.com") == "email_draft"
    assert infer_task_type("Please email the draft") == "email_draft"


def test_infer_task_type_summarize():
    assert infer_task_type("Summarize this report") == "summarize"


def test_infer_task_type_search():
    assert infer_task_type("Search the web for X") == "search"

