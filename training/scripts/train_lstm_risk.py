"""
Train LSTM Conversation Risk Model.

Two-stage ML pipeline:
  Stage 1: DistilBERT classifiers extract per-turn features (already done)
  Stage 2: LSTM learns conversation trajectories → risk score

The LSTM processes partial conversations (turns 1..N) and predicts
deal outcome at each step. This gives a REAL-TIME risk score that
updates every turn — showing how the conversation trajectory evolves.

Architecture:
  Input: (batch, seq_len, 27) — padded turn feature vectors
  LSTM: 2 layers, hidden_dim=64
  Output: (batch, 1) — risk score (probability of deal failure)

Training approach:
  - For each conversation, create MULTIPLE training samples:
    turns[0:1] → outcome, turns[0:2] → outcome, ..., turns[0:N] → outcome
  - This teaches the model to predict from PARTIAL conversations
  - Weighted loss: early turns get lower weight (less signal)
"""

import json, os, sys, time, random
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, classification_report

random.seed(42)
torch.manual_seed(42)
np.random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


class ConversationDataset(Dataset):
    """Dataset of partial conversation sequences → outcome."""

    def __init__(self, sequences, max_len=30):
        self.samples = []
        self.max_len = max_len

        for seq in sequences:
            features = seq["features"]
            outcome = seq["outcome"]
            n = len(features)

            # Create partial sequences: [0:2], [0:3], ..., [0:N]
            # Skip first turn (too little info) and create samples from turn 2 onwards
            for end in range(2, n + 1):
                partial = features[:end]
                # Position weight: later turns are more informative
                weight = min(1.0, end / max(4, n * 0.5))
                self.samples.append({
                    "features": partial,
                    "outcome": outcome,
                    "weight": weight,
                    "position": end / n,  # How far into the conversation
                })

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        features = sample["features"]

        # Pad to max_len
        feat_dim = len(features[0])
        padded = np.zeros((self.max_len, feat_dim), dtype=np.float32)
        seq_len = min(len(features), self.max_len)
        for i in range(seq_len):
            padded[i] = features[i]

        return {
            "features": torch.tensor(padded, dtype=torch.float32),
            "seq_len": torch.tensor(seq_len, dtype=torch.long),
            "outcome": torch.tensor(sample["outcome"], dtype=torch.float32),
            "weight": torch.tensor(sample["weight"], dtype=torch.float32),
        }


class ConversationLSTM(nn.Module):
    """LSTM that processes conversation turn sequences → risk score."""

    def __init__(self, input_dim=27, hidden_dim=64, num_layers=2, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False,
        )
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x, seq_lens):
        # Pack padded sequences for efficiency
        packed = nn.utils.rnn.pack_padded_sequence(
            x, seq_lens.cpu().clamp(min=1), batch_first=True, enforce_sorted=False
        )
        lstm_out, (hidden, _) = self.lstm(packed)

        # Use final hidden state of last layer
        final_hidden = hidden[-1]  # (batch, hidden_dim)
        logits = self.classifier(final_hidden).squeeze(-1)  # (batch,)
        return logits


