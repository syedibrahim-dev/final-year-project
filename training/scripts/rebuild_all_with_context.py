"""
Rebuild ALL classifier training data with:
1. Intelligently labeled SaaS data (conversation-arc reasoning, not keyword heuristics)
2. Claude-labeled data weighted 5x (highest quality B2B-specific)
3. Context windows for state/willingness (utterance + 2 previous turns)
4. Non-SaaS sources for diversity (CraigslistBargains, etc.)

Data leakage prevention:
  - Claude sets 1-2: VALIDATION ONLY (used in validate_with_claude_labels.py)
  - Claude sets 3-4: TRAINING ONLY (used here)
"""
import sys, os, json, re, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter
random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_claude_data():
    """Load Claude-labeled conversations for TRAINING only.

    IMPORTANT: Sets 1-2 are reserved for validation (validate_with_claude_labels.py).
    Only sets 3+ are used here to avoid data leakage.
    """
    turns_by_conv = {}
    for fname in ["claude_validation_set_3.json", "claude_validation_set_4.json"]:
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            convs = json.load(f)
        for conv in convs:
            cid = conv["conversation_id"]
            turns_by_conv[cid] = {
                "turns": conv["turns"],
                "outcome": conv.get("outcome"),
            }
    return turns_by_conv


def build_context_window(turns, current_idx, window_size=3):
    """Build context text from current turn + previous turns."""
    start = max(0, current_idx - window_size + 1)
    window = turns[start:current_idx + 1]
    parts = []
    for t in window:
        speaker = t.get("speaker", "unknown")
        text = t.get("text", t.get("message", ""))
        parts.append(f"{speaker}: {text}")
    return " ".join(parts)


