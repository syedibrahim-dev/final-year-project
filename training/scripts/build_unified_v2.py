"""
Build unified dataset from ALL sources including DialogStudio.
"""
import sys, os, json, glob, csv, random
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from collections import Counter
random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DS_CACHE = os.path.join(DATA_DIR, "dialogstudio_raw")

all_conversations = []


def load_dialogstudio_subset(name, subdir):
    """Load a DialogStudio subset from downloaded JSON files."""
    path = os.path.join(DS_CACHE, subdir, "train")
    convs = []
    for jf in sorted(glob.glob(os.path.join(path, "*.json"))):
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, dialog in data.items():
            log = dialog.get("log", [])
            turns = []
            for t in log:
                u = t.get("user utterance", "").strip()
                s = t.get("system response", "").strip()
                if u and len(u) >= 5:
                    turns.append({"speaker": "customer", "text": u})
                if s and len(s) >= 5:
                    turns.append({"speaker": "sales_rep", "text": s})
            if len(turns) >= 2:
                convs.append({
                    "id": key, "source": name, "turns": turns,
                    "outcome": None, "style": None,
                })
    return convs


# ── 1. DeepMost SaaS ──
print("Loading DeepMost SaaS...")
raw_path = os.path.join(DATA_DIR, "saas_raw_1000.json")
with open(raw_path, "r", encoding="utf-8") as f:
    raw = json.load(f)
for i, row in enumerate(raw):
    conv = row.get("conversation", "")
    if isinstance(conv, str):
        try:
            conv = json.loads(conv)
        except json.JSONDecodeError:
            continue
    if not isinstance(conv, list) or len(conv) < 2:
        continue
    turns = []
    for t in conv:
        text = t.get("message", "").strip()
        speaker = t.get("speaker", "")
        if text and len(text) >= 5 and speaker in ("customer", "sales_rep"):
            turns.append({"speaker": speaker, "text": text})
    if len(turns) >= 2:
        all_conversations.append({
            "id": f"saas_{i}", "source": "deepmost_saas", "turns": turns,
            "outcome": row.get("outcome"), "style": row.get("conversation_style"),
        })
print(f"  deepmost_saas: {sum(1 for c in all_conversations if c['source']=='deepmost_saas')}")

# ── 2. DialogStudio: CraigslistBargains ──
print("Loading CraigslistBargains (DialogStudio)...")
convs = load_dialogstudio_subset("craigslist_bargains", "task_oriented/CraigslistBargains")
all_conversations.extend(convs)
print(f"  craigslist_bargains: {len(convs)}")

# ── 3. DialogStudio: CaSiNo ──
print("Loading CaSiNo (DialogStudio)...")
convs = load_dialogstudio_subset("casino_ds", "task_oriented/CaSiNo")
all_conversations.extend(convs)
print(f"  casino_ds: {len(convs)}")

# ── 4. DialogStudio: SalesBot (Task-Oriented) ──
print("Loading SalesBot Task-Oriented (DialogStudio)...")
convs = load_dialogstudio_subset("salesbot_to", "task_oriented/SalesBot")
all_conversations.extend(convs)
print(f"  salesbot_to: {len(convs)}")

# ── 5. DialogStudio: SalesBot (Conversational Rec.) ──
print("Loading SalesBot Conversational Rec. (DialogStudio)...")
convs = load_dialogstudio_subset("salesbot_cr", "conversational_recommendation/SalesBot")
all_conversations.extend(convs)
print(f"  salesbot_cr: {len(convs)}")

# ── 6. goendalf666 sales ──
print("Loading goendalf666 sales...")
from datasets import load_dataset
ds = load_dataset("goendalf666/sales-conversations", split="train")
count = 0
for i, row in enumerate(ds):
    turns = []
    for col_idx in range(20):
        text = row.get(str(col_idx), None)
        if text and isinstance(text, str) and len(text.strip()) >= 5:
            speaker = "customer" if col_idx % 2 == 0 else "sales_rep"
            turns.append({"speaker": speaker, "text": text.strip()})
    if len(turns) >= 2:
        all_conversations.append({
            "id": f"goendalf_{i}", "source": "goendalf_sales", "turns": turns,
            "outcome": None, "style": None,
        })
        count += 1
