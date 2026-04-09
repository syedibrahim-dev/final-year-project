"""
Intelligent labeling of DeepMost SaaS conversations for:
- C1: Objection Type Detection (8 classes)
- C2: Response Handling Quality (3 classes)

Labels every customer turn for objection type, and every sales_rep turn
following an objection for handling quality.

This replaces CaSiNo (campsite negotiation) data with actual B2B SaaS labels.
"""

import json, os, re, sys, random
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


# ═══════════════════════════════════════
# C1: OBJECTION TYPE DETECTION
# ═══════════════════════════════════════

def classify_objection(text, prev_rep_text=""):
    """
    Classify a customer turn into one of 8 objection types.
    Uses the customer's text + what the rep just said for context.

    Returns: (label, confidence_hint)
    """
    lower = text.lower()

    # ── Price / Budget objections ──
    # Customer pushes back on cost, asks for discount, mentions budget constraints
    if re.search(r'\b(expensive|costly|cost|price|pricing|budget|afford|pay|investment|spend|\$\d|month|annual|subscription fee|roi|return on|worth the money|too much|lot of money)\b', lower):
        # Only if it's pushback, not just asking about pricing
        if re.search(r'\b(too |high|lot|can.t|won.t|hard to|difficult to|justify|concern|worry|hmm|idk|dunno|yikes|ouch|steep|whoa)\b', lower) or '?' in text:
            return "objection_price"
        # Neutral price inquiry (no pushback) = not an objection
        if re.search(r'\b(how much|what.s the (price|cost)|pricing|plan)\b', lower) and not re.search(r'\b(but|however|though|still)\b', lower):
            return "not_objection"
        return "objection_price"

    # ── Timing objections ──
    # Not ready now, need more time, too busy, bad timing
    if re.search(r'\b(not (the right |a good )?time|too (busy|soon|early)|later|next (quarter|year|month)|right now|bandwidth|capacity|plate is full|swamped|tied up|revisit|circle back|down the (road|line))\b', lower):
        return "objection_timing"

    # ── Authority objections ──
    # Need to check with someone else, not the decision maker
    if re.search(r'\b(check with|talk to|run (it |this )?by|boss|manager|team|leadership|committee|board|stakeholder|decision.?maker|buy.?in|approval|sign.?off|cto|cfo|cio|vp |director)\b', lower):
        return "objection_authority"

    # ── Need objections ──
    # Don't see the need, happy with current solution, no pain
    if re.search(r'\b(don.t (need|see|think)|no need|not (looking|interested|necessary)|happy with|satisfied with|already (have|use|using|got)|current (solution|tool|setup|system)|works (fine|well|ok)|good enough|why (would|should)|what.s wrong with)\b', lower):
        return "objection_need"

    # ── Trust / Credibility objections ──
    # Wants proof, skeptical of claims, doesn't believe promises
    if re.search(r'\b(prove|proof|evidence|case study|reference|testimonial|guarantee|promise|skeptic|doubt|trust|believe|sounds too good|really\?|are you sure|how (do i|can i) know|what if|risk|concern|worried|scary|nervous|uncertain)\b', lower):
        # Distinguish from evaluation (genuine questions) vs trust (doubt)
        if re.search(r'\b(but|hmm|idk|not sure|skeptic|doubt|really\?|sounds|what if|risk|scary|worried)\b', lower):
            return "objection_trust"
        return "not_objection"  # Just asking for info, not doubting

    # ── Value objections ──
    # Don't see enough value, features don't justify cost, competitors are better
    if re.search(r'\b(not (worth|enough|impressive|convinc)|value|benefit|advantage|justify|compared to|competitor|alternative|other (tool|solution|option|vendor)|what makes .* (different|better|special)|why (your|this) over|already tried)\b', lower):
        return "objection_value"

    # ── Fairness objections ──
    # Contract terms, lock-in, hidden fees
    if re.search(r'\b(contract|lock.?in|cancel|commitment|hidden (fee|cost|charge)|fine print|terms|conditions|penalty|refund|money back)\b', lower):
        return "objection_fairness"

    # ── Soft objections (expressed as confusion/overwhelm) ──
    # These are objections in disguise — customer is resistant but not explicit
    if re.search(r'\b(overwhelm|confus|complicated|complex|hard to|difficult|struggle|nightmare|hassle|pain|headache|mess)\b', lower):
        # If about the product/onboarding → objection_trust (they don't trust it'll be easy)
        if re.search(r'\b(your|the |this |it.s|tool|platform|software|solution|onboard|implement|migrat|integrat|learn|train)\b', lower):
            return "objection_trust"
        # If about their current situation → not an objection (they're describing pain)
        return "not_objection"

    # ── Questions ending with "?" are usually not objections ──
    if text.strip().endswith('?') and not re.search(r'\b(but|however|though|concern|worried|expensive|budget)\b', lower):
        return "not_objection"

    # ── Positive/neutral statements ──
    if re.search(r'\b(sounds (good|great|interesting|cool)|love|awesome|perfect|makes sense|got it|i see|ok|sure|yeah|yep|right|definitely|absolutely)\b', lower):
        return "not_objection"

    # Default: not an objection
    return "not_objection"


