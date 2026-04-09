"""
Fix Classifier 3: Augment pressure labels and rebalance dataset.

Problem: Only 24 pressure examples vs 12K emotion examples.
Solution: Generate ~500 pressure examples using paraphrase templates,
          then downsample emotions to create a balanced dataset.
"""

import sys, os, json, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── Expanded pressure examples (real B2B sales patterns) ──

CONSULTATIVE_EXAMPLES = [
    "I appreciate you sharing that. What would be most helpful for you?",
    "Take your time. Would you like me to send some materials to review?",
    "That's a great question. Let me find the right answer for you.",
    "I hear your concern. What would need to be true for this to work?",
    "No rush at all. When would be a good time to reconnect?",
    "Would it help if I put together a comparison document?",
    "I understand. Let me know if you have any other questions.",
    "That makes sense. Every team has different needs.",
    "I want to make sure this is the right fit for you, not just push a sale.",
    "Let me walk you through the options so you can decide what works best.",
    "I completely understand your hesitation. What information would help?",
    "There's no pressure here. I just want to help you make an informed decision.",
    "Would a trial period help you evaluate whether this works for your team?",
    "I'd rather you take the time to make the right choice than rush into something.",
    "That's a fair concern. Let me address it directly.",
    "What does your ideal timeline look like for making this kind of decision?",
    "I'm happy to loop in your technical team if that would be helpful.",
    "Would it be useful if I connected you with a customer in a similar situation?",
    "I want to understand your needs better. Can you tell me more about that?",
    "No worries at all. Let's revisit whenever you're ready.",
    "I think the best next step is whatever feels right to you.",
    "Would a case study from your industry be helpful in your evaluation?",
    "I know this is a big decision. What matters most to your team?",
    "Let me know how I can make the evaluation process easier for you.",
    "I'd love to understand what success looks like for your team.",
    "There's no commitment required at this stage. This is just exploratory.",
    "I appreciate your time today. Is there anything else I can clarify?",
    "That's an important consideration. Let me see how we can address it.",
    "I want to be transparent about what we can and can't do for you.",
    "Your feedback is valuable. What would make this a better fit?",
    "Shall I prepare a custom analysis based on what you've told me?",
    "I'd recommend taking the time to review our documentation first.",
    "It sounds like you have a clear picture of what you need. Let me align with that.",
    "I don't want to oversell this. Let me share the honest pros and cons.",
    "That's a really thoughtful approach to evaluating this.",
    "I respect that you need time to think this through.",
    "Can I ask what criteria are most important for your decision?",
    "I think the demo would answer a lot of your questions without any commitment.",
    "Let me know if there's anything I've said that doesn't add up.",
    "I'd rather lose the deal than have you sign up for something that doesn't work.",
]

URGENT_EXAMPLES = [
    "This pricing is only available until the end of the month.",
    "We only have 3 spots left in the Q1 onboarding cohort.",
    "I should mention our rates are going up next month.",
    "The sooner you start, the sooner you'll see the savings.",
    "Your competitor just signed up with us last week.",
    "We have a special offer running this week only.",
    "I'd hate for you to miss this window.",
    "Time is really of the essence given your audit deadline.",
    "This promotion expires on Friday.",
    "We can only guarantee this rate for the next 48 hours.",
    "Our implementation team is fully booked after March.",
    "I want to make sure we can get you onboarded before your compliance deadline.",
    "The beta pricing won't last much longer.",
    "Other companies in your space are already making this move.",
    "If we start now, you'll be live before your board meeting.",
    "This is the last quarter we're offering the migration support for free.",
    "The early adopter discount is ending soon.",
    "I know you mentioned the audit is in 6 weeks. We should start soon to be ready.",
    "We're closing this round of pricing next week.",
    "Your competitor just asked us about the same thing yesterday.",
    "The team that handles enterprise onboarding is booking into Q3 already.",
    "I want to flag that our pricing structure is changing in April.",
    "With your contract renewal coming up, now might be the ideal time.",
    "The longer you wait, the more expired certificates pile up.",
    "We've seen companies lose clients while they were still evaluating.",
    "I don't want to create false urgency, but the timing does matter here.",
    "Every month you delay is another month of manual tracking and risk.",
    "Our current promotion includes free data migration which normally costs extra.",
    "I've seen similar companies regret waiting when they had the chance.",
    "The window for the annual plan discount closes at month end.",
    "Given your team's bandwidth concerns, starting sooner means less pressure later.",
    "Our availability for dedicated onboarding support is limited this quarter.",
    "I noticed your contract with the other vendor expires next month.",
    "The pilot program has limited capacity and it's filling up.",
    "Starting this month means you'll have full ROI data for your Q3 board review.",
    "Other teams we've talked to in your industry are moving quickly on this.",
    "If budget is approved this quarter, we should lock in the current pricing.",
    "The compliance landscape is changing and early movers will have an advantage.",
    "I want to make sure you don't miss the enrollment deadline.",
    "This offer is contingent on signing before the fiscal year ends.",
]

