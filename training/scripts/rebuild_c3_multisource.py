"""
Rebuild Classifier 3 training data from 5 domain-diverse sources.
Addresses committee concern: "all from Reddit"

Sources:
  1. GoEmotions (Reddit, 28 labels) — breadth
  2. dair-ai/emotion (general text, 6 labels) — different domain
  3. ESConv (emotional support dialogues) — conversational context
  4. DeepMost SaaS (sales conversations) — domain-specific
  5. Augmented pressure (hand-crafted) — sales-specific pressure
"""
import sys, os, json, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datasets import load_dataset
from collections import Counter

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

examples = []

# ── Source 1: GoEmotions ──
print("1. GoEmotions...")
ge = load_dataset("go_emotions", "simplified", split="train")
ge_labels = ge.features["labels"].feature.names
emotion_map = {
    "neutral": "neutral", "approval": "positive", "admiration": "positive",
    "joy": "positive", "gratitude": "positive", "optimism": "positive",
    "love": "positive", "caring": "empathetic", "relief": "empathetic",
    "anger": "negative", "annoyance": "negative", "disapproval": "negative",
    "disgust": "negative", "disappointment": "negative", "sadness": "negative",
    "grief": "negative", "remorse": "negative", "fear": "anxious",
    "nervousness": "anxious", "confusion": "anxious", "surprise": "neutral",
    "curiosity": "neutral", "realization": "neutral", "amusement": "positive",
    "excitement": "positive", "pride": "positive", "desire": "neutral",
    "embarrassment": "anxious",
}
ge_items = []
for row in ge:
    text = row["text"]
    label_ids = row["labels"]
    if not text or len(text.strip()) < 10 or not label_ids:
        continue
    label_name = ge_labels[label_ids[0]]
    mapped = emotion_map.get(label_name, "neutral")
    ge_items.append({"text": text.strip(), "label": mapped, "source": "go_emotions"})
random.shuffle(ge_items)
ge_items = ge_items[:10000]
examples.extend(ge_items)
print(f"   GoEmotions: {len(ge_items)} (capped from {len(ge)})")

# ── Source 2: dair-ai/emotion ──
print("2. dair-ai/emotion...")
dair = load_dataset("dair-ai/emotion", split="train")
dair_names = dair.features["label"].names
dair_map = {"sadness": "negative", "joy": "positive", "love": "empathetic",
            "anger": "negative", "fear": "anxious", "surprise": "neutral"}
dair_items = []
for row in dair:
    text = row["text"]
    mapped = dair_map.get(dair_names[row["label"]], "neutral")
    if text and len(text.strip()) >= 10:
        dair_items.append({"text": text.strip(), "label": mapped, "source": "dair_emotion"})
examples.extend(dair_items)
print(f"   dair-ai/emotion: {len(dair_items)}")

# ── Source 3: ESConv ──
print("3. ESConv...")
esconv = load_dataset("thu-coai/esconv", split="train")
esconv_map = {"anxiety": "anxious", "depression": "negative", "sadness": "negative",
              "anger": "negative", "fear": "anxious", "disgust": "negative",
              "guilt": "negative", "shame": "negative", "jealousy": "negative",
              "joy": "positive", "neutral": "neutral"}
esconv_items = []
for row in esconv:
    text_raw = row.get("text", "")
    if not text_raw:
        continue
    try:
        conv = json.loads(text_raw)
        emotion = conv.get("emotion_type", "neutral").lower()
        mapped = esconv_map.get(emotion, "neutral")
        dialog = conv.get("dialog", [])
        for turn in dialog:
            utt = turn.get("text", turn.get("content", ""))
            if utt and len(utt.strip()) >= 10:
                esconv_items.append({"text": utt.strip(), "label": mapped, "source": "esconv"})
    except (json.JSONDecodeError, AttributeError):
        continue
examples.extend(esconv_items)
print(f"   ESConv: {len(esconv_items)}")

# ── Source 4: DeepMost SaaS ──
print("4. DeepMost SaaS...")
with open(os.path.join(DATA_DIR, "saas_raw_1000.json"), "r", encoding="utf-8") as f:
    saas_raw = json.load(f)
style_map = {"skeptical_challenging": "negative", "confused_overwhelmed": "anxious",
             "empathetic_supportive": "empathetic", "casual_friendly": "positive",
             "direct_professional": "neutral", "technical_detailed": "neutral",
             "knowledgeable_assertive": "positive", "consultative_advisory": "empathetic",
             "urgent_time_pressed": "anxious", "storytelling_narrative": "neutral"}
saas_items = []
for row in saas_raw:
    conv = row.get("conversation", "")
    style = row.get("conversation_style", "neutral")
    if isinstance(conv, str):
        try:
            conv = json.loads(conv)
        except json.JSONDecodeError:
            continue
    if not isinstance(conv, list):
        continue
    mapped = style_map.get(style, "neutral")
    for turn in conv:
        text = turn.get("message", "").strip()
        if text and len(text) >= 10:
            saas_items.append({"text": text, "label": mapped, "source": "deepmost_saas"})
examples.extend(saas_items)
print(f"   DeepMost SaaS: {len(saas_items)}")

# ── Source 5: Augmented pressure ──
print("5. Sales pressure (augmented)...")
sys.path.insert(0, os.path.dirname(__file__))
from augment_pressure import CONSULTATIVE_EXAMPLES, URGENT_EXAMPLES, DEMANDING_EXAMPLES
pressure_unique = []
for text in CONSULTATIVE_EXAMPLES:
    pressure_unique.append({"text": text, "label": "consultative", "source": "augmented_pressure"})
for text in URGENT_EXAMPLES:
    pressure_unique.append({"text": text, "label": "urgent", "source": "augmented_pressure"})
for text in DEMANDING_EXAMPLES:
    pressure_unique.append({"text": text, "label": "demanding", "source": "augmented_pressure"})

# Oversample to ~10% of total
target = int(len(examples) * 0.10)
oversampled = []
while len(oversampled) < target:
    oversampled.extend(pressure_unique)
oversampled = oversampled[:target]
examples.extend(oversampled)
print(f"   Pressure: {len(pressure_unique)} unique, oversampled to {len(oversampled)}")

# ── Summary ──
print(f"\n{'='*60}")
print(f"MULTI-SOURCE C3 DATASET")
print(f"{'='*60}")
print(f"Total: {len(examples)}")
sources = Counter(e["source"] for e in examples)
for src, cnt in sources.most_common():
    pct = cnt / len(examples) * 100
    print(f"  {src:25s}: {cnt:6d} ({pct:.1f}%)")
labels = Counter(e["label"] for e in examples)
print(f"Labels:")
for label, cnt in labels.most_common():
    pct = cnt / len(examples) * 100
    print(f"  {label:15s}: {cnt:6d} ({pct:.1f}%)")

# Save
random.shuffle(examples)
n = len(examples)
train_end = int(n * 0.8)
val_end = int(n * 0.9)
splits = {"train": examples[:train_end], "val": examples[train_end:val_end], "test": examples[val_end:]}
path = os.path.join(DATA_DIR, "classifier3_emotion.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(splits, f, ensure_ascii=False)
print(f"\nSaved: {path}")
print(f"Train: {len(splits['train'])}, Val: {len(splits['val'])}, Test: {len(splits['test'])}")