print(f"  goendalf_sales: {count}")

# ── 7. gwenshap transcripts ──
print("Loading gwenshap transcripts...")
cache_dir = os.path.expanduser("~/.cache/huggingface/hub/datasets--gwenshap--sales-transcripts")
csv_files = glob.glob(os.path.join(cache_dir, "**/*.csv"), recursive=True)
conv_map = {}
for csv_file in csv_files:
    with open(csv_file, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("Conversation", "")
            speaker = row.get("Speaker", "")
            text = row.get("Text", "")
            if not cid or not text:
                continue
            if cid not in conv_map:
                conv_map[cid] = []
            sp = "sales_rep" if "Sales" in speaker or "Rep" in speaker else "customer"
            conv_map[cid].append({"speaker": sp, "text": text.strip()})
count = 0
for cid, turns in conv_map.items():
    if len(turns) >= 2:
        all_conversations.append({
            "id": f"gwenshap_{cid}", "source": "gwenshap", "turns": turns,
            "outcome": None, "style": None,
        })
        count += 1
print(f"  gwenshap: {count}")

# ── 8. CaSiNo direct (already loaded separately with strategy annotations) ──
print("Loading CaSiNo direct (with strategy annotations)...")
ds2 = load_dataset("casino", split="train")
count = 0
for i, row in enumerate(ds2):
    annotations = row.get("annotations", [])
    if not annotations or len(annotations) < 2:
        continue
    turns = []
    for j, ann in enumerate(annotations):
        if not isinstance(ann, list) or len(ann) < 2:
            continue
        text = ann[0]
        if not text or len(text.strip()) < 5:
            continue
        speaker = "customer" if j % 2 == 0 else "sales_rep"
        turns.append({"speaker": speaker, "text": text.strip()})
    if len(turns) >= 2:
        all_conversations.append({
            "id": f"casino_direct_{i}", "source": "casino_direct", "turns": turns,
            "outcome": None, "style": None,
        })
        count += 1
print(f"  casino_direct: {count}")

# ── Summary ──
print(f"\n{'='*60}")
print(f"UNIFIED DATASET COMPLETE")
print(f"{'='*60}")
print(f"Total conversations: {len(all_conversations)}")
sources = Counter(c["source"] for c in all_conversations)
for src, cnt in sources.most_common():
    print(f"  {src}: {cnt}")
total_turns = sum(len(c["turns"]) for c in all_conversations)
print(f"Total turns: {total_turns}")
labeled = sum(1 for c in all_conversations if c["outcome"] is not None)
print(f"With outcome labels: {labeled}")

# Save conversations
path = os.path.join(DATA_DIR, "unified_conversations.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(all_conversations, f, ensure_ascii=False)
size_mb = os.path.getsize(path) / 1024 / 1024
print(f"\nSaved: {path} ({size_mb:.1f} MB)")

# Extract utterances
utterances = []
for conv in all_conversations:
    for i, t in enumerate(conv["turns"]):
        utterances.append({
            "text": t["text"], "speaker": t["speaker"],
            "conv_id": conv["id"], "source": conv["source"],
            "turn_idx": i, "outcome": conv.get("outcome"),
        })

utt_path = os.path.join(DATA_DIR, "unified_utterances.json")
with open(utt_path, "w", encoding="utf-8") as f:
    json.dump(utterances, f, ensure_ascii=False)
utt_size = os.path.getsize(utt_path) / 1024 / 1024
print(f"Saved: {utt_path} ({utt_size:.1f} MB)")
print(f"Total utterances: {len(utterances)}")

print(f"\n{'='*60}")
print("STEP 2 COMPLETE")
print(f"{'='*60}")
