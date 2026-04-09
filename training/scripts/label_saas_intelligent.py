"""
Intelligent labeling of DeepMost SaaS conversations for Sales State + Willingness.

Instead of keyword heuristics, this uses conversation-arc logic:
- Position in conversation + outcome determines the EXPECTED arc
- Turn content confirms or overrides the expected state
- Conversation dynamics (question→answer, objection→response) are tracked
- DeepMost metadata (style, outcome) informs the labeling

This produces labels much closer to how a frontier model (Claude) would label,
because it reasons about the CONVERSATION FLOW, not individual keywords.
"""

import json, os, re, sys, random
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── Content signals (what the turn is SAYING) ──

def has_price_concern(text):
    return bool(re.search(r'\b(expensive|costly|price|pricing|budget|afford|cost|invest|pay|\$\d|month)\b', text.lower()))

def has_objection(text):
    lower = text.lower()
    return bool(re.search(r'\b(but |however|concern|worried|skeptic|doubt|hesitant|risky|not sure|idk|dunno|struggle|complicated|nightmare|difficult|hard to)\b', lower))

def has_competitor_or_comparison(text):
    return bool(re.search(r'\b(competitor|alternative|other (tool|solution|option)|already (use|have|using)|current (tool|setup|solution)|compared to|versus)\b', text.lower()))

def has_technical_question(text):
    return bool(re.search(r'\b(integrate|integration|api|security|compliance|data|scale|performance|feature|how does|support|compatible|CI/CD|pipeline|architecture)\b', text.lower()))

def has_interest_signal(text):
    return bool(re.search(r'\b(interesting|tell me more|curious|how does|can you explain|walk me through|what about|show me|demo)\b', text.lower())) or text.strip().endswith('?')

def has_commitment_signal(text):
    return bool(re.search(r'\b(next step|move forward|get started|sign up|trial|pilot|schedule|let.s do|sounds (good|great)|deal|ready|set up|onboard|implement|go ahead|proceed)\b', text.lower()))

def has_disengagement_signal(text):
    return bool(re.search(r'\b(not interested|no thanks|pass|don.t need|too busy|think about it|get back to you|maybe later|not (right now|the right|looking)|send .* email|we.ll see)\b', text.lower()))

def has_rapport_signal(text):
    return bool(re.search(r'\b(thanks|thank you|appreciate|makes sense|i see|got it|understand|fair enough|good point|that.s helpful|great|awesome|perfect)\b', text.lower()))

def has_pushback(text):
    """Stronger than objection — active resistance."""
    lower = text.lower()
    return bool(re.search(r'\b(no way|too (much|expensive|high)|can.t (justify|afford)|won.t work|not worth|waste|don.t (see|think|believe)|disagree)\b', lower))


def label_conversation(conv):
    """Label each turn in a conversation with sales_state and willingness."""
    turns = conv["turns"]
    outcome = conv.get("outcome")  # 1=converted, 0=failed
    style = conv.get("style", "")
    num_turns = len(turns)
    labeled_turns = []

    # Track conversation dynamics
    last_was_objection = False
    objection_count = 0
    commitment_seen = False

    for i, turn in enumerate(turns):
        text = turn["text"]
        speaker = turn["speaker"]
        pos = i / max(1, num_turns - 1)  # 0.0 = start, 1.0 = end

        # ── Determine sales_state ──
        state = None
        willingness = None

        if speaker == "customer":
            # Customer turns — this is where buyer psychology shows

            # Check content signals
            is_price = has_price_concern(text)
            is_objection = has_objection(text)
            is_technical = has_technical_question(text)
            is_interest = has_interest_signal(text)
            is_commitment = has_commitment_signal(text)
            is_disengaged = has_disengagement_signal(text)
            is_rapport = has_rapport_signal(text)
            is_comparison = has_competitor_or_comparison(text)
            is_pushback = has_pushback(text)

            # Priority-based classification (most specific wins)
            if is_disengaged:
                state = "drop_off_risk"
                willingness = "disengaged"
            elif is_commitment:
                state = "decision"
                willingness = "engaged"
                commitment_seen = True
            elif is_pushback or (is_price and is_objection):
                state = "objection"
                willingness = "neutral" if pos < 0.7 else "disengaged"
                objection_count += 1
                last_was_objection = True
            elif is_objection and not is_interest:
                state = "objection"
                willingness = "neutral"
                objection_count += 1
                last_was_objection = True
            elif is_comparison or is_technical:
                state = "evaluation"
                willingness = "engaged"
            elif is_price and not is_objection:
                # Asking about price without pushback = evaluation (engaged buyer)
                state = "evaluation"
                willingness = "engaged"
            elif is_interest:
                state = "interest"
                willingness = "engaged"
            elif is_rapport and pos < 0.3:
                state = "trust"
                willingness = "neutral"
            elif is_rapport and pos >= 0.3:
                # Late rapport after substantive discussion = positive engagement
                state = "interest" if not commitment_seen else "decision"
                willingness = "engaged"
            else:
                # Default based on position and outcome arc
                if pos < 0.15:
                    state = "trust"
                    willingness = "neutral"
                elif pos < 0.4:
                    state = "interest"
                    willingness = "engaged" if outcome == 1 else "neutral"
                elif pos < 0.7:
                    state = "evaluation"
                    willingness = "engaged" if outcome == 1 else "neutral"
                else:
                    # Late conversation — outcome matters
                    if outcome == 1:
                        state = "decision"
                        willingness = "engaged"
                    elif outcome == 0 and objection_count >= 2:
                        state = "drop_off_risk"
                        willingness = "disengaged"
                    else:
                        state = "evaluation"
                        willingness = "neutral"

            # Position-aware corrections
            if pos <= 0.1 and state in ("decision", "drop_off_risk"):
                state = "interest"
                willingness = "neutral"
            if pos >= 0.85 and outcome == 0 and state not in ("objection", "drop_off_risk"):
                # Failed deal, very end — likely disengaging even if text seems neutral
                willingness = "disengaged" if is_disengaged else "neutral"

        else:
            # Sales rep turns — label based on what they're responding to
            if last_was_objection:
                state = "objection"  # Still in objection phase
                willingness = "neutral"
                last_was_objection = False
            elif pos < 0.2:
                state = "trust"
                willingness = "neutral"
            elif pos < 0.5:
                state = "interest"
                willingness = "engaged"
            elif pos < 0.8:
                state = "evaluation"
                willingness = "engaged" if outcome == 1 else "neutral"
            else:
                state = "decision" if outcome == 1 else "evaluation"
                willingness = "engaged" if outcome == 1 else "neutral"

        # Style-based adjustments
        if style == "skeptical_challenging" and state == "interest" and speaker == "customer":
            # Skeptical customers asking questions are evaluating, not just interested
            if is_technical or text.strip().endswith('?'):
                state = "evaluation"
        elif style == "confused_overwhelmed" and speaker == "customer":
            # Confused customers showing concern aren't objecting, they need trust
            if state == "objection" and not is_pushback and not is_price:
                state = "trust"
                willingness = "neutral"

        labeled_turns.append({
            "text": text,
            "speaker": speaker,
            "sales_state": state,
            "willingness": willingness,
            "position": round(pos, 3),
        })

    return labeled_turns