# ═══════════════════════════════════════
# C2: HANDLING QUALITY
# ═══════════════════════════════════════

def classify_handling(objection_text, response_text):
    """
    Classify how well the sales rep handled an objection.

    resolved   — acknowledges concern + provides solution/reframe
    deflected  — ignores/sidesteps the concern, pivots to something else
    escalated  — dismisses concern, gets pushy, makes it worse
    """
    obj_lower = objection_text.lower()
    resp_lower = response_text.lower()

    # ── Check for escalation signals (rare but important) ──
    if re.search(r'\b(you (should|need to|have to|must)|trust me|just (buy|sign|commit)|don.t worry about|that.s not (important|a real|a big)|you.re (wrong|missing|overthinking)|come on|seriously\?)\b', resp_lower):
        return "escalated"

    # ── Check for resolution signals ──
    resolution_signals = 0

    # Acknowledges the concern
    if re.search(r'\b(understand|get (that|it)|hear you|valid|fair (point|concern|question)|make sense|totally|absolutely|great (question|point|concern))\b', resp_lower):
        resolution_signals += 2

    # Provides a solution or reframe
    if re.search(r'\b(here.s (how|what)|the (good news|thing is|way)|actually|in fact|what (we|you) can|option|solution|approach|let me|we (offer|provide|have)|helps? (with|you|reduce|save)|designed to|built (for|to)|saves? (you|time|money)|reduce|improve|benefit)\b', resp_lower):
        resolution_signals += 2

    # Addresses the specific objection topic
    # If objection was about price and response mentions value/ROI/savings
    if re.search(r'\b(price|cost|expensive|budget)\b', obj_lower):
        if re.search(r'\b(value|roi|return|save|saving|pay for itself|investment|worth|long run|time saved|cost.effective)\b', resp_lower):
            resolution_signals += 2

    # If objection was about timing and response offers flexibility
    if re.search(r'\b(time|busy|later|not ready)\b', obj_lower):
        if re.search(r'\b(whenever|flexible|no rush|your pace|pilot|trial|start small|phase|gradual)\b', resp_lower):
            resolution_signals += 2

    # If objection about complexity and response mentions ease/support
    if re.search(r'\b(complicated|complex|hard|difficult|overwhelm)\b', obj_lower):
        if re.search(r'\b(easy|simple|intuitive|support|help|onboard|train|guide|walkthrough|step.by.step|scriptless|no.?code)\b', resp_lower):
            resolution_signals += 2

    # ── Check for deflection signals ──
    deflection_signals = 0

    # Ignores the concern and pivots to a different feature
    if resolution_signals == 0:
        deflection_signals += 1

    # Generic non-answer
    if re.search(r'\b(anyway|moving on|let me (show|tell) you about|speaking of|another thing|also|by the way|on (another|a different) note)\b', resp_lower):
        deflection_signals += 2

    # Very short response (under 50 chars) to a substantive objection
    if len(response_text.strip()) < 50 and len(objection_text.strip()) > 80:
        deflection_signals += 1

    # ── Decide ──
    if resolution_signals >= 3:
        return "resolved"
    elif resolution_signals >= 1 and deflection_signals <= 1:
        return "resolved"  # Partial resolution is still resolution
    elif deflection_signals >= 2:
        return "deflected"
    else:
        # Default: if rep responded at all with some substance, it's a partial resolution
        # Most SaaS sales reps are trained to address concerns
        if len(response_text.strip()) > 80:
            return "resolved"
        return "deflected"


