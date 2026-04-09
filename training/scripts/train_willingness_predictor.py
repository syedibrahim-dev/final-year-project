"""
STEP 5: Translate SalesTalk + Train Willingness Predictor

Source: CyberAgentAILab/salestalk-dataset (109 dialogues, 3,684 utterances)
Language: Japanese → English (translated via MarianMT)
Labels: 3 willingness dimensions per utterance
  - CONTINUING_DIALOGUE: positive/neutral/negative
  - PROVIDING_INFORMATION: positive/neutral/negative
  - GOAL_ACCEPTANCE: positive/neutral/negative

We train a multi-label classifier that predicts all 3 dimensions.
This feeds into the Adaptive Agent and EQ scoring.
"""

import sys, os, json, time, random
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
    MarianMTModel,
    MarianTokenizer,
)
from sklearn.metrics import accuracy_score, f1_score, classification_report
from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
BASE_MODEL = "distilbert-base-uncased"


def load_and_translate():
    """Load SalesTalk, translate JP→EN, extract willingness labels."""
    raw_path = os.path.join(DATA_DIR, "salestalk_raw", "salestalk.json")
    translated_path = os.path.join(DATA_DIR, "salestalk_translated.json")

    # Check if already translated
    if os.path.exists(translated_path):
        print("  Loading cached translations...")
        with open(translated_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Load raw
    dialogues = []
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                dialogues.append(json.loads(line.strip()))

    print(f"  Loaded {len(dialogues)} dialogues")

    # Load translation model
    print("  Loading MarianMT ja→en translation model...")
    mt_model_name = "Helsinki-NLP/opus-mt-ja-en"
    mt_tokenizer = MarianTokenizer.from_pretrained(mt_model_name)
    mt_model = MarianMTModel.from_pretrained(mt_model_name)
    mt_model.eval()
    print("  Translation model loaded!")

    def translate_batch(texts, batch_size=16):
        """Translate a batch of Japanese texts to English."""
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            inputs = mt_tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=128)
            with torch.no_grad():
                translated = mt_model.generate(**inputs, max_length=128)
            decoded = mt_tokenizer.batch_decode(translated, skip_special_tokens=True)
            results.extend(decoded)
        return results

    # Extract and translate utterances
    examples = []
    all_jp_texts = []
    all_meta = []

    for d in dialogues:
        for u in d.get("utterances", []):
            speaker = u.get("speaker", "")
            if speaker == "system":
                continue

            message = u.get("message", "").strip()
            if not message or len(message) < 3:
                continue

            evals = u.get("user_utterance_evals", [])
            if not evals:
                continue

            # Extract willingness labels
            labels = {}
            for e in evals:
                label_name = e.get("label", "")
                answer = e.get("answer", "neutral")
                if label_name in ("CONTINUING_DIALOGUE", "PROVIDING_INFORMATION", "GOAL_ACCEPTANCE"):
                    labels[label_name] = answer

            if len(labels) == 3:
                all_jp_texts.append(message)
                all_meta.append({
                    "speaker": "sales_rep" if speaker == "sales" else "customer",
                    "continuing": labels["CONTINUING_DIALOGUE"],
                    "providing_info": labels["PROVIDING_INFORMATION"],
                    "goal_acceptance": labels["GOAL_ACCEPTANCE"],
                    "dialogue_id": d.get("dialogue_id", 0),
                })

    print(f"  Utterances with willingness labels: {len(all_jp_texts)}")

    # Translate in batches
    print(f"  Translating {len(all_jp_texts)} utterances ja→en...")
    t0 = time.time()
    translated_texts = translate_batch(all_jp_texts)
    elapsed = time.time() - t0
    print(f"  Translation: {elapsed:.0f}s ({len(all_jp_texts) / elapsed:.1f} utterances/sec)")

    # Combine
    for text_en, meta in zip(translated_texts, all_meta):
        if text_en and len(text_en.strip()) >= 5:
            examples.append({
                "text": text_en.strip(),
                "speaker": meta["speaker"],
                "continuing": meta["continuing"],
                "providing_info": meta["providing_info"],
                "goal_acceptance": meta["goal_acceptance"],
                "dialogue_id": meta["dialogue_id"],
            })

    print(f"  Valid translated examples: {len(examples)}")

    # Cache
    with open(translated_path, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)
    print(f"  Cached to {translated_path}")

    return examples