def build_training_data(labeled_convs):
    """Build context-windowed training examples from labeled conversations."""
    state_examples = []
    will_examples = []

    for conv_turns in labeled_convs:
        num_turns = len(conv_turns)
        for i in range(num_turns):
            # Build context window (current + 2 previous turns)
            start = max(0, i - 2)
            window = conv_turns[start:i + 1]
            window_text = " ".join([f"{t['speaker']}: {t['text']}" for t in window])

            if len(window_text.strip()) < 20:
                continue

            window_text = window_text[:512]

            state_examples.append({
                "text": window_text,
                "label": conv_turns[i]["sales_state"],
                "source": "saas_intelligent",
            })
            will_examples.append({
                "text": window_text,
                "label": conv_turns[i]["willingness"],
                "source": "saas_intelligent",
            })

    return state_examples, will_examples


def main():
    print("=" * 60)
    print("INTELLIGENT LABELING: DeepMost SaaS Conversations")
    print("=" * 60)

    with open(os.path.join(DATA_DIR, "unified_conversations.json"), "r", encoding="utf-8") as f:
        convs = json.load(f)

    saas = [c for c in convs if c["source"] == "deepmost_saas"]
    print(f"SaaS conversations: {len(saas)}")
    print(f"Styles: {sorted(set(c.get('style', '?') for c in saas))}")
    print(f"Outcomes: converted={sum(1 for c in saas if c.get('outcome')==1)}, failed={sum(1 for c in saas if c.get('outcome')==0)}")

    # Label all conversations
    all_labeled = []
    for conv in saas:
        labeled = label_conversation(conv)
        all_labeled.append(labeled)

    total_turns = sum(len(c) for c in all_labeled)
    print(f"\nLabeled {total_turns} turns across {len(all_labeled)} conversations")

    # Build training data
    state_examples, will_examples = build_training_data(all_labeled)
    print(f"\nState examples: {len(state_examples)}")
    print(f"Willingness examples: {len(will_examples)}")

    # Show distributions
    from collections import Counter
    state_dist = Counter(e["label"] for e in state_examples)
    will_dist = Counter(e["label"] for e in will_examples)

    print(f"\nSales State distribution:")
    for label, count in state_dist.most_common():
        print(f"  {label:20s}: {count:6d} ({count/len(state_examples)*100:.1f}%)")

    print(f"\nWillingness distribution:")
    for label, count in will_dist.most_common():
        print(f"  {label:20s}: {count:6d} ({count/len(will_examples)*100:.1f}%)")

    # Save
    state_path = os.path.join(DATA_DIR, "saas_state_intelligent.json")
    will_path = os.path.join(DATA_DIR, "saas_willingness_intelligent.json")

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state_examples, f, ensure_ascii=False)
    with open(will_path, "w", encoding="utf-8") as f:
        json.dump(will_examples, f, ensure_ascii=False)

    print(f"\nSaved: {state_path}")
    print(f"Saved: {will_path}")

    # Show some labeled examples for verification
    print("\n" + "=" * 60)
    print("SAMPLE LABELS (verify quality)")
    print("=" * 60)

    for conv_idx in [0, 100, 500, 800]:
        conv = saas[conv_idx]
        labeled = all_labeled[conv_idx]
        print(f"\n--- Conv {conv_idx} (outcome={conv.get('outcome')}, style={conv.get('style')}) ---")
        for j, t in enumerate(labeled[:8]):
            state_str = f"[{t['sales_state']:15s}|{t['willingness']:11s}]"
            text_preview = t['text'][:80].replace('\n', ' ')
            print(f"  {state_str} {t['speaker']}: {text_preview}")


if __name__ == "__main__":
    main()
