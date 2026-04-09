"""
Retrain Classifier 3 with augmented pressure data + class weights.
"""

import sys, os, json, time
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

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
BASE_MODEL = "distilbert-base-uncased"
NAME = "classifier3_emotion"


def load_splits():
    path = os.path.join(DATA_DIR, f"{NAME}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    all_labels = sorted(set(d["label"] for split in data.values() for d in split))
    label2id = {l: i for i, l in enumerate(all_labels)}
    id2label = {i: l for l, i in label2id.items()}
    splits = {}
    for split_name, items in data.items():
        texts = [d["text"] for d in items]
        labels = [label2id[d["label"]] for d in items]
        splits[split_name] = Dataset.from_dict({"text": texts, "label": labels})
    return splits, label2id, id2label


class WeightedTrainer(Trainer):
    """Trainer with class weights to handle imbalanced data."""

    def __init__(self, class_weights=None, **kwargs):
        super().__init__(**kwargs)
        if class_weights is not None:
            self.class_weights = torch.tensor(class_weights, dtype=torch.float32)
        else:
            self.class_weights = None

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        if self.class_weights is not None:
            w = self.class_weights.to(logits.device)
            loss = nn.CrossEntropyLoss(weight=w)(logits, labels)
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
    print(f"\nRetraining Classifier 3 (Emotion + Pressure) with class weights\n")

    splits, label2id, id2label = load_splits()
    num_labels = len(label2id)

    print(f"Labels ({num_labels}): {list(label2id.keys())}")
    print(f"Train: {len(splits['train'])}, Val: {len(splits['val'])}, Test: {len(splits['test'])}")

    # Compute class weights (inverse frequency)
    train_labels = splits["train"]["label"]
    counts = Counter(train_labels)
    total = len(train_labels)
    weights = [total / (num_labels * counts.get(i, 1)) for i in range(num_labels)]
    # Cap weights so rare classes don't dominate
    max_weight = 10.0
    weights = [min(w, max_weight) for w in weights]
    print(f"Class weights: {dict(zip(label2id.keys(), [round(w, 2) for w in weights]))}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)

    train_ds = splits["train"].map(tokenize, batched=True)
    val_ds = splits["val"].map(tokenize, batched=True)
    test_ds = splits["test"].map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=num_labels, id2label=id2label, label2id=label2id,
    )

    output_dir = os.path.join(MODEL_DIR, NAME)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        learning_rate=3e-5,
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

    print(f"\nTraining (8 epochs with class weights)...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"Training completed in {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # Test
    print(f"\nEvaluating on test set...")
    test_results = trainer.evaluate(test_ds)
    print(f"Test Accuracy: {test_results['eval_accuracy']:.4f}")
    print(f"Test F1:       {test_results['eval_f1']:.4f}")

    predictions = trainer.predict(test_ds)
    preds = np.argmax(predictions.predictions, axis=-1)
    labels = predictions.label_ids
    present_labels = sorted(set(labels) | set(preds))
    present_names = [id2label[i] for i in present_labels]
    report = classification_report(labels, preds, labels=present_labels, target_names=present_names, zero_division=0)
    print(f"\nClassification Report:\n{report}")

    # Save
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    with open(os.path.join(output_dir, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": {str(k): v for k, v in id2label.items()}}, f, indent=2)

    print(f"Model saved to: {output_dir}/")


if __name__ == "__main__":
    main()
