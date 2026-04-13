"""
Process DeepMost SaaS Sales Conversations into training data for all 3 classifiers.

Source: DeepMostInnovations/saas-sales-conversations (1,000 conversations, 12,346 utterances)
This replaces CaSiNo camping negotiation data with actual SaaS sales conversations.

Extraction strategy:
  Classifier 1 (Objection Detection):
    - Customer utterances from failed deals (outcome=0) → likely contain objections
    - Customer utterances from successful deals (outcome=1) → likely not objections
    - conversation_style provides additional signal (skeptical_challenging vs casual_friendly)

  Classifier 2 (Response Quality):
    - Extract customer→rep pairs from conversations
    - In outcome=1: rep responses are likely "resolved"
    - In outcome=0: rep responses are likely "deflected" or "escalated"

  Classifier 3 (Emotion + Pressure):
    - Map conversation_style to emotion/pressure labels
    - Use engagement scores as quality signal
"""

import sys, os, json, re, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def parse_conversation(conv_field):
    """Parse conversation field — could be JSON string or already a list."""
    if isinstance(conv_field, list):
        return conv_field
    if isinstance(conv_field, str):
        try:
            return json.loads(conv_field)
        except json.JSONDecodeError:
            return []
    return []


def save_merged(new_data, name, keep_old=True):
    """Merge new SaaS data with existing training data and save."""
    path = os.path.join(DATA_DIR, f"{name}.json")

    existing = {"train": [], "val": [], "test": []}
    if keep_old and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        old_count = sum(len(v) for v in existing.values())
        # Remove old SaaS data if re-running
        for split in existing:
            existing[split] = [e for e in existing[split] if e.get("source") != "saas_deepmost"]
        kept = sum(len(v) for v in existing.values())
        print(f"  Existing data: {old_count} total, {kept} kept (removed old SaaS)")

    # Shuffle and split new data
    random.shuffle(new_data)
    n = len(new_data)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)

    existing["train"].extend(new_data[:train_end])
    existing["val"].extend(new_data[train_end:val_end])
    existing["test"].extend(new_data[val_end:])

    # Shuffle each split
    for split in existing:
        random.shuffle(existing[split])

    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in existing.values())
    new_labels = Counter(d["label"] for d in new_data)
    print(f"  Added {len(new_data)} SaaS examples. Total: {total}")
    print(f"  New SaaS labels: {dict(new_labels)}\n")


# ── Objection keyword patterns for labeling customer utterances ──
OBJECTION_PATTERNS = {
    "objection_price": [
        r'\b(expensive|costly|price|pricing|budget|afford|cost|discount|cheaper|pay)\b',
        r'\b(roi|return on investment|total cost|hidden fee|worth)\b',
    ],
    "objection_timing": [
        r'\b(not the right time|too soon|not ready|busy|quarter|next year|revisit|later)\b',
        r'\b(bandwidth|capacity|restructuring|priorities)\b',
    ],
    "objection_authority": [
        r'\b(check with|boss|manager|director|cto|cfo|team|committee|approval|sign.off)\b',
        r'\b(decision maker|stakeholder|procurement)\b',
    ],
    "objection_need": [
        r'\b(don.t need|already have|works fine|happy with|current solution|not sure we need)\b',
        r'\b(what problem|why change|survive without|in.house)\b',
    ],
    "objection_trust": [
        r'\b(skeptic|trust|proof|evidence|case study|reference|guarantee|promise)\b',
        r'\b(last vendor|bad experience|burned|mixed review)\b',
    ],
    "objection_competitor": [
        r'\b(competitor|alternative|other vendor|switch|migration|current provider)\b',
    ],
}


def classify_customer_utterance(text, outcome, style):
    """Classify a customer utterance as objection type or not_objection."""
    lower = text.lower()

    # Short messages are usually not objections
    if len(text.strip()) < 20:
        return "not_objection"

    # Check against objection patterns
    for label, patterns in OBJECTION_PATTERNS.items():
        if any(re.search(p, lower) for p in patterns):
            return label

    # Use conversation style as signal
    if style in ("skeptical_challenging", "confused_overwhelmed") and outcome == 0:
        # Failed deal + skeptical style + no specific pattern → generic objection
        if any(w in lower for w in ["but", "however", "not sure", "concern", "worried", "issue"]):
            return "objection_need"

    return "not_objection"


def classify_rep_response(customer_text, rep_text, outcome):
    """Classify rep response quality based on outcome and content."""
    rep_lower = rep_text.lower()

    # Empathy/acknowledgment signals
    has_acknowledgment = bool(re.search(
        r'\b(understand|hear you|valid|fair point|appreciate|makes sense|get that)\b', rep_lower
    ))
    # Question (exploring)
    has_question = "?" in rep_text
    # Solution offered
    has_solution = bool(re.search(
        r'\b(we can|we offer|option|plan|let me show|here.s how|solution|help you)\b', rep_lower
    ))
    # Aggressive signals
    has_aggression = bool(re.search(
        r'\b(you should|you need to|can.t afford|clearly|obviously|no brainer)\b', rep_lower
    ))

    if has_aggression and not has_acknowledgment:
        return "escalated"

    if outcome == 1 and (has_acknowledgment or has_solution):
        return "resolved"
    elif outcome == 0 and not has_acknowledgment and not has_question:
        return "deflected"
    elif has_acknowledgment and has_solution:
        return "resolved"
    elif has_acknowledgment and not has_solution:
        return "deflected"  # acknowledged but didn't address
    elif outcome == 1:
        return "resolved"  # successful deal, benefit of doubt
    else:
        return "deflected"


