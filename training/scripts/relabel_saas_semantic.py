"""
Relabel DeepMost SaaS utterances using semantic rules instead of keyword matching.

Problem: Previous keyword-based labeling assigned wrong labels:
  - "I understand your concern about pricing" → "neutral" (should be "empathetic")
  - "Can you tell me more?" → "neutral" (should be "interest" state)
  - "Send me an email, I'll think about it" → "neutral" (should be "disengaged")

Fix: Use multi-signal rules that combine keywords + sentence structure + context
to produce labels closer to what a frontier model would assign.
"""
import sys, os, json, re, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter
random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def classify_emotion_semantic(text, speaker):
    """Semantic emotion classification — goes beyond keywords to sentence meaning."""
    lower = text.lower().strip()

    # === EMPATHETIC signals (acknowledgment + understanding + follow-up) ===
    empathy_strong = [
        r'\bi (understand|hear you|appreciate|get that|see what you mean)',
        r'\bthat (makes sense|must be|sounds|is a real)',
        r'\b(valid|fair) (point|concern|question)',
        r'\bthank you for (sharing|being|telling|explaining)',
    ]
    empathy_moderate = [
        r'\b(absolutely|of course|certainly|definitely)',
        r'\b(help you|work with you|find.*solution)',
        r'\b(no rush|take your time|no pressure|whenever)',
    ]

    # === NEGATIVE signals (frustration + dismissal + anger) ===
    negative_strong = [
        r'\b(frustrated|annoyed|angry|furious|upset|terrible|horrible|awful)',
        r'\b(waste of|don.t care|ridiculous|unacceptable|outrageous)',
        r'\b(we.re done|goodbye|don.t call|stop calling)',
    ]
    negative_moderate = [
        r'\b(not (happy|satisfied|impressed|convinced)|disappointed)',
        r'\b(concerned|worried|skeptical|doubtful|hesitant)',
        r'\b(burned|bad experience|failed|broken|mess|nightmare|headache)',
    ]

    # === POSITIVE signals (enthusiasm + agreement + commitment) ===
    positive_strong = [
        r'\b(love|perfect|excellent|amazing|exactly what|this is great)',
        r'\b(let.s (do|go|schedule|set up|get started|move forward))',
        r'\b(sign (me|us) up|ready to|excited about|looking forward)',
    ]
    positive_moderate = [
        r'\b(sounds (good|great|interesting|promising|reasonable))',
        r'\b(that.s (helpful|useful|good to know|reassuring))',
        r'\b(makes sense|fair enough|I can see|good point)',
    ]

    # === ANXIOUS signals (uncertainty + overwhelm + fear) ===
    anxious_patterns = [
        r'\b(overwhelmed|confused|lost|don.t (know|understand)|not sure)',
        r'\b(scary|risky|dangerous|what if|worried about)',
        r'\b(too (complicated|complex|much|many|fast))',
        r'\b(pressure|deadline|audit|compliance|risk)',
    ]

    # Score each emotion
    scores = {"empathetic": 0, "negative": 0, "positive": 0, "anxious": 0, "neutral": 0}

    for p in empathy_strong:
        if re.search(p, lower): scores["empathetic"] += 3
    for p in empathy_moderate:
        if re.search(p, lower): scores["empathetic"] += 1

    for p in negative_strong:
        if re.search(p, lower): scores["negative"] += 3
    for p in negative_moderate:
        if re.search(p, lower): scores["negative"] += 1

    for p in positive_strong:
        if re.search(p, lower): scores["positive"] += 3
    for p in positive_moderate:
        if re.search(p, lower): scores["positive"] += 1

    for p in anxious_patterns:
        if re.search(p, lower): scores["anxious"] += 2

    # Speaker-based adjustment
    if speaker == "sales_rep":
        # Sales reps who ask questions are being consultative/empathetic
        if "?" in text and scores["empathetic"] == 0:
            scores["empathetic"] += 1

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "neutral"
    return best