def label_conversations():
    """Label all SaaS conversations for objection type and handling quality."""

    with open(os.path.join(DATA_DIR, "unified_conversations.json"), "r", encoding="utf-8") as f:
        convs = json.load(f)

    saas = [c for c in convs if c["source"] == "deepmost_saas"]
    print(f"SaaS conversations: {len(saas)}")

    objection_examples = []
    handling_examples = []

    for conv in saas:
        turns = conv["turns"]
        num_turns = len(turns)

        for i, turn in enumerate(turns):
            text = turn["text"]
            speaker = turn["speaker"]

            if speaker == "customer":
                # Get previous rep text for context
                prev_rep = ""
                if i > 0 and turns[i-1]["speaker"] == "sales_rep":
                    prev_rep = turns[i-1]["text"]

                # Classify objection type
                obj_label = classify_objection(text, prev_rep)

                # Build context window (current + 2 previous)
                start = max(0, i - 2)
                window = turns[start:i + 1]
                window_text = " ".join([f"{t['speaker']}: {t['text']}" for t in window])[:512]

                objection_examples.append({
                    "text": window_text,
                    "label": obj_label,
                    "source": "saas_intelligent",
                })

                # If it's an objection, check how the rep handled it
                if obj_label != "not_objection" and i + 1 < num_turns:
                    next_turn = turns[i + 1]
                    if next_turn["speaker"] == "sales_rep":
                        handling_label = classify_handling(text, next_turn["text"])

                        # Build handling input: "Concern: ... Response: ..."
                        combined = f"Concern: {text} Response: {next_turn['text']}"
                        handling_examples.append({
                            "text": combined[:512],
                            "label": handling_label,
                            "source": "saas_intelligent",
                        })

    return objection_examples, handling_examples


def main():
    print("=" * 60)
    print("INTELLIGENT LABELING: Objection Detection + Handling Quality")
    print("=" * 60)

    objection_examples, handling_examples = label_conversations()

    from collections import Counter

    # ── Objection stats ──
    print(f"\n--- C1: Objection Detection ---")
    print(f"Total examples: {len(objection_examples)}")
    obj_dist = Counter(e["label"] for e in objection_examples)
    for label, count in obj_dist.most_common():
        print(f"  {label:25s}: {count:6d} ({count/len(objection_examples)*100:.1f}%)")

    # ── Handling stats ──
    print(f"\n--- C2: Response Handling ---")
    print(f"Total examples: {len(handling_examples)}")
    hand_dist = Counter(e["label"] for e in handling_examples)
    for label, count in hand_dist.most_common():
        print(f"  {label:15s}: {count:6d} ({count/len(handling_examples)*100:.1f}%)")

    # Save
    obj_path = os.path.join(DATA_DIR, "saas_objection_intelligent.json")
    hand_path = os.path.join(DATA_DIR, "saas_handling_intelligent.json")

    with open(obj_path, "w", encoding="utf-8") as f:
        json.dump(objection_examples, f, ensure_ascii=False)
    with open(hand_path, "w", encoding="utf-8") as f:
        json.dump(handling_examples, f, ensure_ascii=False)

    print(f"\nSaved: {obj_path}")
    print(f"Saved: {hand_path}")

    # ── Show samples for verification ──
    print("\n" + "=" * 60)
    print("SAMPLE OBJECTION LABELS")
    print("=" * 60)

    # Show a few from each objection type
    by_type = {}
    for e in objection_examples:
        by_type.setdefault(e["label"], []).append(e)

    for label in sorted(by_type.keys()):
        examples = by_type[label]
        print(f"\n  [{label}] ({len(examples)} examples)")
        # Show up to 2 samples
        for e in random.sample(examples, min(2, len(examples))):
            # Extract just the last customer turn from window
            parts = e["text"].split("customer: ")
            last_part = parts[-1][:100] if parts else e["text"][:100]
            print(f"    -> {last_part}")

    print("\n" + "=" * 60)
    print("SAMPLE HANDLING LABELS")
    print("=" * 60)

    by_handle = {}
    for e in handling_examples:
        by_handle.setdefault(e["label"], []).append(e)

    for label in sorted(by_handle.keys()):
        examples = by_handle[label]
        print(f"\n  [{label}] ({len(examples)} examples)")
        for e in random.sample(examples, min(2, len(examples))):
            print(f"    -> {e['text'][:150]}")


if __name__ == "__main__":
    main()
