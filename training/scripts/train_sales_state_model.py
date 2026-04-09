"""
STEP 4: Train Sales State Model

7-class classifier that models granular buyer states throughout a conversation.
Goes beyond simple 5-stage tracking (opening/discovery/presentation/objection/closing)
to capture nuanced buyer psychology.

States:
  interest       — buyer showing curiosity, asking questions
  trust          — rapport building, empathy, positive signals
  objection      — pushback, concerns, resistance
  evaluation     — comparing options, asking for details/specs
  comparison     — explicitly referencing competitors or alternatives
  decision       — commitment signals, next steps, scheduling
  drop_off_risk  — disengagement, brush-offs, losing interest

Data sources:
  - DeepMost SaaS: conversation_style + outcome → state mapping
  - CaSiNo: negotiation strategy annotations → state mapping
  - CraigslistBargains: deal progression patterns → state mapping
  - goendalf666 + gwenshap: keyword-based state inference
  - SalesBot: sales recommendation flow → state mapping

Model: DistilBERT on conversation windows (last 3 turns → state prediction)
"""

import sys, os, json, re, time, random
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import torch
from torch import nn
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import accuracy_score, f1_score, classification_report
from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
BASE_MODEL = "distilbert-base-uncased"

# ── State detection patterns ──
STATE_PATTERNS = {
    "interest": [
        r"\b(interesting|tell me more|curious|how does|can you explain|walk me through)\b",
        r"\b(sounds good|that.s cool|intriguing|want to learn|know more)\b",
        r"\?\s*$",  # ends with a question
    ],
    "trust": [
        r"\b(appreciate|thank|glad|nice to|pleasure|understand|hear you|makes sense)\b",
        r"\b(honest|transparent|respect|trust|fair|open|genuine)\b",
    ],
    "objection": [
        r"\b(expensive|costly|budget|afford|too much|price|discount)\b",
        r"\b(not sure|concerned|worried|skeptic|doubt|hesitant|risky)\b",
        r"\b(competitor|alternative|already have|current solution|switch)\b",
        r"\b(not ready|too soon|not the right time|busy|bandwidth)\b",
        r"\b(check with|boss|manager|approval|committee)\b",
    ],
    "evaluation": [
        r"\b(how does it work|integrate|compatible|feature|spec|technical)\b",
        r"\b(case study|reference|example|proof|evidence|data)\b",
        r"\b(compare|versus|difference|better than|advantage)\b",
        r"\b(security|compliance|soc|iso|gdpr|hipaa)\b",
    ],
    "comparison": [
        r"\b(competitor|vendor|alternative|other option|already using)\b",
        r"\b(compared to|better than|worse than|different from)\b",
        r"\b(their product|other solution|current provider|existing)\b",
    ],
    "decision": [
        r"\b(next step|move forward|get started|sign up|demo|trial|pilot)\b",
        r"\b(schedule|meeting|call back|follow up|proposal|quote)\b",
        r"\b(ready to|let.s do|sounds like a plan|deal|agree)\b",
        r"\b(send me|email me|put together|timeline)\b",
    ],
    "drop_off_risk": [
        r"\b(not interested|no thanks|pass|don.t need|good bye)\b",
        r"\b(send me an email|think about it|get back to you|maybe later)\b",
        r"\b(too busy|wrong time|not looking|happy with what we have)\b",
        r"\b(end this|wrap up|got to go|running out of time)\b",
    ],
}


def classify_state(text, position_ratio=0.5, outcome=None):
    """
    Classify a conversation window's state using patterns + position heuristics.
    position_ratio: 0.0 = start of conversation, 1.0 = end
    """
    lower = text.lower()
    scores = {}

    for state, patterns in STATE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, lower))
        scores[state] = score

    # Position-based boosting
    if position_ratio < 0.2:
        scores["interest"] += 2
        scores["trust"] += 1
    elif position_ratio > 0.8:
        scores["decision"] += 2
        if outcome == 0:
            scores["drop_off_risk"] += 3
        elif outcome == 1:
            scores["decision"] += 2

    # Outcome-based boosting for clear cases
    if outcome == 0 and position_ratio > 0.6:
        scores["objection"] += 1
        scores["drop_off_risk"] += 1
    elif outcome == 1 and position_ratio > 0.6:
        scores["decision"] += 1

    # Pick highest scoring state
    best_state = max(scores, key=scores.get)
    best_score = scores[best_state]

    # Minimum threshold — if nothing matched, use position heuristic
    if best_score == 0:
        if position_ratio < 0.15:
            return "trust"
        elif position_ratio < 0.35:
            return "interest"
        elif position_ratio < 0.6:
            return "evaluation"
        elif position_ratio < 0.8:
            return "objection" if outcome == 0 else "evaluation"
        else:
            return "decision" if outcome == 1 else "drop_off_risk"

    return best_state


def build_state_data():
    """Build training data for the Sales State Model from unified conversations."""
    with open(os.path.join(DATA_DIR, "unified_conversations.json"), "r", encoding="utf-8") as f:
        conversations = json.load(f)

    examples = []
    window_size = 3  # Use last 3 turns as context

    for conv in conversations:
        turns = conv["turns"]
        outcome = conv.get("outcome")
        source = conv["source"]

        if len(turns) < 3:
            continue

        num_turns = len(turns)

        # Slide a window across the conversation
        for i in range(0, num_turns, 2):  # every other turn to avoid too many examples
            end = min(i + window_size, num_turns)
            window = turns[i:end]

            # Build window text
            window_text = " ".join([f"{t['speaker']}: {t['text']}" for t in window])
            if len(window_text.strip()) < 30:
                continue

            # Truncate to fit model
            window_text = window_text[:512]

            # Position in conversation
            position_ratio = round(i / max(1, num_turns - 1), 2)

            # Classify state
            state = classify_state(window_text, position_ratio, outcome)

            examples.append({
                "text": window_text,
                "label": state,
                "source": source,
                "position": position_ratio,
            })

    return examples


