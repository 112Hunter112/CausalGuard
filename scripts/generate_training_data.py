"""
Generate synthetic normal agent session trajectories for Neural ODE training.

Uses InjecAgent's legitimate user_cases.jsonl as a template: each case gives
User Tool and Tool Parameters. We synthesize tool_call sequences with
timestamps and encode them into (T, d) feature vectors for trajectory training.

Feature vector per step: [tool_encoded, param_count_norm, payload_size_norm, inter_call_delay_norm]
Output: data/normal_trajectories.npy (object array of (T, 4) arrays).

Run: python scripts/generate_training_data.py
Then optionally train Layer 5 on these trajectories: python scripts/train_layer5_trajectories.py
"""

import ast
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INJECAGENT_PATH = DATA_DIR / "InjecAgent" / "user_cases.jsonl"
OUTPUT_PATH = DATA_DIR / "normal_trajectories.npy"

# Tool name -> normalized id [0,1]. Map InjecAgent-style and CausalGuard tools.
TOOL_ENCODING = {
    "read_email": 0,
    "gmailreademail": 0,
    "send_email": 1,
    "read_file": 2,
    "read_document": 2,
    "write_file": 3,
    "web_search": 4,
    "webbrowsernavigateto": 4,
    "calendar": 5,
    "googlecalendarreadevents": 5,
    "googlecalendargeteventsfromsharedcalendar": 5,
    "contacts": 6,
    "amazongetproductdetails": 0.1,
    "evernotemanagersearchnotes": 0.2,
    "githubgetrepositorydetails": 0.3,
    "githubgetuserdetails": 0.35,
    "githubsearchrepositories": 0.4,
    "gmailsearchemails": 0.05,
    "shopifygetproductdetails": 0.15,
    "teladocviewreviews": 0.2,
    "todoistsearchtasks": 0.25,
    "twiliogetreceivedsmsmessages": 0.1,
    "twittermanagergetuserprofile": 0.3,
    "twittermanagerreadtweet": 0.35,
    "twittermanagersearchtweets": 0.4,
    "unknown": 7,
}


def _tool_to_encoded(tool_name: str) -> float:
    key = (tool_name or "").strip().lower().replace(" ", "")
    for k, v in TOOL_ENCODING.items():
        if k in key or key in k:
            return v / 7.0
    return TOOL_ENCODING["unknown"] / 7.0


def _parse_params(tool_params: str) -> dict:
    if not tool_params:
        return {}
    s = (tool_params or "").strip()
    if s.startswith("{"):
        try:
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            try:
                return json.loads(s.replace("'", '"'))
            except Exception:
                pass
    return {}


def encode_tool_call(
    tool_name: str,
    params: dict,
    delay_ms: float,
    task_context: str = "",
) -> np.ndarray:
    """Single step feature vector: [tool_id_norm, param_count_norm, payload_norm, delay_norm]."""
    tool_id = _tool_to_encoded(tool_name)
    param_count = min(len(params) / 10.0, 1.0)
    payload_size = min(sum(len(str(v)) for v in params.values()) / 1000.0, 1.0)
    delay_norm = min(delay_ms / 5000.0, 1.0)
    return np.array([tool_id, param_count, payload_size, delay_norm], dtype=np.float32)


def session_to_trajectory(tool_calls: list) -> np.ndarray:
    """
    Convert a list of tool calls into a (T, d) array for Neural ODE training.
    T = number of calls, d = 4.
    """
    vectors = []
    prev_time = 0
    for call in tool_calls:
        ts = call.get("timestamp", prev_time + 500)
        delay = max(ts - prev_time, 0)
        vec = encode_tool_call(
            call.get("tool", "unknown"),
            call.get("params", {}),
            delay,
            call.get("task_context", ""),
        )
        vectors.append(vec)
        prev_time = ts
    return np.array(vectors)


def load_user_cases(path: Path) -> list:
    out = []
    if not path.exists():
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def user_case_to_tool_call(case: dict, timestamp_ms: int) -> dict:
    """Turn one InjecAgent user case into a synthetic tool_call dict."""
    tool = case.get("User Tool") or case.get("user_tool") or "unknown"
    params_str = case.get("Tool Parameters") or case.get("tool_parameters") or "{}"
    params = _parse_params(params_str)
    return {"tool": tool, "params": params, "timestamp": timestamp_ms}


def main():
    print("Synthetic training data generation for Layer 5 (Neural ODE)")
    print()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not INJECAGENT_PATH.exists():
        print(f"Missing {INJECAGENT_PATH}. Run: python scripts/download_datasets.py")
        sys.exit(1)

    user_cases = load_user_cases(INJECAGENT_PATH)
    print(f"Loaded {len(user_cases)} benign user cases from InjecAgent.")

    trajectories = []
    # Build 2-step sessions from consecutive pairs (like download_datasets)
    for i in range(len(user_cases) - 1):
        t0 = 0
        t1 = 500 + random.randint(0, 500)
        call0 = user_case_to_tool_call(user_cases[i], t0)
        call1 = user_case_to_tool_call(user_cases[i + 1], t1)
        traj = session_to_trajectory([call0, call1])
        trajectories.append(traj)

    # Also add longer synthetic sessions: chain 3–4 tools with random delays
    for _ in range(200):
        n = random.randint(2, 4)
        indices = random.choices(range(len(user_cases)), k=n)
        calls = []
        prev_ts = 0
        for idx in indices:
            prev_ts += 300 + random.randint(0, 700)
            calls.append(user_case_to_tool_call(user_cases[idx], prev_ts))
        traj = session_to_trajectory(calls)
        trajectories.append(traj)

    trajectories = np.array(trajectories, dtype=object)
    np.save(OUTPUT_PATH, trajectories)
    print(f"Saved {len(trajectories)} trajectories to {OUTPUT_PATH}")
    print(f"  Each trajectory shape: (T, 4) with T in [2, 4].")
    print()
    print("Train Layer 5 on these trajectories:")
    print("  python scripts/train_layer5_trajectories.py")
    print("Done.")


if __name__ == "__main__":
    main()
