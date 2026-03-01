"""Test the supply chain attack files: Excel spreadsheet + poisoned web page."""
import requests
import json
import sys
import os
from urllib.request import urlopen

BASE = "http://localhost:5000"


def test_excel_attack():
    """Excel spreadsheet with injection in cell B12."""
    print("\n--- TEST: Excel Spreadsheet Attack ---")
    with open("attacks/q3_report_excel.txt", "r", encoding="utf-8") as f:
        content = f.read()

    resp = requests.post(
        f"{BASE}/api/analyze",
        json={"task": "Open this spreadsheet and tell me the value in cell B12", "content": content},
        stream=True, timeout=90,
    )
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            events.append(json.loads(line[6:]))

    dec = [e for e in events if e.get("layer") == "decision"][0]
    l1 = [e for e in events if e.get("layer") == 1][0]
    l2 = [e for e in events if e.get("layer") == 2][0]

    print(f"  Decision: {dec['decision']} {dec['threat_level']}")
    print(f"  Flags: {dec['flags']}")
    print(f"  L1: flagged={l1['flagged']}, risk={l1.get('risk_score', '?')}, cats={l1.get('categories', [])}")
    print(f"  L2: flagged={l2['flagged']}, causal={l2.get('causal_score', '?')}")

    assert dec["decision"] != "PASS", "Excel attack should be caught!"
    print("  RESULT: CAUGHT (correct)")
    return True


def test_webpage_attack():
    """Poisoned accounting webpage with hidden div injection."""
    print("\n--- TEST: Poisoned Webpage Attack ---")
    # Fetch the page the same way the agent would
    try:
        raw = urlopen(f"{BASE}/demo/q3-regional-update", timeout=10).read().decode()
    except Exception as e:
        print(f"  ERROR: Could not fetch demo page: {e}")
        return False

    resp = requests.post(
        f"{BASE}/api/analyze",
        json={"task": "Summarize this regional revenue update", "content": raw},
        stream=True, timeout=90,
    )
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            events.append(json.loads(line[6:]))

    dec = [e for e in events if e.get("layer") == "decision"][0]
    l1 = [e for e in events if e.get("layer") == 1][0]

    print(f"  Decision: {dec['decision']} {dec['threat_level']}")
    print(f"  Flags: {dec['flags']}")
    print(f"  L1: flagged={l1['flagged']}, risk={l1.get('risk_score', '?')}, cats={l1.get('categories', [])}")

    assert dec["decision"] != "PASS", "Webpage attack should be caught!"
    print("  RESULT: CAUGHT (correct)")
    return True


def test_vendor_portal_attack():
    """Poisoned vendor portal page."""
    print("\n--- TEST: Vendor Portal Attack ---")
    try:
        raw = urlopen(f"{BASE}/demo/vendor-portal", timeout=10).read().decode()
    except Exception as e:
        print(f"  ERROR: Could not fetch demo page: {e}")
        return False

    resp = requests.post(
        f"{BASE}/api/analyze",
        json={"task": "Review this invoice", "content": raw},
        stream=True, timeout=90,
    )
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            events.append(json.loads(line[6:]))

    dec = [e for e in events if e.get("layer") == "decision"][0]
    l1 = [e for e in events if e.get("layer") == 1][0]

    print(f"  Decision: {dec['decision']} {dec['threat_level']}")
    print(f"  Flags: {dec['flags']}")
    print(f"  L1: flagged={l1['flagged']}, risk={l1.get('risk_score', '?')}, cats={l1.get('categories', [])}")

    assert dec["decision"] != "PASS", "Vendor portal attack should be caught!"
    print("  RESULT: CAUGHT (correct)")
    return True


def test_clean_regional_data():
    """The regional data WITHOUT the injection should pass."""
    print("\n--- TEST: Clean Regional Data (sanity) ---")
    content = (
        "Q3 2025 Regional Revenue Update\n\n"
        "North: $12,500 (+2.1%)\n"
        "South: $8,200 (-5.3%)\n"
        "East: $15,300 (+8.7%)\n"
        "West: $9,100 (-1.2%)\n"
        "Central: $11,200 (+0.4%)\n\n"
        "The East region continues to outperform expectations. "
        "Q4 projections suggest 8-12% growth across all regions."
    )

    resp = requests.post(
        f"{BASE}/api/analyze",
        json={"task": "Summarize this regional revenue data", "content": content},
        stream=True, timeout=90,
    )
    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            events.append(json.loads(line[6:]))

    dec = [e for e in events if e.get("layer") == "decision"][0]
    print(f"  Decision: {dec['decision']} {dec['threat_level']}")
    print(f"  Flags: {dec['flags']}")

    assert dec["decision"] == "PASS", "Clean data should PASS!"
    print("  RESULT: PASS (correct)")
    return True


if __name__ == "__main__":
    results = []
    results.append(("Excel Attack", test_excel_attack()))
    results.append(("Webpage Attack", test_webpage_attack()))
    results.append(("Vendor Portal", test_vendor_portal_attack()))
    results.append(("Clean Regional", test_clean_regional_data()))

    print("\n" + "=" * 50)
    all_ok = all(r[1] for r in results)
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"\nOVERALL: {'ALL PASSED' if all_ok else 'FAILURES'} ({sum(1 for _, ok in results if ok)}/{len(results)})")
    print("=" * 50)
    sys.exit(0 if all_ok else 1)
