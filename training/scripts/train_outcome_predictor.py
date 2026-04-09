"""
STEP 3: Train Conversation-Level Outcome Predictor

Binary classifier: Will this deal close? (0 = failed, 1 = converted)

Data: DeepMost SaaS conversations (1,000 with outcome labels)
      + CraigslistBargains (infer outcome from deal/no-deal language)

Model: DistilBERT fine-tuned on full conversation text → binary prediction
This replaces the shaky SalesRLAgent PPO with a clean, trained model.
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
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
BASE_MODEL = "distilbert-base-uncased"


def load_outcome_data():
    """
    Build training data for outcome prediction.
    Uses DeepMost SaaS (explicit labels) + CraigslistBargains (inferred).
    """
    with open(os.path.join(DATA_DIR, "unified_conversations.json"), "r", encoding="utf-8") as f:
        conversations = json.load(f)

    examples = []

    for conv in conversations:
        source = conv["source"]
        turns = conv["turns"]
        outcome = conv.get("outcome")

        # Build conversation text (last N turns to fit in 512 tokens)
        recent_turns = turns[-10:]  # last 10 turns
        conv_text = " ".join([f"{t['speaker']}: {t['text']}" for t in recent_turns])

        if not conv_text or len(conv_text.strip()) < 50:
            continue

        # ── DeepMost SaaS: explicit outcome labels ──
        if source == "deepmost_saas" and outcome is not None:
            examples.append({"text": conv_text[:512], "label": int(outcome), "source": source})

        # ── CraigslistBargains: infer outcome from final turns ──
        elif source == "craigslist_bargains":
            last_texts = " ".join([t["text"].lower() for t in turns[-3:]])
            if any(w in last_texts for w in ["deal", "accept", "agree", "sold", "sounds good", "great", "perfect"]):
                examples.append({"text": conv_text[:512], "label": 1, "source": source})
            elif any(w in last_texts for w in ["no deal", "reject", "walk away", "pass", "not interested", "too high", "no thanks"]):
                examples.append({"text": conv_text[:512], "label": 0, "source": source})
            # Skip ambiguous conversations

        # ── goendalf666: infer from conversation ending ──
        elif source == "goendalf_sales":
            last_texts = " ".join([t["text"].lower() for t in turns[-2:]])
            if any(w in last_texts for w in ["purchase", "buy", "sign up", "get started", "proceed", "order", "deal"]):
                examples.append({"text": conv_text[:512], "label": 1, "source": source})
            elif any(w in last_texts for w in ["not interested", "no thanks", "pass", "think about", "get back to you", "not right now"]):
                examples.append({"text": conv_text[:512], "label": 0, "source": source})

    return examples


def compute_metrics(pred):
    labels = pred.label_ids
    preds = np.argmax(pred.predictions, axis=-1)
    return {
        "accuracy": round(accuracy_score(labels, preds), 4),
        "f1": round(f1_score(labels, preds, average="binary"), 4),
    }


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


def main():
    print("=" * 60)
    print("STEP 3: Training Outcome Predictor")
    print("=" * 60 + "\n")

    # Load data
    examples = load_outcome_data()
    print(f"Total examples: {len(examples)}")
    print(f"Labels: {Counter(e['label'] for e in examples)}")
    print(f"Sources: {Counter(e['source'] for e in examples)}")

    # Split
    random.shuffle(examples)
    n = len(examples)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)

    label2id = {"failed": 0, "converted": 1}
    id2label = {0: "failed", 1: "converted"}

    train_ds = Dataset.from_dict({
        "text": [e["text"] for e in examples[:train_end]],
        "label": [e["label"] for e in examples[:train_end]],
    })
    val_ds = Dataset.from_dict({
        "text": [e["text"] for e in examples[train_end:val_end]],
        "label": [e["label"] for e in examples[train_end:val_end]],
    })
    test_ds = Dataset.from_dict({
        "text": [e["text"] for e in examples[val_end:]],
        "label": [e["label"] for e in examples[val_end:]],
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
        BASE_MODEL, num_labels=2, id2label=id2label, label2id=label2id,
    )

    output_dir = os.path.join(MODEL_DIR, "outcome_predictor")

    # Class weights
    train_labels = [e["label"] for e in examples[:train_end]]
    counts = Counter(train_labels)
    total = len(train_labels)
    weights = [total / (2 * counts.get(i, 1)) for i in range(2)]
    print(f"Class weights: failed={weights[0]:.2f}, converted={weights[1]:.2f}")

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=25,
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

    print(f"\nTraining (5 epochs)...")
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
    labels = predictions.label_ids

    report = classification_report(labels, preds, target_names=["failed", "converted"], zero_division=0)
    print(f"\n{report}")

    cm = confusion_matrix(labels, preds)
    print(f"Confusion Matrix:")
    print(f"  {'':15s} Pred:Failed  Pred:Converted")
    print(f"  Actual:Failed    {cm[0][0]:5d}         {cm[0][1]:5d}")
    print(f"  Actual:Converted {cm[1][0]:5d}         {cm[1][1]:5d}")

    # Save
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    with open(os.path.join(output_dir, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f, indent=2)

    print(f"\nModel saved to: {output_dir}/")
    print(f"\nThis model replaces the SalesRLAgent for conversion prediction.")
    print(f"Runs at <50ms on CPU. No PPO, no embeddings, no Ollama dependency.")


if __name__ == "__main__":
    main()