def build_combined_label(example):
    """
    Combine 3 willingness dimensions into a single label for classification.
    9 possible combinations (3x3), but we simplify to 5 classes:
      high_willingness: all positive
      moderate_positive: mostly positive, some neutral
      neutral: all neutral or mixed
      moderate_negative: some negative signals
      low_willingness: contains negative
    """
    dims = [example["continuing"], example["providing_info"], example["goal_acceptance"]]
    pos_count = dims.count("positive")
    neg_count = dims.count("negative")

    if neg_count >= 2:
        return "low_willingness"
    elif neg_count == 1:
        return "moderate_negative"
    elif pos_count >= 3:
        return "high_willingness"
    elif pos_count >= 2:
        return "moderate_positive"
    else:
        return "neutral"


def compute_metrics(pred):
    labels = pred.label_ids
    preds = np.argmax(pred.predictions, axis=-1)
    return {
        "accuracy": round(accuracy_score(labels, preds), 4),
        "f1": round(f1_score(labels, preds, average="weighted"), 4),
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
    print("STEP 5: Willingness Predictor (SalesTalk)")
    print("=" * 60 + "\n")

    # Load and translate
    print("Loading and translating SalesTalk dataset...")
    examples = load_and_translate()

    # Build combined labels
    for ex in examples:
        ex["label"] = build_combined_label(ex)

    print(f"\nTotal examples: {len(examples)}")
    labels = Counter(ex["label"] for ex in examples)
    print(f"Label distribution:")
    for label, count in labels.most_common():
        print(f"  {label:25s}: {count:4d} ({count/len(examples)*100:.1f}%)")

    # Show sample translations
    print(f"\nSample translations:")
    for ex in examples[:5]:
        print(f"  [{ex['label']:20s}] {ex['text'][:80]}")

    # Split
    random.shuffle(examples)
    n = len(examples)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)

    all_labels = sorted(set(ex["label"] for ex in examples))
    label2id = {l: i for i, l in enumerate(all_labels)}
    id2label = {i: l for l, i in label2id.items()}
    num_labels = len(label2id)

    train_ds = Dataset.from_dict({
        "text": [ex["text"] for ex in examples[:train_end]],
        "label": [label2id[ex["label"]] for ex in examples[:train_end]],
    })
    val_ds = Dataset.from_dict({
        "text": [ex["text"] for ex in examples[train_end:val_end]],
        "label": [label2id[ex["label"]] for ex in examples[train_end:val_end]],
    })
    test_ds = Dataset.from_dict({
        "text": [ex["text"] for ex in examples[val_end:]],
        "label": [label2id[ex["label"]] for ex in examples[val_end:]],
    })

    print(f"\nTrain: {len(train_ds)}, Val: {len(val_ds)}, Test: {len(test_ds)}")

    # Tokenize
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(batch):
        return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=128)

    train_ds = train_ds.map(tokenize, batched=True)
    val_ds = val_ds.map(tokenize, batched=True)
    test_ds = test_ds.map(tokenize, batched=True)

    # Model
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=num_labels, id2label=id2label, label2id=label2id,
    )

    output_dir = os.path.join(MODEL_DIR, "willingness_predictor")

    # Class weights
    train_labels = [label2id[ex["label"]] for ex in examples[:train_end]]
    counts = Counter(train_labels)
    total = len(train_labels)
    weights = [min(10.0, total / (num_labels * counts.get(i, 1))) for i in range(num_labels)]
    print(f"Class weights: {[round(w, 2) for w in weights]}")

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=8,  # small dataset needs more epochs
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
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

    print(f"\nTraining (8 epochs)...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"Training: {elapsed:.0f}s ({elapsed / 60:.1f} min)")

    # Test
    print(f"\nEvaluating on test set...")
    test_results = trainer.evaluate(test_ds)
    print(f"Test Accuracy: {test_results['eval_accuracy']:.4f}")
    print(f"Test F1:       {test_results['eval_f1']:.4f}")

    # Report
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
    print(f"\nThis model predicts buyer willingness from the SalesTalk framework.")
    print(f"Based on Hentona et al., COLING 2025 — the only real-human annotated sales dataset.")


if __name__ == "__main__":
    main()