def main():
    print("=" * 60)
    print("REBUILDING ALL TRAINING DATA WITH INTELLIGENT LABELS")
    print("=" * 60)

    # ── Load intelligently labeled SaaS data ──
    state_intel_path = os.path.join(DATA_DIR, "saas_state_intelligent.json")
    will_intel_path = os.path.join(DATA_DIR, "saas_willingness_intelligent.json")

    with open(state_intel_path, "r", encoding="utf-8") as f:
        saas_state = json.load(f)
    with open(will_intel_path, "r", encoding="utf-8") as f:
        saas_will = json.load(f)

    print(f"SaaS intelligent labels: {len(saas_state)} state, {len(saas_will)} willingness")

    # ── Load Claude data ──
    claude_convs = load_claude_data()
    total_claude_turns = sum(len(c["turns"]) for c in claude_convs.values())
    print(f"Claude conversations: {len(claude_convs)} ({total_claude_turns} turns)")

    # ═══════════════════════════════════════
    # REBUILD SALES STATE TRAINING DATA
    # ═══════════════════════════════════════
    print("\n--- Rebuilding Sales State data ---")

    state_examples = []

    # 1. Intelligently labeled SaaS (primary source)
    for e in saas_state:
        state_examples.append(e)

    # 2. Claude data with context windows (5x weight)
    for cid, conv_data in claude_convs.items():
        turns = conv_data["turns"]
        for i, turn in enumerate(turns):
            state = turn["labels"].get("sales_state")
            if not state:
                continue
            # Merge comparison → evaluation
            if state == "comparison":
                state = "evaluation"
            context = build_context_window(turns, i)
            for _ in range(5):
                state_examples.append({"text": context[:512], "label": state, "source": "claude_opus"})

    # 3. Non-SaaS sources for diversity
    with open(os.path.join(DATA_DIR, "unified_conversations.json"), "r", encoding="utf-8") as f:
        unified = json.load(f)

    other_count = 0
    for conv in unified:
        if conv["source"] in ("deepmost_saas",):
            continue
        turns = conv["turns"]
        if len(turns) < 3:
            continue
        for i in range(0, len(turns), 3):
            end = min(i+3, len(turns))
            window = turns[i:end]
            context = " ".join([f"{t['speaker']}: {t['text']}" for t in window])
            if len(context) < 30:
                continue
            lower = context.lower()
            if any(w in lower for w in ["not interested", "no thanks", "goodbye"]):
                label = "drop_off_risk"
            elif any(w in lower for w in ["schedule", "demo", "sign up", "next step"]):
                label = "decision"
            elif any(w in lower for w in ["expensive", "budget", "not sure", "concerned"]):
                label = "objection"
            elif any(w in lower for w in ["how does", "feature", "integrate", "compare"]):
                label = "evaluation"
            elif any(w in lower for w in ["appreciate", "thank", "understand"]):
                label = "trust"
            else:
                label = "interest"
            state_examples.append({"text": context[:512], "label": label, "source": conv["source"]})
            other_count += 1
            if other_count >= 5000:
                break
        if other_count >= 5000:
            break

    # Oversample minority classes to at least 500
    label_groups = {}
    for e in state_examples:
        label_groups.setdefault(e["label"], []).append(e)

    min_target = 500
    for label, group in label_groups.items():
        if len(group) < min_target:
            deficit = min_target - len(group)
            oversampled = [random.choice(group) for _ in range(deficit)]
            state_examples.extend(oversampled)
            print(f"  Oversampled {label}: {len(group)} -> {len(group) + deficit}")

    random.shuffle(state_examples)
    state_examples = state_examples[:20000]

    n = len(state_examples)
    state_splits = {"train": state_examples[:int(n*0.8)], "val": state_examples[int(n*0.8):int(n*0.9)], "test": state_examples[int(n*0.9):]}
    state_path = os.path.join(DATA_DIR, "sales_state_training.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_splits, f, ensure_ascii=False)

    print(f"  State examples: {len(state_examples)}")
    print(f"  Sources: {dict(Counter(e['source'] for e in state_examples).most_common())}")
    print(f"  Labels: {dict(Counter(e['label'] for e in state_examples).most_common())}")

    # ═══════════════════════════════════════
    # REBUILD WILLINGNESS TRAINING DATA
    # ═══════════════════════════════════════
    print("\n--- Rebuilding Willingness data ---")

    will_examples = []

    # 1. Intelligently labeled SaaS
    for e in saas_will:
        will_examples.append(e)

    # 2. Claude data (5x weight)
    for cid, conv_data in claude_convs.items():
        turns = conv_data["turns"]
        for i, turn in enumerate(turns):
            willingness = turn["labels"].get("willingness")
            if not willingness:
                continue
            context = build_context_window(turns, i)
            for _ in range(5):
                will_examples.append({"text": context[:512], "label": willingness, "source": "claude_opus"})

    # Oversample minority classes
    will_label_groups = {}
    for e in will_examples:
        will_label_groups.setdefault(e["label"], []).append(e)

    for label, group in will_label_groups.items():
        if len(group) < min_target:
            deficit = min_target - len(group)
            oversampled = [random.choice(group) for _ in range(deficit)]
            will_examples.extend(oversampled)
            print(f"  Oversampled {label}: {len(group)} -> {len(group) + deficit}")

    random.shuffle(will_examples)
    will_examples = will_examples[:15000]

    n = len(will_examples)
    will_splits = {"train": will_examples[:int(n*0.8)], "val": will_examples[int(n*0.8):int(n*0.9)], "test": will_examples[int(n*0.9):]}
    will_path = os.path.join(DATA_DIR, "willingness_training.json")
    with open(will_path, "w", encoding="utf-8") as f:
        json.dump(will_splits, f, ensure_ascii=False)

    print(f"  Willingness examples: {len(will_examples)}")
    print(f"  Sources: {dict(Counter(e['source'] for e in will_examples).most_common())}")
    print(f"  Labels: {dict(Counter(e['label'] for e in will_examples).most_common())}")

    print(f"\n{'='*60}")
    print("DATA REBUILD COMPLETE")
    print(f"{'='*60}")
    print(f"  Sales State:   {state_path} ({len(state_examples)} examples)")
    print(f"  Willingness:   {will_path} ({len(will_examples)} examples)")
    print(f"\nKey improvements:")
    print(f"  - Intelligent conversation-arc labeling (not keyword heuristics)")
    print(f"  - Context windows (utterance + 2 previous turns)")
    print(f"  - Claude Opus labels weighted 5x")
    print(f"  - Minority class oversampling to 500+")


if __name__ == "__main__":
    main()
