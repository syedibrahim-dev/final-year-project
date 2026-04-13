"""
Step 1: Download and preprocess datasets for fine-tuning 3 classifiers.

Datasets used:
  - CaSiNo: 1,030 negotiation dialogues with strategy annotations
  - GoEmotions: 43,410 labeled emotion examples (28 classes)
  - Synthetic sales: hand-crafted B2B sales examples

Output files in training/data/:
  classifier1_objection.json  — objection type detection
  classifier2_handling.json   — response quality scoring
  classifier3_emotion.json    — emotion + pressure classification
"""

import sys, os, json, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datasets import load_dataset
from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)


def save_dataset(data, name):
    random.shuffle(data)
    n = len(data)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)
    splits = {"train": data[:train_end], "val": data[train_end:val_end], "test": data[val_end:]}
    path = os.path.join(DATA_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2, ensure_ascii=False)
    labels = Counter(d["label"] for d in data)
    print(f"  Saved {name}.json: {n} examples ({len(splits['train'])} train / {len(splits['val'])} val / {len(splits['test'])} test)")
    print(f"  Labels: {dict(labels)}\n")
    return splits


# ══════════════════════════════════════════════════════════════════
#  CLASSIFIER 1: Objection Type Detection
# ══════════════════════════════════════════════════════════════════

def prepare_classifier1():
    print("=" * 60)
    print("CLASSIFIER 1: Objection Type Detection")
    print("=" * 60 + "\n")

    examples = []

    # ── CaSiNo: extract annotated utterances ──
    print("  Loading CaSiNo...")
    casino = load_dataset("casino", split="train")
    print(f"  CaSiNo: {len(casino)} dialogues")

    strategy_map = {
        "uv-part": "objection_value",
        "vouch-fairness": "objection_fairness",
        "self-need": "objection_need",
        "other-need": "not_objection",
        "empathy": "not_objection",
        "small-talk": "not_objection",
        "promote-coordination": "not_objection",
        "coordination": "not_objection",
        "elicit-pref": "not_objection",
        "no-need": "not_objection",
        "non-strategic": "not_objection",
    }

    for row in casino:
        # annotations field: list of [text, strategy_string] pairs
        annotations = row.get("annotations", [])
        for ann in annotations:
            if not isinstance(ann, list) or len(ann) < 2:
                continue
            text = ann[0]
            strategies_raw = ann[1]  # e.g. "promote-coordination,elicit-pref"

            if not text or len(text.strip()) < 10:
                continue

            # Take the first strategy for the label
            strategies = [s.strip().lower() for s in strategies_raw.split(",")]
            label = None
            for s in strategies:
                if s in strategy_map:
                    label = strategy_map[s]
                    break

            if label:
                examples.append({"text": text.strip(), "label": label, "source": "casino"})

    casino_count = len(examples)
    print(f"  Extracted {casino_count} annotated utterances from CaSiNo")

    # ── Synthetic B2B sales objections ──
    print("  Adding synthetic sales objections...")
    sales_data = [
        # objection_price
        ("That's way over our budget for this quarter.", "objection_price"),
        ("We can't justify that kind of spend right now.", "objection_price"),
        ("Your competitor is offering something similar for half the price.", "objection_price"),
        ("What's the total cost of ownership including implementation?", "objection_price"),
        ("$79 a month is a bit steep for what we'd get.", "objection_price"),
        ("Can we negotiate on the pricing? We need a discount.", "objection_price"),
        ("Our budget has already been allocated for this fiscal year.", "objection_price"),
        ("How does your pricing compare to the alternatives?", "objection_price"),
        ("That's more than what our current vendor charges.", "objection_price"),
        ("We were expecting something in the $30-40 range.", "objection_price"),
        ("I need to see a clear ROI before I can justify this cost.", "objection_price"),
        ("Is there a cheaper plan for smaller teams?", "objection_price"),

        # objection_timing
        ("This isn't the right time for us to make a change.", "objection_timing"),
        ("We're in the middle of a restructuring right now.", "objection_timing"),
        ("Can we revisit this in Q3 when our budget refreshes?", "objection_timing"),
        ("We just signed a 2-year contract with another vendor.", "objection_timing"),
        ("We're too busy this quarter to evaluate anything new.", "objection_timing"),
        ("Our team doesn't have bandwidth for implementation right now.", "objection_timing"),
        ("We have bigger priorities to deal with first.", "objection_timing"),
        ("Maybe next quarter. We've got a lot on our plate.", "objection_timing"),
        ("The timing just doesn't work for us right now.", "objection_timing"),
        ("We need to get through our audit first before looking at new tools.", "objection_timing"),

        # objection_authority
        ("I'd need to run this by my CTO before we go further.", "objection_authority"),
        ("I'm not the decision maker on this kind of purchase.", "objection_authority"),
        ("Our procurement committee would need to approve this.", "objection_authority"),
        ("Let me check with my director and get back to you.", "objection_authority"),
        ("I can't commit to anything without getting sign-off from above.", "objection_authority"),
        ("My boss handles all vendor decisions. I'm just gathering info.", "objection_authority"),
        ("This kind of decision goes through our board.", "objection_authority"),
        ("I'll need to loop in our VP of IT before we can move forward.", "objection_authority"),

        # objection_need
        ("I'm not sure we actually need this. Our current setup works.", "objection_need"),
        ("How is this different from what we already have?", "objection_need"),
        ("We've survived without this so far. Why change now?", "objection_need"),
        ("What problem does this solve that we can't solve ourselves?", "objection_need"),
        ("I don't see how this applies to our specific situation.", "objection_need"),
        ("Our current solution handles this just fine.", "objection_need"),
        ("We built something in-house that does most of this.", "objection_need"),
        ("We don't really have a problem in this area.", "objection_need"),

        # objection_trust
        ("I've heard mixed reviews about your company online.", "objection_trust"),
        ("Can you provide references from companies in our industry?", "objection_trust"),
        ("The last vendor who promised easy deployment took 6 months.", "objection_trust"),
        ("What happens if this doesn't work? What's your guarantee?", "objection_trust"),
        ("How do I know your numbers are real and not marketing fluff?", "objection_trust"),
        ("Every vendor says they're the best. Why should I believe you?", "objection_trust"),
        ("We got burned by the last software migration. I'm skeptical.", "objection_trust"),
        ("Can you prove that 99.7% figure with independent verification?", "objection_trust"),

        # not_objection (positive/neutral)
        ("That sounds really promising. Tell me more.", "not_objection"),
        ("Can you walk me through the technical architecture?", "not_objection"),
        ("We've been looking for exactly this kind of solution.", "not_objection"),
        ("Let's schedule a demo for next week.", "not_objection"),
        ("How does the onboarding process work?", "not_objection"),
        ("What integrations do you offer out of the box?", "not_objection"),
        ("Thanks for explaining that. Very helpful.", "not_objection"),
        ("Our team would love to see a proof of concept.", "not_objection"),
        ("We manage about 300 certificates across AWS and Azure.", "not_objection"),
        ("Good morning! Thanks for taking the time to chat.", "not_objection"),
        ("That 99.7% renewal rate is impressive. How do you achieve that?", "not_objection"),
        ("Can you send me some documentation to review?", "not_objection"),
        ("We've had three outages this quarter from expired certs.", "not_objection"),
        ("Our IT team has been struggling with this exact problem.", "not_objection"),
        ("What kind of support do you offer post-deployment?", "not_objection"),
        ("Sure, I'm available Tuesday at 2pm for the demo.", "not_objection"),
    ]

    for text, label in sales_data:
        examples.append({"text": text, "label": label, "source": "synthetic_sales"})

    print(f"  Total: {len(examples)} examples ({casino_count} CaSiNo + {len(examples) - casino_count} synthetic)")
    save_dataset(examples, "classifier1_objection")