DEMANDING_EXAMPLES = [
    "You're losing money every day you don't have this in place.",
    "I don't understand why you'd want to keep doing things the old way.",
    "If you can't see the value then I'm not sure what else to show you.",
    "Your current approach is clearly not working.",
    "At some point you need to make a decision. How much longer will you wait?",
    "Every day you wait is another day your competitors get ahead.",
    "Frankly if this isn't a priority then maybe we should talk to someone else.",
    "You'd be foolish to pass on this opportunity.",
    "Look, I've shown you the data. What more do you need?",
    "If you can't afford $79 a month then maybe this isn't for you.",
    "Your team is wasting hours every week on something we could automate.",
    "With all due respect, your current process is outdated.",
    "I've been doing this for 10 years. Trust me, you need this.",
    "Companies that wait too long on this end up paying double later.",
    "I'm not sure what's holding you back at this point.",
    "If price is your only concern, you're looking at this the wrong way.",
    "The fact that you're still using spreadsheets in 2026 is concerning.",
    "You should really be talking to your board about this immediately.",
    "I don't think you fully appreciate the risk you're taking by waiting.",
    "Other companies your size figured this out months ago.",
    "If you want to keep losing clients to expired certificates, that's your choice.",
    "I've given you everything you need. The ball is in your court.",
    "I think you're underestimating how much this is costing your organization.",
    "Honestly, I'm surprised this isn't already in place for a company your size.",
    "You can't put a price on security. Not having this is a liability.",
    "I'll be direct: your competitors are already using solutions like ours.",
    "If your team can't handle the transition, maybe you need different people.",
    "At what point does the risk become unacceptable to your leadership?",
    "I've laid out the case as clearly as I can. It's a no-brainer.",
    "The question isn't whether you need this. It's whether you can afford not to have it.",
    "I'm going to be honest with you: waiting is the worst option here.",
    "You're paying more for your current mess than our solution would cost.",
    "If you're not ready to make decisions, I should talk to whoever is.",
    "Every outage costs you more than a year of our service. Do the math.",
    "I've been patient, but at some point we need a yes or no.",
    "Your current vendor is clearly failing you. Why are you loyal to them?",
    "I think we both know your current setup isn't sustainable.",
    "Stop overthinking this. The ROI speaks for itself.",
    "Companies that hesitate on security investments are the ones that get breached.",
    "I don't mean to be blunt, but you're leaving money on the table.",
]

def main():
    print("Augmenting Classifier 3 pressure data...\n")

    # Load existing data
    path = os.path.join(DATA_DIR, "classifier3_emotion.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Combine all splits
    all_examples = data["train"] + data["val"] + data["test"]

    # Remove old pressure examples (only 24)
    emotion_examples = [e for e in all_examples if e["label"] not in ("consultative", "urgent", "demanding")]
    old_pressure = [e for e in all_examples if e["label"] in ("consultative", "urgent", "demanding")]
    print(f"  Existing emotion examples: {len(emotion_examples)}")
    print(f"  Old pressure examples: {len(old_pressure)}")

    # Add new augmented pressure examples
    new_pressure = []
    for text in CONSULTATIVE_EXAMPLES:
        new_pressure.append({"text": text, "label": "consultative", "source": "augmented"})
    for text in URGENT_EXAMPLES:
        new_pressure.append({"text": text, "label": "urgent", "source": "augmented"})
    for text in DEMANDING_EXAMPLES:
        new_pressure.append({"text": text, "label": "demanding", "source": "augmented"})

    print(f"  New pressure examples: {len(new_pressure)} ({len(CONSULTATIVE_EXAMPLES)} consultative, {len(URGENT_EXAMPLES)} urgent, {len(DEMANDING_EXAMPLES)} demanding)")

    # Keep ALL emotion examples, OVERSAMPLE pressure to ~10% of dataset
    # 12K emotions → need ~1.3K pressure → repeat 120 examples ~11x
    target_pressure_count = int(len(emotion_examples) * 0.10)
    oversampled_pressure = []
    while len(oversampled_pressure) < target_pressure_count:
        oversampled_pressure.extend(new_pressure)
    oversampled_pressure = oversampled_pressure[:target_pressure_count]
    random.shuffle(oversampled_pressure)

    print(f"  Oversampled pressure: {len(new_pressure)} unique → {len(oversampled_pressure)} total (repeated ~{len(oversampled_pressure)//len(new_pressure)}x)")

    combined = emotion_examples + oversampled_pressure
    random.shuffle(combined)

    # Split
    n = len(combined)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)
    splits = {
        "train": combined[:train_end],
        "val": combined[train_end:val_end],
        "test": combined[val_end:],
    }

    # Save
    with open(path, "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2, ensure_ascii=False)

    labels = Counter(d["label"] for d in combined)
    print(f"\n  New dataset: {len(combined)} total")
    print(f"  Train: {len(splits['train'])}, Val: {len(splits['val'])}, Test: {len(splits['test'])}")
    print(f"  Labels: {dict(sorted(labels.items()))}")
    print(f"\n  Pressure ratio: {sum(labels[k] for k in ('consultative','urgent','demanding'))}/{len(combined)} = {sum(labels[k] for k in ('consultative','urgent','demanding'))/len(combined)*100:.1f}%")
    print("\n  Now retrain: python training/scripts/retrain_classifier3.py")


if __name__ == "__main__":
    main()
