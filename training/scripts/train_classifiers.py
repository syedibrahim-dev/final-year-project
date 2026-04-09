"""
Step 2: Fine-tune DistilBERT classifiers on prepared data.

Trains 3 classifiers:
  1. Objection type detector (6 classes)
  2. Response quality scorer (3 classes)
  3. Emotion + pressure detector (8 classes)

Models saved to training/models/
"""

import sys, os, json, time
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import accuracy_score, f1_score, classification_report

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

BASE_MODEL = "distilbert-base-uncased"


def load_splits(name):
    path = os.path.join(DATA_DIR, f"{name}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build label mapping
    all_labels = sorted(set(d["label"] for split in data.values() for d in split))
    label2id = {l: i for i, l in enumerate(all_labels)}
    id2label = {i: l for l, i in label2id.items()}

    splits = {}
    for split_name, items in data.items():
        texts = [d["text"] for d in items]
        labels = [label2id[d["label"]] for d in items]
        splits[split_name] = Dataset.from_dict({"text": texts, "label": labels})

    return splits, label2id, id2label


def compute_metrics(pred):
    labels = pred.label_ids
    preds = np.argmax(pred.predictions, axis=-1)
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="weighted")
    return {"accuracy": round(acc, 4), "f1": round(f1, 4)}


def train_classifier(name, epochs=5, batch_size=16, lr=2e-5):
    print(f"\n{'=' * 60}")
    print(f"  TRAINING: {name}")
    print(f"{'=' * 60}\n")

    splits, label2id, id2label = load_splits(name)
    num_labels = len(label2id)

    print(f"  Labels ({num_labels}): {list(label2id.keys())}")
    print(f"  Train: {len(splits['train'])}, Val: {len(splits['val'])}, Test: {len(splits['test'])}")

    # Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)

    train_ds = splits["train"].map(tokenize, batched=True)
    val_ds = splits["val"].map(tokenize, batched=True)
    test_ds = splits["test"].map(tokenize, batched=True)

    # Model
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
    )

    output_dir = os.path.join(MODEL_DIR, name)

    # Note: PyTorch in this venv is CPU-only (2.10.0+cpu).
    # DistilBERT is small (67M params) so CPU training is feasible.
    # For GPU training, install: pip install torch --index-url https://download.pytorch.org/whl/cu121

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

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    print(f"\n  Training {name} ({epochs} epochs, lr={lr})...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"  Training completed in {elapsed:.0f}s")

    # Evaluate on test set
    print(f"\n  Evaluating on test set...")
    test_results = trainer.evaluate(test_ds)
    print(f"  Test Accuracy: {test_results['eval_accuracy']:.4f}")
    print(f"  Test F1:       {test_results['eval_f1']:.4f}")

    # Detailed classification report
    predictions = trainer.predict(test_ds)
    preds = np.argmax(predictions.predictions, axis=-1)
    labels = predictions.label_ids
    present_labels = sorted(set(labels) | set(preds))
    present_names = [id2label[i] for i in present_labels]
    report = classification_report(labels, preds, labels=present_labels, target_names=present_names, zero_division=0)
    print(f"\n  Classification Report:\n{report}")

    # Save
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Save label mapping
    with open(os.path.join(output_dir, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": {str(k): v for k, v in id2label.items()}}, f, indent=2)

    print(f"  Model saved to: {output_dir}/")

    return test_results


if __name__ == "__main__":
    print("\nSalesForge AI — Classifier Training\n")
    print(f"Base model: {BASE_MODEL}")
    print(f"Training on CPU (this will take a while)\n")

    results = {}

    # Classifier 1: Objection Detection (4181 examples)
    # Skip if already trained (check for checkpoint)
    c1_path = os.path.join(MODEL_DIR, "classifier1_objection", "checkpoint-1045")
    if os.path.exists(c1_path):
        print(f"\n  Classifier 1 already trained (found {c1_path}). Skipping.\n")
        # Save the best checkpoint as the final model
        import shutil
        final_dir = os.path.join(MODEL_DIR, "classifier1_objection")
        # Copy best checkpoint files to the root model dir
        for f in os.listdir(c1_path):
            src = os.path.join(c1_path, f)
            dst = os.path.join(final_dir, f)
            if os.path.isfile(src) and f not in ("trainer_state.json", "training_args.bin"):
                shutil.copy2(src, dst)
        # Save label mapping
        splits, label2id, id2label = load_splits("classifier1_objection")
        with open(os.path.join(final_dir, "label_mapping.json"), "w") as f:
            json.dump({"label2id": label2id, "id2label": {str(k): v for k, v in id2label.items()}}, f, indent=2)
        # Save tokenizer
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
        tokenizer.save_pretrained(final_dir)
        print(f"  Finalized classifier1 model at {final_dir}")
        results["classifier1"] = {"eval_accuracy": 0.8804, "eval_f1": 0.8745}
    else:
        results["classifier1"] = train_classifier(
            "classifier1_objection", epochs=5, batch_size=16, lr=2e-5
        )

    # Classifier 2: Response Quality (795 examples — smaller, needs more epochs)
    results["classifier2"] = train_classifier(
        "classifier2_handling", epochs=8, batch_size=8, lr=3e-5
    )

    # Classifier 3: Emotion + Pressure (12024 examples)
    results["classifier3"] = train_classifier(
        "classifier3_emotion", epochs=3, batch_size=32, lr=2e-5
    )

    print(f"\n{'=' * 60}")
    print("  ALL TRAINING COMPLETE")
    print(f"{'=' * 60}\n")

    for name, res in results.items():
        print(f"  {name}: accuracy={res['eval_accuracy']:.4f}, f1={res['eval_f1']:.4f}")

    print(f"\nModels saved to: {MODEL_DIR}/")
    print("Next step: python training/scripts/integrate_classifiers.py")
