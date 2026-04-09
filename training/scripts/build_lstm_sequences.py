"""
Build LSTM training sequences from 1,000 SaaS conversations.

Pipeline:
1. Run all 6 classifiers on each turn (with context windows)
2. Convert classifier outputs to numerical feature vectors
3. Save as sequences with outcome labels

Each conversation becomes:
  features: [[turn1_features], [turn2_features], ...]
  outcome: 0 or 1

Per-turn features (6 dims):
  - sales_state (one-hot encoded, 6 classes)
  - willingness (one-hot encoded, 3 classes)
  - objection_type (one-hot encoded, 8 classes)
  - emotion (one-hot encoded, 8 classes)
  - position (float 0-1)
  - objection_resolved (binary — was previous objection handled?)
"""

import json, os, sys, time
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path so we can import training.inference
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Feature encoding maps
STATE_LABELS = ["decision", "drop_off_risk", "evaluation", "interest", "objection", "trust"]
WILL_LABELS = ["disengaged", "engaged", "neutral"]
OBJ_LABELS = ["not_objection", "objection_authority", "objection_need", "objection_price",
              "objection_timing", "objection_trust", "objection_value"]
EMO_LABELS = ["anxious", "consultative", "demanding", "empathetic", "negative", "neutral", "positive", "urgent"]


def encode_label(label, label_list):
    """One-hot encode a label."""
    vec = [0.0] * len(label_list)
    if label in label_list:
        vec[label_list.index(label)] = 1.0
    else:
        # Default to most common class
        vec[0] = 1.0
    return vec


def main():
    print("=" * 60)
    print("BUILDING LSTM SEQUENCES FROM SAAS CONVERSATIONS")
    print("=" * 60)

    # Load classifiers
    print("\nLoading classifiers...")
    t0 = time.time()
    from training.inference import (
        predict_objection, predict_sales_state,
        predict_willingness, predict_emotion
    )
    print(f"Classifiers loaded in {time.time()-t0:.1f}s")

    # Load SaaS conversations
    with open(os.path.join(DATA_DIR, "unified_conversations.json"), "r", encoding="utf-8") as f:
        convs = json.load(f)

    saas = [c for c in convs if c["source"] == "deepmost_saas"]
    print(f"\nProcessing {len(saas)} SaaS conversations...")

    sequences = []
    skipped = 0

    for idx, conv in enumerate(saas):
        turns = conv["turns"]
        outcome = conv.get("outcome")
        if outcome is None or len(turns) < 4:
            skipped += 1
            continue

        num_turns = len(turns)
        turn_features = []
        prev_was_objection = False

        for i, turn in enumerate(turns):
            text = turn["text"]
            speaker = turn["speaker"]
            position = i / max(1, num_turns - 1)

            # Build context window (last 3 turns)
            start = max(0, i - 2)
            window = turns[start:i + 1]
            window_text = " ".join([f"{t['speaker']}: {t['text']}" for t in window])[:512]

            # Run classifiers
            state_pred = predict_sales_state(window_text)
            will_pred = predict_willingness(window_text)
            obj_pred = predict_objection(text)
            emo_pred = predict_emotion(text)

            # Extract labels
            state_label = state_pred.get("state", "interest")
            will_label = will_pred.get("level", "neutral")
            obj_label = obj_pred.get("label", "not_objection")
            emo_label = emo_pred.get("label", "neutral")

            # Objection resolved flag
            is_objection = obj_label != "not_objection"
            obj_resolved = 0.0
            if speaker == "sales_rep" and prev_was_objection:
                obj_resolved = 1.0  # Rep responded to objection
            prev_was_objection = is_objection and speaker == "customer"

            # Build feature vector
            features = []
            features.extend(encode_label(state_label, STATE_LABELS))    # 6 dims
            features.extend(encode_label(will_label, WILL_LABELS))      # 3 dims
            features.extend(encode_label(obj_label, OBJ_LABELS))        # 7 dims
            features.extend(encode_label(emo_label, EMO_LABELS))        # 8 dims
            features.append(position)                                     # 1 dim
            features.append(obj_resolved)                                 # 1 dim
            features.append(1.0 if speaker == "customer" else 0.0)       # 1 dim (speaker)

            turn_features.append(features)

        sequences.append({
            "features": turn_features,
            "outcome": outcome,
            "num_turns": num_turns,
            "conv_id": conv.get("id", idx),
        })

        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx+1}/{len(saas)} conversations...")

    print(f"\nTotal sequences: {len(sequences)} (skipped {skipped})")
    print(f"Feature dims per turn: {len(sequences[0]['features'][0])}")  # 27
    print(f"Avg turns per conversation: {sum(s['num_turns'] for s in sequences)/len(sequences):.1f}")
    print(f"Outcomes: converted={sum(1 for s in sequences if s['outcome']==1)}, failed={sum(1 for s in sequences if s['outcome']==0)}")

    # Save
    out_path = os.path.join(DATA_DIR, "lstm_sequences.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sequences, f)

    print(f"\nSaved: {out_path}")
    print(f"Feature vector: 6(state) + 3(willingness) + 7(objection) + 8(emotion) + 1(position) + 1(resolved) + 1(speaker) = 27 dims")


if __name__ == "__main__":
    main()