class WeightedTrainer(Trainer):
    def __init__(self, class_weights=None, **kwargs):
        super().__init__(**kwargs)
        self.class_weights = torch.tensor(class_weights, dtype=torch.float32) if class_weights else None

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        if self.class_weights is not None:
            loss = nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))(logits, labels)
        else:
            loss = nn.CrossEntropyLoss()(logits, labels)
        return (loss, outputs) if return_outputs else loss


def compute_metrics(pred):
    labels = pred.label_ids
    preds = np.argmax(pred.predictions, axis=-1)
    return {
        "accuracy": round(accuracy_score(labels, preds), 4),
        "f1": round(f1_score(labels, preds, average="weighted"), 4),
    }


def main():
    print("=" * 60)
    print("STEP 4: Training Sales State Model")
    print("=" * 60 + "\n")

    # Load pre-built data (from rebuild_all_with_context.py)
    prebuilt_path = os.path.join(DATA_DIR, "sales_state_training.json")
    if os.path.exists(prebuilt_path):
        print(f"Loading pre-built data from {prebuilt_path}")
        with open(prebuilt_path, "r", encoding="utf-8") as f:
            splits = json.load(f)
        train_examples = splits["train"]
        val_examples = splits["val"]
        test_examples = splits["test"]
        all_examples = train_examples + val_examples + test_examples
        print(f"Total: {len(all_examples)} (train={len(train_examples)}, val={len(val_examples)}, test={len(test_examples)})")
    else:
        print("No pre-built data found, building from scratch...")
        all_examples = build_state_data()
        random.shuffle(all_examples)
        MAX_EXAMPLES = 20000
        if len(all_examples) > MAX_EXAMPLES:
            all_examples = all_examples[:MAX_EXAMPLES]
        n = len(all_examples)
        train_examples = all_examples[:int(n*0.8)]
        val_examples = all_examples[int(n*0.8):int(n*0.9)]
        test_examples = all_examples[int(n*0.9):]

    labels = Counter(e["label"] for e in all_examples)
    print(f"State distribution:")
    for state, count in labels.most_common():
        print(f"  {state:20s}: {count:6d} ({count/len(all_examples)*100:.1f}%)")

    sources = Counter(e["source"] for e in all_examples)
    print(f"\nSources:")
    for src, count in sources.most_common():
        print(f"  {src:25s}: {count}")

    all_labels = sorted(set(e["label"] for e in all_examples))
    label2id = {l: i for i, l in enumerate(all_labels)}
    id2label = {i: l for l, i in label2id.items()}
    num_labels = len(label2id)

    print(f"\nLabels ({num_labels}): {all_labels}")

    train_ds = Dataset.from_dict({
        "text": [e["text"] for e in train_examples],
        "label": [label2id[e["label"]] for e in train_examples],
    })
    val_ds = Dataset.from_dict({
        "text": [e["text"] for e in val_examples],
        "label": [label2id[e["label"]] for e in val_examples],
    })
    test_ds = Dataset.from_dict({
        "text": [e["text"] for e in test_examples],
        "label": [label2id[e["label"]] for e in test_examples],
    })

    print(f"Train: {len(train_ds)}, Val: {len(val_ds)}, Test: {len(test_ds)}")

    # Tokenize
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=256)

    train_ds = train_ds.map(tokenize, batched=True)
    val_ds = val_ds.map(tokenize, batched=True)
    test_ds = test_ds.map(tokenize, batched=True)

    # Model
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=num_labels, id2label=id2label, label2id=label2id,
    )

    output_dir = os.path.join(MODEL_DIR, "sales_state_model")

    # Class weights
    train_labels = [label2id[e["label"]] for e in train_examples]
    counts = Counter(train_labels)
    total = len(train_labels)
    weights = [min(10.0, total / (num_labels * counts.get(i, 1))) for i in range(num_labels)]
    print(f"Class weights: {[round(w, 2) for w in weights]}")

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        report_to="none",
        fp16=False,
        use_cpu=True,
    )

    trainer = WeightedTrainer(
        class_weights=weights,
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    print(f"\nTraining (3 epochs)...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"Training: {elapsed:.0f}s ({elapsed / 60:.1f} min)")

    # Test
    print(f"\nEvaluating on test set...")
    test_results = trainer.evaluate(test_ds)
    print(f"Test Accuracy: {test_results['eval_accuracy']:.4f}")
    print(f"Test F1:       {test_results['eval_f1']:.4f}")

    # Detailed report
    predictions = trainer.predict(test_ds)
    preds = np.argmax(predictions.predictions, axis=-1)
    labels_arr = predictions.label_ids
    present = sorted(set(labels_arr) | set(preds))
    names = [id2label[i] for i in present]
    report = classification_report(labels_arr, preds, labels=present, target_names=names, zero_division=0)
    print(f"\n{report}")

    # Save
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    with open(os.path.join(output_dir, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": {str(k): v for k, v in id2label.items()}}, f, indent=2)

    print(f"\nModel saved to: {output_dir}/")
    print(f"\nThis model tracks 7 buyer states throughout the conversation.")
    print(f"Replaces simple 5-stage tracking with granular buyer psychology.")


if __name__ == "__main__":
    main()
