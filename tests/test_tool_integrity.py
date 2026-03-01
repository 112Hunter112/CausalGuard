"""Unit tests for Tool Output Integrity (HMAC signing and verification)."""
import time
import pytest

from causalguard.tool_integrity import (
    SignedToolOutput,
    sign_tool_output,
    verify_tool_output,
    wrap_tool_output,
    unwrap_and_verify,
)


# ---------------------------------------------------------------------------
# sign_tool_output + verify_tool_output roundtrip
# ---------------------------------------------------------------------------

class TestSignVerifyRoundtrip:
    def test_valid_signature_passes(self):
        ts = time.time()
        sig = sign_tool_output("search", "result data", timestamp=ts)
        assert verify_tool_output("search", "result data", ts, sig)

    def test_signature_is_hex_string(self):
        sig = sign_tool_output("tool", "content", timestamp=1000.0)
        assert isinstance(sig, str)
        # HMAC-SHA256 hexdigest is 64 hex chars
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_deterministic_signature(self):
        ts = 12345.0
        sig1 = sign_tool_output("read_file", "data", timestamp=ts)
        sig2 = sign_tool_output("read_file", "data", timestamp=ts)
        assert sig1 == sig2


# ---------------------------------------------------------------------------
# Tampered content fails
# ---------------------------------------------------------------------------

class TestTamperedContent:
    def test_modified_content_fails(self):
        ts = time.time()
        sig = sign_tool_output("search", "original data", timestamp=ts)
        assert not verify_tool_output("search", "TAMPERED data", ts, sig)

    def test_appended_content_fails(self):
        ts = time.time()
        sig = sign_tool_output("tool", "safe output", timestamp=ts)
        assert not verify_tool_output("tool", "safe output + injection", ts, sig)

    def test_empty_vs_nonempty_fails(self):
        ts = time.time()
        sig = sign_tool_output("tool", "", timestamp=ts)
        assert not verify_tool_output("tool", "nonempty", ts, sig)

    def test_modified_timestamp_fails(self):
        ts = time.time()
        sig = sign_tool_output("tool", "content", timestamp=ts)
        assert not verify_tool_output("tool", "content", ts + 1.0, sig)


# ---------------------------------------------------------------------------
# Wrong tool name fails
# ---------------------------------------------------------------------------

class TestWrongToolName:
    def test_different_tool_name_fails(self):
        ts = time.time()
        sig = sign_tool_output("search", "data", timestamp=ts)
        assert not verify_tool_output("send_email", "data", ts, sig)

    def test_case_sensitive_tool_name(self):
        ts = time.time()
        sig = sign_tool_output("Search", "data", timestamp=ts)
        assert not verify_tool_output("search", "data", ts, sig)


# ---------------------------------------------------------------------------
# wrap_tool_output + unwrap_and_verify roundtrip
# ---------------------------------------------------------------------------

class TestWrapUnwrapRoundtrip:
    def test_roundtrip_succeeds(self):
        payload = wrap_tool_output("read_file", "file contents here")
        ok, content = unwrap_and_verify(payload)
        assert ok
        assert content == "file contents here"

    def test_payload_has_required_keys(self):
        payload = wrap_tool_output("tool", "data")
        assert "tool" in payload
        assert "content" in payload
        assert "timestamp" in payload
        assert "signature" in payload

    def test_payload_tool_matches(self):
        payload = wrap_tool_output("my_tool", "output")
        assert payload["tool"] == "my_tool"

    def test_payload_content_matches(self):
        payload = wrap_tool_output("t", "my content")
        assert payload["content"] == "my content"

    def test_signed_tool_output_dataclass_verify(self):
        payload = wrap_tool_output("search", "results")
        sto = SignedToolOutput(
            tool_name=payload["tool"],
            content=payload["content"],
            timestamp=payload["timestamp"],
            signature=payload["signature"],
        )
        assert sto.verify()


# ---------------------------------------------------------------------------
# Tampered payload fails unwrap
# ---------------------------------------------------------------------------

class TestTamperedPayloadUnwrap:
    def test_tampered_content_in_payload(self):
        payload = wrap_tool_output("tool", "original")
        payload["content"] = "INJECTED CONTENT"
        ok, content = unwrap_and_verify(payload)
        assert not ok
        assert content == ""

    def test_tampered_tool_in_payload(self):
        payload = wrap_tool_output("safe_tool", "data")
        payload["tool"] = "malicious_tool"
        ok, content = unwrap_and_verify(payload)
        assert not ok

    def test_tampered_signature_in_payload(self):
        payload = wrap_tool_output("tool", "data")
        payload["signature"] = "0" * 64
        ok, content = unwrap_and_verify(payload)
        assert not ok

    def test_missing_signature_fails(self):
        payload = wrap_tool_output("tool", "data")
        del payload["signature"]
        ok, content = unwrap_and_verify(payload)
        assert not ok

    def test_missing_tool_fails(self):
        payload = wrap_tool_output("tool", "data")
        del payload["tool"]
        ok, content = unwrap_and_verify(payload)
        assert not ok

    def test_empty_payload_fails(self):
        ok, content = unwrap_and_verify({})
        assert not ok
        assert content == ""

    def test_none_values_fail(self):
        ok, content = unwrap_and_verify({"tool": None, "content": None, "signature": None, "timestamp": None})
        assert not ok


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestToolIntegrityEdgeCases:
    def test_unicode_content(self):
        payload = wrap_tool_output("tool", "Unicode content: \u00e9\u00e8\u00ea \u2603 \u2764")
        ok, content = unwrap_and_verify(payload)
        assert ok
        assert "\u00e9" in content

    def test_empty_content_valid(self):
        payload = wrap_tool_output("tool", "")
        ok, content = unwrap_and_verify(payload)
        assert ok
        assert content == ""

    def test_large_content(self):
        large = "x" * 100_000
        payload = wrap_tool_output("tool", large)
        ok, content = unwrap_and_verify(payload)
        assert ok
        assert len(content) == 100_000
