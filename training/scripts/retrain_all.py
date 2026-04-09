"""
Retrain all 3 classifiers with combined CaSiNo + GoEmotions + SaaS sales data.
Uses class weights for imbalanced labels.
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


def load_splits(name):
    path = os.path.join(DATA_DIR, f"{name}.json")
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


def train_one(name, epochs, batch_size, lr, use_weights=False):
    print(f"\n{'='*60}")
    print(f"  TRAINING: {name}")
    print(f"{'='*60}\n")

    splits, label2id, id2label = load_splits(name)
    num_labels = len(label2id)

    print(f"  Labels ({num_labels}): {list(label2id.keys())}")
    for split_name, ds in splits.items():
        print(f"  {split_name}: {len(ds)}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)

    train_ds = splits["train"].map(tokenize, batched=True)
    val_ds = splits["val"].map(tokenize, batched=True)
    test_ds = splits["test"].map(tokenize, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=num_labels, id2label=id2label, label2id=label2id,
    )

    output_dir = os.path.join(MODEL_DIR, name)

    # Class weights
    weights = None
    if use_weights:
        train_labels = train_ds["label"]
        counts = Counter(train_labels)
        total = len(train_labels)
        weights = [min(10.0, total / (num_labels * counts.get(i, 1))) for i in range(num_labels)]
        print(f"  Class weights: {[round(w, 2) for w in weights]}")

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
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

    TrainerClass = WeightedTrainer if use_weights else Trainer
    trainer_kwargs = {"class_weights": weights} if use_weights else {}

    trainer = TrainerClass(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        **trainer_kwargs,
    )

    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"\n  Training: {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # Test
    test_results = trainer.evaluate(test_ds)
    print(f"  Test Accuracy: {test_results['eval_accuracy']:.4f}")
    print(f"  Test F1:       {test_results['eval_f1']:.4f}")

    predictions = trainer.predict(test_ds)
    preds = np.argmax(predictions.predictions, axis=-1)
    labels = predictions.label_ids
    present = sorted(set(labels) | set(preds))
    names = [id2label[i] for i in present]
    report = classification_report(labels, preds, labels=present, target_names=names, zero_division=0)
    print(f"\n{report}")

    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    with open(os.path.join(output_dir, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": {str(k): v for k, v in id2label.items()}}, f, indent=2)

    return test_results


if __name__ == "__main__":
    print("\nSalesForge AI — Retrain All Classifiers (CaSiNo + GoEmotions + SaaS)\n")

    results = {}

    # Classifier 1: 10,610 examples, 3 epochs (more data = fewer epochs needed)
    results["c1"] = train_one("classifier1_objection", epochs=3, batch_size=16, lr=2e-5, use_weights=True)

    # Classifier 2: 2,858 examples, 5 epochs
    results["c2"] = train_one("classifier2_handling", epochs=5, batch_size=8, lr=3e-5, use_weights=True)

    # Classifier 3: 31,654 examples, 2 epochs (large dataset)
    results["c3"] = train_one("classifier3_emotion", epochs=2, batch_size=32, lr=2e-5, use_weights=True)

    print(f"\n{'='*60}")
    print("  ALL TRAINING COMPLETE")
    print(f"{'='*60}\n")
    for name, r in results.items():
        print(f"  {name}: accuracy={r['eval_accuracy']:.4f}, f1={r['eval_f1']:.4f}")
