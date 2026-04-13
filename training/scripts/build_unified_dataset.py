"""
STEP 2: Build Unified Dataset Format

Downloads and standardizes all Tier 1 + Tier 2 datasets into a common format.
This single clean dataset is used by all downstream models:
  - Outcome Predictor (Step 3)
  - Sales State Model (Step 4)
  - Willingness Predictor (Step 5)

Common format per conversation:
{
    "conversation_id": str,
    "source": str,
    "turns": [{"speaker": "customer"|"sales_rep", "text": str}],
    "metadata": {
        "outcome": 0|1|null,                    # deal closed?
        "engagement": float|null,               # 0-1
        "effectiveness": float|null,            # 0-1
        "conversation_style": str|null,         # e.g. "skeptical_challenging"
        "strategies": [str]|null,               # per-turn strategy labels (CaSiNo)
        "deal_price": float|null,               # final price (CraigslistBargains)
    },
    "num_turns": int,
}

Common format per utterance (for utterance-level models):
{
    "text": str,
    "speaker": "customer"|"sales_rep",
    "conversation_id": str,
    "turn_index": int,
    "source": str,
    "conversation_outcome": 0|1|null,
    "state_label": str|null,                    # for Sales State Model
}
"""

import sys, os, json, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)


def load_deepmost_saas():
    """Load DeepMost SaaS conversations (already downloaded)."""
    raw_path = os.path.join(DATA_DIR, "saas_raw_1000.json")
    if not os.path.exists(raw_path):
        print("  DeepMost SaaS not found. Run prepare_saas_data.py first.")
        return []

    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    conversations = []
    for i, row in enumerate(raw):
        conv_turns = row.get("conversation", "")
        if isinstance(conv_turns, str):
            try:
                conv_turns = json.loads(conv_turns)
            except json.JSONDecodeError:
                continue
        if not isinstance(conv_turns, list) or len(conv_turns) < 2:
            continue

        turns = []
        for t in conv_turns:
            speaker = t.get("speaker", "")
            text = t.get("message", "")
            if speaker in ("customer", "sales_rep") and text and len(text.strip()) >= 5:
                turns.append({"speaker": speaker, "text": text.strip()})

        if len(turns) >= 2:
            conversations.append({
                "conversation_id": f"saas_{i}",
                "source": "deepmost_saas",
                "turns": turns,
                "metadata": {
                    "outcome": row.get("outcome"),
                    "engagement": row.get("customer_engagement"),
                    "effectiveness": row.get("sales_effectiveness"),
                    "conversation_style": row.get("conversation_style"),
                    "strategies": None,
                    "deal_price": None,
                },
                "num_turns": len(turns),
            })

    return conversations


def load_casino():
    """Load CaSiNo from DialogStudio/HuggingFace."""
    print("  Loading CaSiNo...")
    from datasets import load_dataset
    ds = load_dataset("casino", split="train")

    conversations = []
    for i, row in enumerate(ds):
        annotations = row.get("annotations", [])
        if not annotations or len(annotations) < 2:
            continue

        turns = []
        strategies = []
        # CaSiNo alternates between two participants
        for j, ann in enumerate(annotations):
            if not isinstance(ann, list) or len(ann) < 2:
                continue
            text = ann[0]
            strat = ann[1]
            if not text or len(text.strip()) < 5:
                continue
            # Alternate speaker assignment
            speaker = "customer" if j % 2 == 0 else "sales_rep"
            turns.append({"speaker": speaker, "text": text.strip()})
            strategies.append(strat)

        if len(turns) >= 2:
            conversations.append({
                "conversation_id": f"casino_{i}",
                "source": "casino",
                "turns": turns,
                "metadata": {
                    "outcome": None,
                    "engagement": None,
                    "effectiveness": None,
                    "conversation_style": None,
                    "strategies": strategies,
                    "deal_price": None,
                },
                "num_turns": len(turns),
            })

    return conversations


