"""
Data Preparation for Conversion Predictor — Random Split + Embeddings

Downloads 2300 conversations from the SalesRLAgent dataset,
shuffles randomly, splits 80/20, extracts combined features
(28 keyword + 388 embedding = 416), then applies PCA during training.

Usage:
    python -m conversion.data_prep                    # Full: download + features
    python -m conversion.data_prep --skip-download     # Use cached JSON
    python -m conversion.data_prep --no-embeddings     # Keyword features only
"""

import os
import json
import random
import numpy as np
import requests
from pathlib import Path

from conversion.feature_extractor import (
    extract_features_from_messages,
    NUM_FEATURES,
    FEATURE_NAMES,
)

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# HuggingFace REST API
HF_API = "https://datasets-server.huggingface.co/rows"
DATASET = "DeepMostInnovations/saas-sales-conversations"
BATCH = 100

# Dataset config
TOTAL_ROWS = 2300
TEST_FRACTION = 0.2
RANDOM_SEED = 42


def _fetch_rows(offset, length):
    """Fetch rows from HuggingFace datasets API."""
    params = {
        "dataset": DATASET,
        "config": "default",
        "split": "train",
        "offset": offset,
        "length": min(length, BATCH),
    }
    resp = requests.get(HF_API, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _parse_conversation(conv_field):
    """Parse conversation field to our message format."""
    if isinstance(conv_field, str):
        try:
            messages = json.loads(conv_field)
        except json.JSONDecodeError:
            return []
    elif isinstance(conv_field, list):
        messages = conv_field
    else:
        return []
    
    normalized = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get('role', msg.get('sender', '')).lower()
            text = msg.get('content', msg.get('text', msg.get('message', '')))
            if not text or not isinstance(text, str):
                continue
            if role in ('sales_rep', 'sales', 'representative', 'agent', 'salesperson'):
                sender = 'trainee'
            elif role in ('customer', 'prospect', 'client', 'buyer', 'user'):
                sender = 'ai_customer'
            else:
                sender = 'trainee' if len(normalized) % 2 == 0 else 'ai_customer'
            normalized.append({'sender': sender, 'text': text.strip()})
    return normalized


def download_all(n_rows=TOTAL_ROWS):
    """Download all conversations from the HuggingFace API."""
    print(f"📥 Downloading {n_rows} conversations from {DATASET}...")
    
    conversations = []
    skipped = 0
    offset = 0
    
    while offset < n_rows:
        batch_size = min(BATCH, n_rows - offset)
        print(f"   Fetching rows {offset}-{offset + batch_size}...")
        
        try:
            data = _fetch_rows(offset, batch_size)
        except Exception as e:
            print(f"   Error: {e}")
            break
        
        rows = data.get('rows', [])
        if not rows:
            break
        
        for row_data in rows:
            rec = row_data.get('row', row_data)
            msgs = _parse_conversation(rec.get('conversation', '[]'))
            outcome = rec.get('outcome')
            
            if outcome is None or len(msgs) < 4:
                skipped += 1
                continue
            
            conversations.append({
                'messages': msgs,
                'expected': int(outcome),
                'length': len(msgs),
            })
        
        offset += len(rows)
    
    n_pos = sum(1 for c in conversations if c['expected'] == 1)
    n_neg = len(conversations) - n_pos
    print(f"   Got {len(conversations)} valid (Convert={n_pos}, NoConvert={n_neg}, skipped={skipped})")
    return conversations


def random_split(conversations, test_frac=TEST_FRACTION, seed=RANDOM_SEED):
    """Randomly split conversations into train and test sets."""
    rng = random.Random(seed)
    indices = list(range(len(conversations)))
    rng.shuffle(indices)
    
    n_test = int(len(conversations) * test_frac)
    test_idx = set(indices[:n_test])
    
    train = [conversations[i] for i in range(len(conversations)) if i not in test_idx]
    test = [conversations[i] for i in range(len(conversations)) if i in test_idx]
    
    return train, test


def extract_keyword_features(conversations, multi_turn=True):
    """Extract 28 keyword-based features."""
    X_list, y_list = [], []
    
    for conv in conversations:
        msgs = conv['messages']
        outcome = conv['expected']
        
        if multi_turn and len(msgs) >= 8:
            turn_indices = sorted(set([
                max(1, len(msgs) // 4) - 1,
                max(1, len(msgs) // 2) - 1,
                max(1, 3 * len(msgs) // 4) - 1,
                len(msgs) - 1,
            ]))
        else:
            turn_indices = [len(msgs) - 1]
        
        for turn_idx in turn_indices:
            features = extract_features_from_messages(
                msgs, turn_index=turn_idx, expected_length=len(msgs),
            )
            if not np.any(np.isnan(features)):
                X_list.append(features)
                y_list.append(outcome)
    
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


def extract_embedding_features(conversations, multi_turn=True):
    """Extract sentence embedding features using all-MiniLM-L6-v2."""
    from conversion.embedding_extractor import batch_extract_embeddings
    X_emb, indices = batch_extract_embeddings(conversations, multi_turn=multi_turn)
    return X_emb


def save_data(X, y, suffix=""):
    """Save processed features to disk."""
    fname = f"processed_features{suffix}.npz"
    path = DATA_DIR / fname
    np.savez(path, X=X, y=y, feature_names=np.array(FEATURE_NAMES))
    print(f"💾 Saved {fname}: {X.shape[0]} samples × {X.shape[1]} features ({path.stat().st_size / 1024:.0f} KB)")
    return path


def load_processed_data(suffix=""):
    """Load previously processed features."""
    fname = f"processed_features{suffix}.npz"
    path = DATA_DIR / fname
    if not path.exists():
        raise FileNotFoundError(f"No data at {path}. Run data_prep.py first.")
    data = np.load(path, allow_pickle=True)
    return data['X'], data['y'], data['feature_names']


# ── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-download', action='store_true')
    parser.add_argument('--no-embeddings', action='store_true')
    parser.add_argument('--no-multi-turn', action='store_true')
    args = parser.parse_args()
    
    multi_turn = not args.no_multi_turn
    use_embeddings = not args.no_embeddings
    
    print("=" * 60)
    print("  Conversion Predictor — Data Preparation")
    print(f"  Split: Random {int((1-TEST_FRACTION)*100)}/{int(TEST_FRACTION*100)} (seed={RANDOM_SEED})")
    print(f"  Multi-turn: {multi_turn} | Embeddings: {use_embeddings}")
    print("=" * 60)
    
    # Step 1: Get conversations
    cache_path = DATA_DIR / "all_conversations.json"
    
    if args.skip_download and cache_path.exists():
        print(f"\n📂 Loading cached conversations...")
        with open(cache_path, 'r', encoding='utf-8') as f:
            all_convs = json.load(f)
        print(f"   Loaded {len(all_convs)} conversations")
    else:
        all_convs = download_all()
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(all_convs, f, indent=1)
        print(f"   Cached to {cache_path}")
    
    # Step 2: Random split
    print(f"\n🔀 Random split ({len(all_convs)} conversations)...")
    train_convs, test_convs = random_split(all_convs)
    
    n_train_pos = sum(1 for c in train_convs if c['expected'] == 1)
    n_test_pos = sum(1 for c in test_convs if c['expected'] == 1)
    print(f"   Train: {len(train_convs)} (Convert={n_train_pos}, NoConvert={len(train_convs)-n_train_pos})")
    print(f"   Test:  {len(test_convs)} (Convert={n_test_pos}, NoConvert={len(test_convs)-n_test_pos})")
    
    # Step 3: Extract keyword features
    print(f"\n📊 Extracting keyword features...")
    X_train_kw, y_train = extract_keyword_features(train_convs, multi_turn=multi_turn)
    X_test_kw, y_test = extract_keyword_features(test_convs, multi_turn=False)
    print(f"   Train: {X_train_kw.shape[0]} samples × {X_train_kw.shape[1]} features")
    print(f"   Test:  {X_test_kw.shape[0]} samples × {X_test_kw.shape[1]} features")
    
    if use_embeddings:
        # Step 4: Extract embeddings
        print(f"\n🧠 Extracting sentence embeddings...")
        X_train_emb = extract_embedding_features(train_convs, multi_turn=multi_turn)
        X_test_emb = extract_embedding_features(test_convs, multi_turn=False)
        
        if X_train_emb is not None and len(X_train_emb) == len(X_train_kw):
            X_train = np.hstack([X_train_kw, X_train_emb])
            X_test = np.hstack([X_test_kw, X_test_emb])
            print(f"   Combined: {X_train.shape[1]} features (28 kw + {X_train_emb.shape[1]} emb)")
        else:
            print("   WARNING: embedding mismatch, using keyword only")
            X_train, X_test = X_train_kw, X_test_kw
    else:
        X_train, X_test = X_train_kw, X_test_kw
    
    # Step 5: Save
    save_data(X_train, y_train, suffix="")
    save_data(X_test, y_test, suffix="_test")
    
    print("\n🎉 Done! Next: python -m conversion.train_model")
