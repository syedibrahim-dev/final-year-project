"""
STEP 5 (v2): Willingness Predictor from DeepMost SaaS Data

Instead of translating Japanese SalesTalk, we build willingness labels
from DeepMost SaaS conversations which have:
  - customer_engagement (0-1): proxy for willingness to continue
  - conversation_style: proxy for information sharing willingness
  - outcome (0/1): proxy for goal acceptance
  - actual conversation text: in English, sales domain

Labels (3 classes for simplicity + accuracy):
  engaged     — high engagement, positive outcome signals
  neutral     — moderate engagement, undecided
  disengaged  — low engagement, negative outcome signals

We classify conversation WINDOWS (last 3 turns) — same approach as Sales State Model.
This runs alongside the EQ Agent to provide a willingness signal to the Adaptive Agent.
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


# Engagement keywords
ENGAGED_PATTERNS = [
    r"\b(interested|tell me more|sounds good|great|perfect|love|exciting)\b",
    r"\b(when can|how soon|schedule|demo|trial|sign up|get started)\b",
    r"\b(how much|pricing|cost|plan|package)\b",  # asking about pricing = engaged
    r"\?\s*$",  # asking questions = engaged
]

DISENGAGED_PATTERNS = [
    r"\b(not interested|no thanks|pass|don.t need|too busy)\b",
    r"\b(send me an email|think about it|get back to you|maybe later)\b",
    r"\b(not the right time|not looking|already have|happy with)\b",
    r"\b(got to go|wrap up|end this|no more time)\b",
]


def classify_willingness(text, engagement, outcome, position_ratio):
    """Classify a conversation window's willingness level."""
    lower = text.lower()

    engaged_score = sum(1 for p in ENGAGED_PATTERNS if re.search(p, lower))
    disengaged_score = sum(1 for p in DISENGAGED_PATTERNS if re.search(p, lower))

    # Combine text signals with metadata
    if engagement is not None:
        if engagement >= 0.7:
            engaged_score += 2
        elif engagement <= 0.3:
            disengaged_score += 2

    # Outcome signal (stronger at end of conversation)
    if outcome is not None and position_ratio > 0.6:
        if outcome == 1:
            engaged_score += 2
        else:
            disengaged_score += 1

    # Classify
    if disengaged_score >= 2 and disengaged_score > engaged_score:
        return "disengaged"
    elif engaged_score >= 2 and engaged_score > disengaged_score:
        return "engaged"
    else:
        return "neutral"


def build_willingness_data():
    """Build training data from unified conversations."""
    with open(os.path.join(DATA_DIR, "unified_conversations.json"), "r", encoding="utf-8") as f:
        conversations = json.load(f)

    examples = []
    window_size = 3

    for conv in conversations:
        turns = conv["turns"]
        outcome = conv.get("outcome")
        source = conv["source"]

        # Only use sources with engagement signals
        engagement = None
        if source == "deepmost_saas":
            # DeepMost has explicit engagement scores in the raw data
            engagement = None  # We'll infer from text

        if len(turns) < 3:
            continue

        num_turns = len(turns)

        for i in range(0, num_turns, 2):
            end = min(i + window_size, num_turns)
            window = turns[i:end]

            window_text = " ".join([f"{t['speaker']}: {t['text']}" for t in window])
            if len(window_text.strip()) < 30:
                continue

            window_text = window_text[:512]
            position_ratio = round(i / max(1, num_turns - 1), 2)

            label = classify_willingness(window_text, engagement, outcome, position_ratio)
            examples.append({
                "text": window_text,
                "label": label,
                "source": source,
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
    print("STEP 5 (v2): Willingness Predictor from English Data")
    print("=" * 60 + "\n")

    # Load pre-built data (from rebuild_all_with_context.py)
    prebuilt_path = os.path.join(DATA_DIR, "willingness_training.json")
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
        all_examples = build_willingness_data()
        random.shuffle(all_examples)
        MAX = 15000
        if len(all_examples) > MAX:
            all_examples = all_examples[:MAX]
        n = len(all_examples)
        train_examples = all_examples[:int(n*0.8)]
        val_examples = all_examples[int(n*0.8):int(n*0.9)]
        test_examples = all_examples[int(n*0.9):]

    labels = Counter(e["label"] for e in all_examples)
    print(f"Label distribution:")
    for label, count in labels.most_common():
        print(f"  {label:15s}: {count:6d} ({count / len(all_examples) * 100:.1f}%)")

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

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=256)

    train_ds = train_ds.map(tokenize, batched=True)
    val_ds = val_ds.map(tokenize, batched=True)
    test_ds = test_ds.map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=num_labels, id2label=id2label, label2id=label2id,
    )

    output_dir = os.path.join(MODEL_DIR, "willingness_predictor")

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
    print(f"Predicts buyer willingness (engaged/neutral/disengaged) from conversation windows.")


if __name__ == "__main__":
    main()