def load_craigslist():
    """Load CraigslistBargains from HuggingFace."""
    print("  Loading CraigslistBargains...")
    from datasets import load_dataset
    try:
        ds = load_dataset("stanfordnlp/craigslist_bargains", split="train")
    except RuntimeError:
        # Legacy dataset script — try alternate loader
        try:
            ds = load_dataset("craigslist_bargains", split="train")
        except Exception:
            print("  WARNING: CraigslistBargains failed to load. Skipping.")
            return []

    conversations = []
    for i, row in enumerate(ds):
        agent_info = row.get("agent_info", {})
        # Try different column names for utterances
        dialogue = row.get("utterance", row.get("dialogue", row.get("turns", [])))

        if not dialogue or len(dialogue) < 2:
            continue

        # Determine outcome from agent_info
        # If agents reached a deal, outcome = 1
        outcome = 1 if row.get("split", "") == "train" else None
        # Check for deal markers in the dialogue
        full_text = " ".join(str(u) for u in dialogue if u).lower()
        if "deal" in full_text or "accept" in full_text or "agree" in full_text:
            outcome = 1
        elif "reject" in full_text or "no deal" in full_text or "walk away" in full_text:
            outcome = 0

        turns = []
        for j, utt in enumerate(dialogue):
            if not utt or not isinstance(utt, str) or len(utt.strip()) < 5:
                continue
            speaker = "customer" if j % 2 == 0 else "sales_rep"
            turns.append({"speaker": speaker, "text": utt.strip()})

        if len(turns) >= 2:
            conversations.append({
                "conversation_id": f"craigslist_{i}",
                "source": "craigslist_bargains",
                "turns": turns,
                "metadata": {
                    "outcome": outcome,
                    "engagement": None,
                    "effectiveness": None,
                    "conversation_style": None,
                    "strategies": None,
                    "deal_price": None,
                },
                "num_turns": len(turns),
            })

    return conversations


def load_goendalf_sales():
    """Load goendalf666/sales-conversations."""
    print("  Loading goendalf666/sales-conversations...")
    from datasets import load_dataset
    ds = load_dataset("goendalf666/sales-conversations", split="train")

    conversations = []
    for i, row in enumerate(ds):
        # This dataset has numbered columns with alternating customer/salesman turns
        turns = []
        for col_idx in range(20):  # up to 20 columns
            text = row.get(str(col_idx), None)
            if text and isinstance(text, str) and len(text.strip()) >= 5:
                speaker = "customer" if col_idx % 2 == 0 else "sales_rep"
                turns.append({"speaker": speaker, "text": text.strip()})

        if len(turns) >= 2:
            conversations.append({
                "conversation_id": f"goendalf_{i}",
                "source": "goendalf_sales",
                "turns": turns,
                "metadata": {
                    "outcome": None,
                    "engagement": None,
                    "effectiveness": None,
                    "conversation_style": None,
                    "strategies": None,
                    "deal_price": None,
                },
                "num_turns": len(turns),
            })

    return conversations


def load_gwenshap_transcripts():
    """Load gwenshap/sales-transcripts."""
    print("  Loading gwenshap/sales-transcripts...")
    from datasets import load_dataset
    try:
        ds = load_dataset("gwenshap/sales-transcripts", split="train")
    except Exception as e:
        print(f"  WARNING: gwenshap/sales-transcripts failed to load: {str(e)[:100]}. Skipping.")
        return []

    conversations = []
    current_conv = []
    conv_idx = 0

    for row in ds:
        text = row.get("text", "")
        if not text or len(text.strip()) < 10:
            continue

        # Parse speaker from text format "Sales Rep: ..." or "Customer: ..."
        if text.startswith("Sales Rep:"):
            current_conv.append({"speaker": "sales_rep", "text": text[len("Sales Rep:"):].strip()})
        elif text.startswith("Customer:"):
            current_conv.append({"speaker": "customer", "text": text[len("Customer:"):].strip()})
        else:
            # New conversation or continuation
            if len(current_conv) >= 2:
                conversations.append({
                    "conversation_id": f"gwenshap_{conv_idx}",
                    "source": "gwenshap_transcripts",
                    "turns": current_conv,
                    "metadata": {
                        "outcome": None, "engagement": None,
                        "effectiveness": None, "conversation_style": None,
                        "strategies": None, "deal_price": None,
                    },
                    "num_turns": len(current_conv),
                })
                conv_idx += 1
            current_conv = []

    # Don't forget last conversation
    if len(current_conv) >= 2:
        conversations.append({
            "conversation_id": f"gwenshap_{conv_idx}",
            "source": "gwenshap_transcripts",
            "turns": current_conv,
            "metadata": {
                "outcome": None, "engagement": None,
                "effectiveness": None, "conversation_style": None,
                "strategies": None, "deal_price": None,
            },
            "num_turns": len(current_conv),
        })

    return conversations


