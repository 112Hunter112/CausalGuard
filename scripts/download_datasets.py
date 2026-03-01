"""
Download all datasets from trainingAdvice.txt and run CausalGuard on them.

Datasets:
1. InjecAgent (GitHub raw) - user_cases.jsonl, attacker_cases_dh.jsonl, attacker_cases_ds.jsonl
2. Microsoft LLMail-Inject (HuggingFace) - optional, large
3. deepset prompt-injections (HuggingFace)
4. ToolBench (HuggingFace) - may not exist as stated
5. AgentHarm (GitHub) - optional clone

Usage: python scripts/download_datasets.py
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlretrieve, urlopen

# Project root
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

INJECAGENT_BASE = "https://raw.githubusercontent.com/uiuc-kang-lab/InjecAgent/main/data"


def download_injecagent():
    """Download InjecAgent JSONL files from GitHub."""
    sub = DATA_DIR / "InjecAgent"
    sub.mkdir(exist_ok=True)
    for name in ["user_cases.jsonl", "attacker_cases_dh.jsonl", "attacker_cases_ds.jsonl"]:
        path = sub / name
        if path.exists():
            print(f"  [skip] {path} (exists)")
            continue
        url = f"{INJECAGENT_BASE}/{name}"
        print(f"  Downloading {url} ...")
        try:
            urlretrieve(url, path)
            print(f"  -> {path}")
        except Exception as e:
            print(f"  ERROR: {e}")
    return sub


def load_injecagent_user_cases(data_dir: Path):
    """Load user_cases.jsonl; return list of dicts."""
    path = data_dir / "InjecAgent" / "user_cases.jsonl"
    if not path.exists():
        return []
    out = []
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


def load_injecagent_attacker_cases(data_dir: Path, which: str):
    """Load attacker_cases_dh or attacker_cases_ds."""
    path = data_dir / "InjecAgent" / f"attacker_cases_{which}.jsonl"
    if not path.exists():
        return []
    out = []
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


def injecagent_to_layer5_sessions(user_cases: list) -> list:
    """Convert InjecAgent user_cases to Layer 5 format: list of [(task_type, tool_name), ...].
    Each user case has one tool; we form 2-step sessions by pairing consecutive cases."""
    sessions = []
    for i, row in enumerate(user_cases):
        tool = row.get("User Tool") or row.get("user_tool") or "unknown"
        task_type = "user"
        if i + 1 < len(user_cases):
            next_row = user_cases[i + 1]
            next_tool = next_row.get("User Tool") or next_row.get("user_tool") or "unknown"
            sessions.append([(task_type, tool), (task_type, next_tool)])
        else:
            sessions.append([(task_type, tool)])
    return [s for s in sessions if len(s) >= 2]


def run_layer1_on_texts(texts: list, limit: int = 500):
    """Run Layer 1 scanner on a list of text strings. Returns (flagged_count, total)."""
    from causalguard.layer1_lexical import scan
    total = min(len(texts), limit)
    flagged = 0
    for i in range(total):
        r = scan(texts[i] if isinstance(texts[i], str) else str(texts[i])[:5000])
        if r.is_flagged:
            flagged += 1
    return flagged, total


def run_layer5_train_and_eval(sessions_benign: list, sessions_attack: list):
    """Train Layer 5 on benign sessions, evaluate on attack sessions."""
    from causalguard.layer5_neural_ode import (
        EventEncoder,
        AgentDynamicsODE,
        train_behavioral_ode,
        analyze_session,
        save_layer5_checkpoint,
        get_default_checkpoint_path,
    )
    if len(sessions_benign) < 10:
        print("  [Layer 5] Not enough benign sessions to train; need >= 10.")
        return
    print("  Training Layer 5 on InjecAgent benign sessions ...")
    ode, encoder = train_behavioral_ode(
        sessions_benign,
        latent_dim=32,
        epochs=50,
        lr=1e-3,
    )
    ckpt = ROOT / "causalguard" / "checkpoints" / "layer5_injecagent.pt"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    save_layer5_checkpoint(ode, encoder, ckpt)
    print(f"  Saved checkpoint: {ckpt}")
    # Evaluate on attack sessions (expect high anomaly)
    if sessions_attack:
        scores = []
        for s in sessions_attack[:100]:
            if len(s) < 2:
                continue
            r = analyze_session(ode, encoder, s, threshold=999.0)
            scores.append(r.anomaly_score)
        if scores:
            avg = sum(scores) / len(scores)
            print(f"  Attack sessions (n={len(scores)}): mean anomaly score = {avg:.4f} (high = good detection)")


def main():
    print("=" * 60)
    print("CausalGuard — Download datasets & run model")
    print("=" * 60)
    print()
    print("1. Downloading InjecAgent (user + attacker cases) ...")
    download_injecagent()
    print()

    user_cases = load_injecagent_user_cases(DATA_DIR)
    attacker_dh = load_injecagent_attacker_cases(DATA_DIR, "dh")
    attacker_ds = load_injecagent_attacker_cases(DATA_DIR, "ds")
    print(f"  Loaded: {len(user_cases)} user cases, {len(attacker_dh)} attacker_dh, {len(attacker_ds)} attacker_ds")
    print()

    print("2. Layer 1 on InjecAgent attacker instructions (expect many flagged) ...")
    texts_attack = []
    for row in attacker_dh + attacker_ds:
        t = row.get("Attacker Instruction") or row.get("Attacker instruction") or ""
        if t:
            texts_attack.append(t)
    if texts_attack:
        flagged, total = run_layer1_on_texts(texts_attack, limit=min(500, len(texts_attack)))
        print(f"  Layer 1: {flagged}/{total} attacker instructions flagged as injection ({100*flagged/max(1,total):.1f}%)")
    print()

    print("3. Layer 1 on InjecAgent user instructions (expect few flagged = benign) ...")
    texts_user = []
    for row in user_cases:
        t = row.get("User Instruction") or row.get("User instruction") or ""
        if t:
            texts_user.append(t)
    if texts_user:
        flagged, total = run_layer1_on_texts(texts_user, limit=min(500, len(texts_user)))
        print(f"  Layer 1: {flagged}/{total} user instructions flagged ({100*flagged/max(1,total):.1f}% — low is good)")
    print()

    print("4. Layer 5: train on benign sessions, eval on attack sessions ...")
    sessions_benign = injecagent_to_layer5_sessions(user_cases)
    sessions_attack = []
    for row in attacker_dh + attacker_ds:
        tools = row.get("Attacker Tools") or row.get("attacker_tools") or []
        if isinstance(tools, list) and len(tools) >= 1:
            task_type = "attacker"
            seq = [(task_type, str(t)) for t in tools]
            if len(seq) == 1:
                seq = [seq[0], seq[0]]
            sessions_attack.append(seq)
    run_layer5_train_and_eval(sessions_benign, sessions_attack)
    print()

    print("5. HuggingFace: deepset/prompt-injections (Layer 1 validation) ...")
    try:
        from datasets import load_dataset
        ds = load_dataset("deepset/prompt-injections")
        texts_hf = []
        labels_hf = []
        for split in ["train", "test", "validation"]:
            if split in ds:
                for ex in ds[split]:
                    text = ex.get("text") or ex.get("content") or ""
                    label = ex.get("label", -1)
                    if text:
                        texts_hf.append(text)
                        labels_hf.append(label)
        if texts_hf:
            flagged, total = run_layer1_on_texts(texts_hf, limit=min(500, len(texts_hf)))
            inj_count = sum(1 for l in labels_hf[:total] if l == 1)
            print(f"  Loaded {len(texts_hf)} examples. Layer 1 on first {total}: {flagged} flagged.")
            print(f"  (Label 1 = injection in data; compare Layer 1 flags to labels for precision/recall.)")
        else:
            print("  No 'text' field found; check dataset schema.")
    except Exception as e:
        print(f"  ERROR (install: pip install datasets): {e}")
    print()

    print("6. HuggingFace: microsoft/llmail-inject-challenge (optional, large) ...")
    try:
        from datasets import load_dataset
        ds = load_dataset("microsoft/llmail-inject-challenge", split="Phase1[:500]")
        texts_ll = []
        for ex in ds:
            text = ex.get("attack") or ex.get("prompt") or ex.get("text") or str(ex)[:2000]
            if text:
                texts_ll.append(text)
        if texts_ll:
            flagged, total = run_layer1_on_texts(texts_ll, limit=len(texts_ll))
            print(f"  Layer 1 on {total} LLMail samples: {flagged} flagged ({100*flagged/max(1,total):.1f}%)")
        else:
            print("  No text field found.")
    except Exception as e:
        print(f"  Skip or ERROR: {e}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