def train_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss = 0
    all_preds = []
    all_labels = []

    for batch in dataloader:
        features = batch["features"].to(device)
        seq_lens = batch["seq_len"].to(device)
        outcomes = batch["outcome"].to(device)
        weights = batch["weight"].to(device)

        optimizer.zero_grad()
        logits = model(features, seq_lens)
        loss = criterion(logits, outcomes)
        # Apply position weights
        loss = (loss * weights).mean()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        preds = torch.sigmoid(logits).detach().cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(outcomes.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    all_preds_binary = [1 if p >= 0.5 else 0 for p in all_preds]
    acc = accuracy_score(all_labels, all_preds_binary)
    return avg_loss, acc


def evaluate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            features = batch["features"].to(device)
            seq_lens = batch["seq_len"].to(device)
            outcomes = batch["outcome"].to(device)

            logits = model(features, seq_lens)
            loss = criterion(logits, outcomes).mean()
            total_loss += loss.item()

            preds = torch.sigmoid(logits).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(outcomes.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    all_preds_binary = [1 if p >= 0.5 else 0 for p in all_preds]
    acc = accuracy_score(all_labels, all_preds_binary)
    f1 = f1_score(all_labels, all_preds_binary, average="binary")

    try:
        auc = roc_auc_score(all_labels, all_preds)
    except ValueError:
        auc = 0.0

    return avg_loss, acc, f1, auc, all_preds, all_labels


def main():
    print("=" * 60)
    print("TRAINING LSTM CONVERSATION RISK MODEL")
    print("=" * 60)

    # Load sequences
    seq_path = os.path.join(DATA_DIR, "lstm_sequences.json")
    with open(seq_path, "r") as f:
        sequences = json.load(f)

    print(f"Loaded {len(sequences)} conversation sequences")
    print(f"Feature dims: {len(sequences[0]['features'][0])}")
    print(f"Outcomes: converted={sum(1 for s in sequences if s['outcome']==1)}, failed={sum(1 for s in sequences if s['outcome']==0)}")

    # Split: 80% train, 10% val, 10% test (conversation-level split)
    random.shuffle(sequences)
    n = len(sequences)
    train_seqs = sequences[:int(n * 0.8)]
    val_seqs = sequences[int(n * 0.8):int(n * 0.9)]
    test_seqs = sequences[int(n * 0.9):]

    print(f"Split: train={len(train_seqs)}, val={len(val_seqs)}, test={len(test_seqs)}")

    # Create datasets with partial sequences
    max_len = max(s["num_turns"] for s in sequences)
    max_len = min(max_len, 30)  # Cap at 30 turns

    train_ds = ConversationDataset(train_seqs, max_len=max_len)
    val_ds = ConversationDataset(val_seqs, max_len=max_len)
    test_ds = ConversationDataset(test_seqs, max_len=max_len)

    print(f"Partial sequence samples: train={len(train_ds)}, val={len(val_ds)}, test={len(test_ds)}")

    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)

    # Model
    device = torch.device("cpu")
    input_dim = len(sequences[0]["features"][0])
    model = ConversationLSTM(input_dim=input_dim, hidden_dim=64, num_layers=2, dropout=0.3)
    model = model.to(device)

    param_count = sum(p.numel() for p in model.parameters())
    print(f"\nModel: LSTM (input={input_dim}, hidden=64, layers=2)")
    print(f"Parameters: {param_count:,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
    criterion = nn.BCEWithLogitsLoss(reduction='none')  # None for per-sample weighting

    # Training
    best_val_auc = 0
    best_epoch = 0
    epochs = 30

    print(f"\nTraining for {epochs} epochs...")
    t0 = time.time()

    for epoch in range(1, epochs + 1):
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc, val_f1, val_auc, _, _ = evaluate(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            best_epoch = epoch
            # Save best model
            save_dir = os.path.join(MODEL_DIR, "lstm_risk_model")
            os.makedirs(save_dir, exist_ok=True)
            torch.save({
                "model_state_dict": model.state_dict(),
                "input_dim": input_dim,
                "hidden_dim": 64,
                "num_layers": 2,
                "best_epoch": epoch,
                "val_auc": val_auc,
            }, os.path.join(save_dir, "model.pt"))

        if epoch % 5 == 0 or epoch == 1:
            print(f"  Epoch {epoch:2d}: train_loss={train_loss:.4f} train_acc={train_acc:.3f} | val_loss={val_loss:.4f} val_acc={val_acc:.3f} val_f1={val_f1:.3f} val_auc={val_auc:.3f}")

    elapsed = time.time() - t0
    print(f"\nTraining: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Best epoch: {best_epoch} (val AUC: {best_val_auc:.4f})")

    # Load best model and evaluate on test
    checkpoint = torch.load(os.path.join(MODEL_DIR, "lstm_risk_model", "model.pt"), weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])

    test_loss, test_acc, test_f1, test_auc, test_preds, test_labels = evaluate(model, test_loader, criterion, device)

    print(f"\n{'='*60}")
    print(f"TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Accuracy: {test_acc:.4f}")
    print(f"  F1 Score: {test_f1:.4f}")
    print(f"  AUC-ROC:  {test_auc:.4f}")

    # Per-class report
    test_preds_binary = [1 if p >= 0.5 else 0 for p in test_preds]
    print(f"\n{classification_report(test_labels, test_preds_binary, target_names=['failed', 'converted'])}")

    # Analyze risk by conversation position
    print("\nRisk Score by Conversation Position:")
    test_ds_raw = test_ds.samples
    position_buckets = {"early (0-33%)": [], "mid (33-66%)": [], "late (66-100%)": []}

    for sample, pred in zip(test_ds_raw[:len(test_preds)], test_preds):
        pos = sample["position"]
        correct = (pred >= 0.5) == sample["outcome"]
        if pos <= 0.33:
            position_buckets["early (0-33%)"].append(correct)
        elif pos <= 0.66:
            position_buckets["mid (33-66%)"].append(correct)
        else:
            position_buckets["late (66-100%)"].append(correct)

    for bucket, results in position_buckets.items():
        if results:
            acc = sum(results) / len(results)
            print(f"  {bucket}: {acc:.1%} accuracy ({len(results)} samples)")

    print(f"\nModel saved to: {os.path.join(MODEL_DIR, 'lstm_risk_model')}/")
    print(f"\nThis model predicts deal risk from conversation trajectories.")
    print(f"Input: sequence of classifier features per turn")
    print(f"Output: risk score 0.0 (safe) to 1.0 (likely to fail)")


if __name__ == "__main__":
    main()