# ══════════════════════════════════════════════════════════════════
#  CLASSIFIER 2: Response Quality (resolved / deflected / escalated)
# ══════════════════════════════════════════════════════════════════

def prepare_classifier2():
    print("=" * 60)
    print("CLASSIFIER 2: Response Quality Scoring")
    print("=" * 60 + "\n")

    examples = []

    # ── CaSiNo: extract objection→response pairs ──
    print("  Extracting response pairs from CaSiNo...")
    casino = load_dataset("casino", split="train")

    objection_strategies = {"uv-part", "vouch-fairness", "self-need"}
    resolved_strategies = {"empathy", "promote-coordination", "other-need", "coordination"}
    deflected_strategies = {"small-talk", "elicit-pref", "no-need", "non-strategic"}
    escalated_strategies = {"uv-part"}  # responding to objection with own objection

    for row in casino:
        annotations = row.get("annotations", [])
        for i in range(1, len(annotations)):
            prev = annotations[i - 1]
            curr = annotations[i]
            if not isinstance(prev, list) or not isinstance(curr, list):
                continue
            if len(prev) < 2 or len(curr) < 2:
                continue

            prev_text, prev_strats = prev[0], prev[1].lower()
            curr_text, curr_strats = curr[0], curr[1].lower()

            prev_labels = {s.strip() for s in prev_strats.split(",")}
            curr_labels = {s.strip() for s in curr_strats.split(",")}

            # Only process if previous was an objection
            if not prev_labels & objection_strategies:
                continue

            if not prev_text or not curr_text or len(curr_text.strip()) < 10:
                continue

            if curr_labels & resolved_strategies:
                label = "resolved"
            elif curr_labels & deflected_strategies:
                label = "deflected"
            elif curr_labels & escalated_strategies:
                label = "escalated"
            else:
                continue

            examples.append({
                "text": f"Concern: {prev_text.strip()} Response: {curr_text.strip()}",
                "label": label,
                "source": "casino",
            })

    casino_pairs = len(examples)
    print(f"  Extracted {casino_pairs} response pairs from CaSiNo")

    # ── Synthetic sales response pairs ──
    print("  Adding synthetic response pairs...")
    synthetic = [
        # resolved
        ("That's too expensive.", "I understand the budget concern. Let me show you our starter plan at $29/month.", "resolved"),
        ("I need to check with my boss.", "Of course. Would it help if I prepared a summary with ROI projections?", "resolved"),
        ("We're happy with our current vendor.", "I respect that. What would need to be different for you to consider an alternative?", "resolved"),
        ("The timeline is too long.", "I hear you. We have an expedited track that cuts it to 10 days.", "resolved"),
        ("I don't see the ROI.", "Fair point. Let me show you a case study from a company your size.", "resolved"),
        ("What if it doesn't work?", "Valid concern. We offer a 60-day money-back guarantee.", "resolved"),
        ("Your competitor offered a better deal.", "I appreciate you sharing that. Can I ask what they included? I want to make sure you're comparing apples to apples.", "resolved"),
        ("I'm not convinced this is reliable enough.", "That's understandable. Let me share our uptime stats and independent audit results.", "resolved"),
        ("We tried something similar before and it failed.", "I can see why you'd be cautious. What specifically went wrong? I want to make sure we address that.", "resolved"),
        ("Our team won't want to learn a new system.", "That's a real concern. Our onboarding takes 2 hours and we assign a dedicated success manager.", "resolved"),

        # deflected
        ("That's too expensive.", "Let me tell you about our new AI features that just launched.", "deflected"),
        ("I need to check with my boss.", "Sure. Did you see our new dashboard update?", "deflected"),
        ("We're happy with our current vendor.", "A lot of people say that. Anyway, our platform has 15 features.", "deflected"),
        ("The timeline is too long.", "I can send you our brochure. Have you checked out our blog?", "deflected"),
        ("I don't see the ROI.", "Our platform is industry-leading. Let me show you the feature list.", "deflected"),
        ("What if it doesn't work?", "It will work. We have thousands of customers. Now, about pricing...", "deflected"),
        ("Your competitor offered a better deal.", "I'm sure they did. But we have more features. Let me show you.", "deflected"),
        ("We tried something similar before and it failed.", "That was probably a different product. Ours is much more advanced.", "deflected"),
        ("Our team won't want to learn a new system.", "Most teams adapt quickly. Anyway, let me tell you about our integrations.", "deflected"),
        ("I'm not convinced this is reliable enough.", "It's very reliable. Let me show you our product roadmap for next quarter.", "deflected"),

        # escalated
        ("That's too expensive.", "If you can't afford $79 a month then maybe this isn't for you.", "escalated"),
        ("I need to check with my boss.", "Can't you make decisions yourself? Should I talk to someone more senior?", "escalated"),
        ("We're happy with our current vendor.", "Your current solution is clearly outdated and you're falling behind.", "escalated"),
        ("The timeline is too long.", "Every day you wait you're losing money. You can't afford to delay.", "escalated"),
        ("I don't see the ROI.", "That's because you haven't looked at the data properly.", "escalated"),
        ("What if it doesn't work?", "It works for everyone else. The problem would be on your end.", "escalated"),
        ("Your competitor offered a better deal.", "You get what you pay for. Go with the cheap option if you want.", "escalated"),
        ("We tried something similar before and it failed.", "Well that's your problem for choosing the wrong vendor.", "escalated"),
        ("Our team won't want to learn a new system.", "If your team can't learn a simple tool maybe you need better staff.", "escalated"),
        ("I'm not convinced this is reliable enough.", "I don't understand why you can't see the obvious value here.", "escalated"),
    ]

    for concern, response, label in synthetic:
        examples.append({
            "text": f"Concern: {concern} Response: {response}",
            "label": label,
            "source": "synthetic_sales",
        })

    print(f"  Total: {len(examples)} examples ({casino_pairs} CaSiNo + {len(examples) - casino_pairs} synthetic)")
    save_dataset(examples, "classifier2_handling")