def classify_state_semantic(text, speaker, position_ratio, outcome):
    """Semantic sales state classification."""
    lower = text.lower().strip()

    # Strong signals
    if any(re.search(p, lower) for p in [
        r'\b(schedule|demo|trial|next step|move forward|get started|sign up|proposal|quote)',
        r'\b(send (me|us)|put together|let.s (do|set|plan))',
    ]):
        return "decision"

    if any(re.search(p, lower) for p in [
        r'\b(not interested|no thanks|we.re done|goodbye|don.t call|pass)',
        r'\b(too busy|wrong time|send me an email.*think)',
    ]):
        return "drop_off_risk"

    if any(re.search(p, lower) for p in [
        r'\b(competitor|venafi|digicert|datadog|already (using|have)|current (vendor|solution|provider))',
        r'\b(compared to|versus|better than|different from|why.*switch)',
    ]):
        return "comparison"

    if any(re.search(p, lower) for p in [
        r'\b(expensive|costly|budget|afford|price|discount|too much|can.t justify)',
        r'\b(not (sure|convinced|ready)|concerned|worried|skeptic)',
        r'\b(check with|boss|manager|approval|committee|authority)',
        r'\b(not the right time|too (soon|long|complicated))',
    ]):
        return "objection"

    if any(re.search(p, lower) for p in [
        r'\b(how does|integrate|feature|spec|technical|api|security|compliance)',
        r'\b(case study|reference|example|proof|data|numbers|breakdown)',
        r'\b(what.s included|total cost|roi|compare)',
    ]):
        return "evaluation"

    if any(re.search(p, lower) for p in [
        r'\b(appreciate|thank|understand|hear you|trust|fair|honest|transparent)',
        r'\b(glad|nice to|pleasure|good to)',
    ]):
        return "trust"

    # Default by position
    if position_ratio < 0.3:
        return "interest"
    elif position_ratio < 0.6:
        return "evaluation"
    elif outcome == 1:
        return "decision"
    else:
        return "objection"


def classify_willingness_semantic(text, speaker, position_ratio, outcome):
    """Semantic willingness classification."""
    lower = text.lower().strip()

    engaged_signals = [
        r'\b(tell me more|interested|sounds (good|great|interesting)|how (does|do|much|long))',
        r'\b(schedule|demo|trial|show me|walk me through|let.s)',
        r'\b(perfect|exactly|great|love|excited)',
        r'\?\s*$',  # asking questions = engaged
    ]

    disengaged_signals = [
        r'\b(not interested|no thanks|pass|we.re done|goodbye|don.t call)',
        r'\b(send me an email|think about it|get back to you|maybe later)',
        r'\b(too busy|wrong time|not looking|happy with what)',
        r'\b(can.t commit|no commitment|not ready|not now)',
    ]

    eng = sum(1 for p in engaged_signals if re.search(p, lower))
    dis = sum(1 for p in disengaged_signals if re.search(p, lower))

    if dis >= 2 or (dis >= 1 and eng == 0):
        return "disengaged"
    if eng >= 2 or (eng >= 1 and dis == 0 and "?" in text):
        return "engaged"

    # Context signals
    if outcome == 1 and position_ratio > 0.5:
        return "engaged"
    if outcome == 0 and position_ratio > 0.7:
        return "disengaged"

    return "neutral"


def main():
    print("Relabeling SaaS data with semantic rules...\n")

    # Load raw SaaS data
    with open(os.path.join(DATA_DIR, "saas_raw_1000.json"), "r", encoding="utf-8") as f:
        saas_raw = json.load(f)

    emotion_examples = []
    state_examples = []
    willingness_examples = []

    for row in saas_raw:
        conv = row.get("conversation", "")
        outcome = row.get("outcome")
        if isinstance(conv, str):
            try: conv = json.loads(conv)
            except: continue
        if not isinstance(conv, list) or len(conv) < 2:
            continue

        num_turns = len(conv)

        for i, turn in enumerate(conv):
            text = turn.get("message", "").strip()
            speaker = turn.get("speaker", "")
            if not text or len(text) < 10:
                continue

            position_ratio = i / max(1, num_turns - 1)

            # Semantic labels
            emotion = classify_emotion_semantic(text, speaker)
            state = classify_state_semantic(text, speaker, position_ratio, outcome)
            willingness = classify_willingness_semantic(text, speaker, position_ratio, outcome)

            emotion_examples.append({"text": text, "label": emotion, "source": "saas_semantic"})
            state_examples.append({"text": text, "label": state, "source": "saas_semantic"})
            willingness_examples.append({"text": text, "label": willingness, "source": "saas_semantic"})

    print(f"Relabeled {len(emotion_examples)} SaaS utterances")
    print(f"\nEmotion labels:     {dict(Counter(e['label'] for e in emotion_examples).most_common())}")
    print(f"State labels:       {dict(Counter(e['label'] for e in state_examples).most_common())}")
    print(f"Willingness labels: {dict(Counter(e['label'] for e in willingness_examples).most_common())}")

    # Save for use in retraining
    output = {
        "emotion": emotion_examples,
        "state": state_examples,
        "willingness": willingness_examples,
    }
    path = os.path.join(DATA_DIR, "saas_relabeled_semantic.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