# Conversation style → emotion/pressure label mapping
STYLE_MAP = {
    "skeptical_challenging": "negative",
    "confused_overwhelmed": "anxious",
    "empathetic_supportive": "empathetic",
    "casual_friendly": "positive",
    "direct_professional": "neutral",
    "technical_detailed": "neutral",
    "knowledgeable_assertive": "positive",
    "consultative_advisory": "consultative",
    "urgent_time_pressed": "urgent",
    "storytelling_narrative": "neutral",
}


def main():
    print("Processing DeepMost SaaS Sales Data\n")

    # Load raw data
    raw_path = os.path.join(DATA_DIR, "saas_raw_1000.json")
    with open(raw_path, "r", encoding="utf-8") as f:
        conversations = json.load(f)
    print(f"Loaded {len(conversations)} conversations\n")

    c1_examples = []  # Objection detection
    c2_examples = []  # Response quality
    c3_examples = []  # Emotion + pressure

    for conv_data in conversations:
        turns = parse_conversation(conv_data["conversation"])
        outcome = conv_data["outcome"]
        style = conv_data.get("conversation_style", "neutral")
        engagement = conv_data.get("customer_engagement", 0.5)

        if not turns or len(turns) < 2:
            continue

        for i, turn in enumerate(turns):
            speaker = turn.get("speaker", "")
            text = turn.get("message", "")
            if not text or len(text.strip()) < 10:
                continue

            # ── Classifier 1: Customer utterances → objection type ──
            if speaker == "customer":
                label = classify_customer_utterance(text, outcome, style)
                c1_examples.append({
                    "text": text.strip(),
                    "label": label,
                    "source": "saas_deepmost",
                })

            # ── Classifier 2: Customer→Rep pairs → response quality ──
            if speaker == "customer" and i + 1 < len(turns):
                next_turn = turns[i + 1]
                if next_turn.get("speaker") == "sales_rep":
                    rep_text = next_turn.get("message", "")
                    if rep_text and len(rep_text.strip()) >= 10:
                        # Only label pairs where customer showed concern
                        cust_label = classify_customer_utterance(text, outcome, style)
                        if cust_label != "not_objection":
                            handling = classify_rep_response(text, rep_text, outcome)
                            c2_examples.append({
                                "text": f"Concern: {text.strip()} Response: {rep_text.strip()}",
                                "label": handling,
                                "source": "saas_deepmost",
                            })

            # ── Classifier 3: All utterances → emotion/pressure ──
            if speaker == "sales_rep":
                # Rep utterances: check for pressure patterns
                rep_lower = text.lower()
                if any(re.search(p, rep_lower) for p in [
                    r'\b(losing money|every day|can.t afford to wait|time is)\b',
                    r'\b(no brainer|obviously|clearly you need|foolish)\b',
                ]):
                    c3_examples.append({"text": text.strip(), "label": "demanding", "source": "saas_deepmost"})
                elif any(re.search(p, rep_lower) for p in [
                    r'\b(limited time|expires|only.*left|this week only|prices going up)\b',
                    r'\b(before.*deadline|sooner.*better|filling up)\b',
                ]):
                    c3_examples.append({"text": text.strip(), "label": "urgent", "source": "saas_deepmost"})
                elif any(re.search(p, rep_lower) for p in [
                    r'\b(take your time|no rush|no pressure|whenever you.re ready)\b',
                    r'\b(what.*helpful|understand|happy to|let me know)\b',
                ]):
                    c3_examples.append({"text": text.strip(), "label": "consultative", "source": "saas_deepmost"})
                else:
                    # Use conversation style as fallback
                    emotion_label = STYLE_MAP.get(style, "neutral")
                    if emotion_label in ("consultative", "urgent", "demanding"):
                        c3_examples.append({"text": text.strip(), "label": emotion_label, "source": "saas_deepmost"})
                    else:
                        c3_examples.append({"text": text.strip(), "label": emotion_label, "source": "saas_deepmost"})

            elif speaker == "customer":
                # Customer utterances: use engagement + style
                emotion_label = STYLE_MAP.get(style, "neutral")
                if engagement < 0.3:
                    emotion_label = "negative"
                elif engagement > 0.8:
                    emotion_label = "positive"
                c3_examples.append({"text": text.strip(), "label": emotion_label, "source": "saas_deepmost"})

    # ── Stats ──
    print(f"{'='*60}")
    print(f"CLASSIFIER 1 (Objection Detection)")
    print(f"{'='*60}")
    print(f"  Extracted {len(c1_examples)} customer utterances")
    print(f"  Labels: {dict(Counter(e['label'] for e in c1_examples))}")
    save_merged(c1_examples, "classifier1_objection")

    print(f"{'='*60}")
    print(f"CLASSIFIER 2 (Response Quality)")
    print(f"{'='*60}")
    print(f"  Extracted {len(c2_examples)} concern→response pairs")
    print(f"  Labels: {dict(Counter(e['label'] for e in c2_examples))}")
    save_merged(c2_examples, "classifier2_handling")

    print(f"{'='*60}")
    print(f"CLASSIFIER 3 (Emotion + Pressure)")
    print(f"{'='*60}")
    print(f"  Extracted {len(c3_examples)} utterances")
    print(f"  Labels: {dict(Counter(e['label'] for e in c3_examples))}")
    save_merged(c3_examples, "classifier3_emotion")

    print(f"{'='*60}")
    print(f"DONE — data files updated in {DATA_DIR}/")
    print(f"Next: retrain all 3 classifiers")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