# ══════════════════════════════════════════════════════════════════
#  CLASSIFIER 3: Emotion + Pressure
# ══════════════════════════════════════════════════════════════════

def prepare_classifier3():
    print("=" * 60)
    print("CLASSIFIER 3: Emotion + Pressure Detection")
    print("=" * 60 + "\n")

    examples = []

    # ── GoEmotions: 43K labeled emotion examples ──
    print("  Loading GoEmotions (simplified)...")
    ge = load_dataset("go_emotions", "simplified", split="train")
    print(f"  GoEmotions: {len(ge)} examples")

    # GoEmotions simplified label IDs → names
    ge_labels = ge.features["labels"].feature.names
    print(f"  Labels: {ge_labels}")

    # Map GoEmotions labels to our sales-relevant categories
    emotion_map = {
        "neutral": "neutral",
        "approval": "positive", "admiration": "positive", "joy": "positive",
        "gratitude": "positive", "optimism": "positive", "love": "positive",
        "caring": "empathetic", "relief": "empathetic",
        "anger": "negative", "annoyance": "negative", "disapproval": "negative",
        "disgust": "negative", "disappointment": "negative",
        "sadness": "negative", "grief": "negative", "remorse": "negative",
        "fear": "anxious", "nervousness": "anxious", "confusion": "anxious",
        "surprise": "neutral", "curiosity": "neutral", "realization": "neutral",
        "amusement": "positive", "excitement": "positive", "pride": "positive",
        "desire": "neutral", "embarrassment": "anxious",
    }

    for row in ge:
        text = row["text"]
        label_ids = row["labels"]

        if not text or len(text.strip()) < 10 or not label_ids:
            continue

        # Take the first label
        label_name = ge_labels[label_ids[0]] if label_ids[0] < len(ge_labels) else "neutral"
        mapped = emotion_map.get(label_name, "neutral")
        examples.append({"text": text.strip(), "label": mapped, "source": "go_emotions"})

    ge_count = len(examples)
    print(f"  Mapped {ge_count} GoEmotions examples to 5 categories")

    # ── Sales pressure examples ──
    print("  Adding sales pressure examples...")
    pressure_data = [
        ("I appreciate you sharing that. What would be most helpful for you?", "consultative"),
        ("Take your time. Would you like me to send some materials to review?", "consultative"),
        ("That's a great question. Let me find the right answer for you.", "consultative"),
        ("I hear your concern. What would need to be true for this to work?", "consultative"),
        ("No rush at all. When would be a good time to reconnect?", "consultative"),
        ("Would it help if I put together a comparison document?", "consultative"),
        ("I understand. Let me know if you have any other questions.", "consultative"),
        ("That makes sense. Every team has different needs.", "consultative"),

        ("This pricing is only available until the end of the month.", "urgent"),
        ("We only have 3 spots left in the Q1 onboarding cohort.", "urgent"),
        ("I should mention our rates are going up next month.", "urgent"),
        ("The sooner you start, the sooner you'll see the savings.", "urgent"),
        ("Your competitor just signed up with us last week.", "urgent"),
        ("We have a special offer running this week only.", "urgent"),
        ("I'd hate for you to miss this window.", "urgent"),
        ("Time is really of the essence here given your audit deadline.", "urgent"),

        ("You're losing money every day you don't have this in place.", "demanding"),
        ("I don't understand why you'd want to keep doing things the old way.", "demanding"),
        ("If you can't see the value then I'm not sure what else to show you.", "demanding"),
        ("Your current approach is clearly not working.", "demanding"),
        ("At some point you need to make a decision. How much longer?", "demanding"),
        ("Every day you wait is another day your competitors get ahead.", "demanding"),
        ("Frankly if this isn't a priority then maybe we should talk to someone else.", "demanding"),
        ("You'd be foolish to pass on this opportunity.", "demanding"),
    ]

    for text, label in pressure_data:
        examples.append({"text": text, "label": label, "source": "synthetic_pressure"})

    # Balance: cap GoEmotions at 12K to not overwhelm pressure examples
    ge_items = [e for e in examples if e["source"] == "go_emotions"]
    other_items = [e for e in examples if e["source"] != "go_emotions"]
    if len(ge_items) > 12000:
        random.shuffle(ge_items)
        ge_items = ge_items[:12000]
    examples = ge_items + other_items

    print(f"  Total: {len(examples)} examples ({min(ge_count, 12000)} GoEmotions + {len(other_items)} pressure)")
    save_dataset(examples, "classifier3_emotion")


# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\nSalesForge AI — Training Data Preparation\n")
    prepare_classifier1()
    prepare_classifier2()
    prepare_classifier3()
    print("=" * 60)
    print("DONE. Next: python training/scripts/train_classifiers.py")
    print("=" * 60)