def extract_utterances(conversations):
    """Extract individual utterances from conversations for utterance-level models."""
    utterances = []
    for conv in conversations:
        outcome = conv["metadata"].get("outcome")
        for i, turn in enumerate(conv["turns"]):
            utterances.append({
                "text": turn["text"],
                "speaker": turn["speaker"],
                "conversation_id": conv["conversation_id"],
                "turn_index": i,
                "source": conv["source"],
                "conversation_outcome": outcome,
                "num_turns_total": conv["num_turns"],
                "position_ratio": round(i / max(1, conv["num_turns"] - 1), 2),
            })
    return utterances


def main():
    print("=" * 60)
    print("STEP 2: Building Unified Dataset")
    print("=" * 60 + "\n")

    all_conversations = []

    # Tier 1: Labeled
    print("TIER 1 — Labeled datasets:\n")

    convs = load_deepmost_saas()
    print(f"  DeepMost SaaS: {len(convs)} conversations")
    all_conversations.extend(convs)

    convs = load_casino()
    print(f"  CaSiNo: {len(convs)} conversations")
    all_conversations.extend(convs)

    convs = load_craigslist()
    print(f"  CraigslistBargains: {len(convs)} conversations")
    all_conversations.extend(convs)

    # Tier 2: Unlabeled
    print("\nTIER 2 — Unlabeled datasets:\n")

    convs = load_goendalf_sales()
    print(f"  goendalf666 sales: {len(convs)} conversations")
    all_conversations.extend(convs)

    convs = load_gwenshap_transcripts()
    print(f"  gwenshap transcripts: {len(convs)} conversations")
    all_conversations.extend(convs)

    # Stats
    print(f"\n{'=' * 60}")
    print(f"UNIFIED DATASET SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total conversations: {len(all_conversations)}")

    source_counts = Counter(c["source"] for c in all_conversations)
    for src, count in source_counts.most_common():
        print(f"  {src}: {count}")

    total_turns = sum(c["num_turns"] for c in all_conversations)
    print(f"Total turns: {total_turns}")

    labeled = sum(1 for c in all_conversations if c["metadata"]["outcome"] is not None)
    print(f"With outcome labels: {labeled}")

    # Extract utterances
    utterances = extract_utterances(all_conversations)
    print(f"Total utterances: {len(utterances)}")

    # Save conversation-level dataset
    conv_path = os.path.join(DATA_DIR, "unified_conversations.json")
    with open(conv_path, "w", encoding="utf-8") as f:
        json.dump(all_conversations, f, ensure_ascii=False)
    print(f"\nSaved: {conv_path}")

    # Save utterance-level dataset
    utt_path = os.path.join(DATA_DIR, "unified_utterances.json")
    with open(utt_path, "w", encoding="utf-8") as f:
        json.dump(utterances, f, ensure_ascii=False)
    print(f"Saved: {utt_path}")

    # Save summary stats
    stats = {
        "total_conversations": len(all_conversations),
        "total_utterances": len(utterances),
        "sources": dict(source_counts),
        "labeled_outcomes": labeled,
        "avg_turns": round(total_turns / max(1, len(all_conversations)), 1),
    }
    stats_path = os.path.join(DATA_DIR, "unified_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"Saved: {stats_path}")

    print(f"\n{'=' * 60}")
    print("STEP 2 COMPLETE — Unified dataset ready")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
