"""
Rebuild C1 (Objection) and C2 (Handling) training data by combining:
- Original CaSiNo data (academic, ground-truth labels)
- New intelligently-labeled SaaS data (domain-specific B2B)
- Claude-labeled data (5x weight)

This gives us ~10K objection examples and ~4K handling examples,
up from ~4K and ~800 respectively.
"""

import json, os, sys, random
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_claude_objection_handling():
    """Extract objection/handling labels from Claude validation sets 3-4 (training only)."""
    obj_examples = []
    hand_examples = []

    for fname in ["claude_validation_set_3.json", "claude_validation_set_4.json"]:
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            convs = json.load(f)

        for conv in convs:
            turns = conv["turns"]
            for i, turn in enumerate(turns):
                labels = turn.get("labels", {})
                text = turn["text"]

                # Objection labels
                obj_type = labels.get("objection_type")
                if obj_type:
                    # Build context window
                    start = max(0, i - 2)
                    window = turns[start:i + 1]
                    window_text = " ".join([f"{t['speaker']}: {t['text']}" for t in window])[:512]
                    obj_examples.append({
                        "text": window_text,
                        "label": obj_type,
                        "source": "claude_opus",
                    })

                # Handling labels (for sales_rep turns following objections)
                handling = labels.get("handling")
                if handling and turn["speaker"] == "sales_rep" and i > 0:
                    prev = turns[i - 1]
                    if prev.get("labels", {}).get("objection_type", "").startswith("objection_"):
                        combined = f"Concern: {prev['text']} Response: {text}"
                        hand_examples.append({
                            "text": combined[:512],
                            "label": handling,
                            "source": "claude_opus",
                        })

    return obj_examples, hand_examples


def main():
    print("=" * 60)
    print("REBUILDING C1 (Objection) + C2 (Handling) TRAINING DATA")
    print("=" * 60)

    # ── Load existing CaSiNo data ──
    casino_c1_path = os.path.join(DATA_DIR, "classifier1_objection.json")
    casino_c2_path = os.path.join(DATA_DIR, "classifier2_handling.json")

    casino_c1 = []
    casino_c2 = []

    if os.path.exists(casino_c1_path):
        with open(casino_c1_path, "r", encoding="utf-8") as f:
            casino_data = json.load(f)
        for split_examples in casino_data.values():
            casino_c1.extend(split_examples)
        print(f"CaSiNo C1: {len(casino_c1)} examples")
    else:
        print("WARNING: No existing C1 data found")

    if os.path.exists(casino_c2_path):
        with open(casino_c2_path, "r", encoding="utf-8") as f:
            casino_data = json.load(f)
        for split_examples in casino_data.values():
            casino_c2.extend(split_examples)
        print(f"CaSiNo C2: {len(casino_c2)} examples")
    else:
        print("WARNING: No existing C2 data found")

    # ── Load SaaS intelligent labels ──
    saas_c1_path = os.path.join(DATA_DIR, "saas_objection_intelligent.json")
    saas_c2_path = os.path.join(DATA_DIR, "saas_handling_intelligent.json")

    with open(saas_c1_path, "r", encoding="utf-8") as f:
        saas_c1 = json.load(f)
    with open(saas_c2_path, "r", encoding="utf-8") as f:
        saas_c2 = json.load(f)

    print(f"SaaS C1: {len(saas_c1)} examples")
    print(f"SaaS C2: {len(saas_c2)} examples")

    # ── Load Claude data (5x weight) ──
    claude_c1, claude_c2 = load_claude_objection_handling()
    print(f"Claude C1: {len(claude_c1)} examples (will be 5x weighted)")
    print(f"Claude C2: {len(claude_c2)} examples (will be 5x weighted)")

    # ═══════════════════════════════════════
    # BUILD C1 DATASET
    # ═══════════════════════════════════════
    print(f"\n--- Building C1 (Objection Detection) ---")

    all_c1 = []
    all_c1.extend(casino_c1)
    all_c1.extend(saas_c1)

    # Claude 5x weight
    for e in claude_c1:
        for _ in range(5):
            all_c1.append(e)

    # Merge objection_fairness into objection_value (too few of each)
    for e in all_c1:
        if e["label"] == "objection_fairness":
            e["label"] = "objection_value"

    print(f"Total C1: {len(all_c1)}")
    c1_dist = Counter(e["label"] for e in all_c1)
    for label, count in c1_dist.most_common():
        print(f"  {label:25s}: {count:6d} ({count/len(all_c1)*100:.1f}%)")

    # Oversample minority classes to at least 200
    c1_groups = {}
    for e in all_c1:
        c1_groups.setdefault(e["label"], []).append(e)

    for label, group in c1_groups.items():
        if len(group) < 200:
            deficit = 200 - len(group)
            all_c1.extend([random.choice(group) for _ in range(deficit)])
            print(f"  Oversampled {label}: {len(group)} -> 200")

    random.shuffle(all_c1)

    # Split 80/10/10
    n = len(all_c1)
    c1_splits = {
        "train": all_c1[:int(n*0.8)],
        "val": all_c1[int(n*0.8):int(n*0.9)],
        "test": all_c1[int(n*0.9):],
    }

    c1_out = os.path.join(DATA_DIR, "classifier1_objection.json")
    with open(c1_out, "w", encoding="utf-8") as f:
        json.dump(c1_splits, f, ensure_ascii=False)
    print(f"  Saved: {c1_out} (train={len(c1_splits['train'])}, val={len(c1_splits['val'])}, test={len(c1_splits['test'])})")

    # ═══════════════════════════════════════
    # BUILD C2 DATASET
    # ═══════════════════════════════════════
    print(f"\n--- Building C2 (Handling Quality) ---")

    all_c2 = []
    all_c2.extend(casino_c2)
    all_c2.extend(saas_c2)

    # Claude 5x weight
    for e in claude_c2:
        for _ in range(5):
            all_c2.append(e)

    print(f"Total C2: {len(all_c2)}")
    c2_dist = Counter(e["label"] for e in all_c2)
    for label, count in c2_dist.most_common():
        print(f"  {label:15s}: {count:6d} ({count/len(all_c2)*100:.1f}%)")

    # Oversample escalated to at least 200
    c2_groups = {}
    for e in all_c2:
        c2_groups.setdefault(e["label"], []).append(e)

    for label, group in c2_groups.items():
        if len(group) < 200:
            deficit = 200 - len(group)
            all_c2.extend([random.choice(group) for _ in range(deficit)])
            print(f"  Oversampled {label}: {len(group)} -> 200")

    random.shuffle(all_c2)

    n = len(all_c2)
    c2_splits = {
        "train": all_c2[:int(n*0.8)],
        "val": all_c2[int(n*0.8):int(n*0.9)],
        "test": all_c2[int(n*0.9):],
    }

    c2_out = os.path.join(DATA_DIR, "classifier2_handling.json")
    with open(c2_out, "w", encoding="utf-8") as f:
        json.dump(c2_splits, f, ensure_ascii=False)
    print(f"  Saved: {c2_out} (train={len(c2_splits['train'])}, val={len(c2_splits['val'])}, test={len(c2_splits['test'])})")

    print(f"\n{'='*60}")
    print("DONE — Ready to retrain C1 and C2")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
