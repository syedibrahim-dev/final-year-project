"""
LSTM Conversation Risk Model — real-time inference.

Takes a sequence of classifier outputs (one per turn) and returns
a risk score (0.0 = safe, 1.0 = deal likely to fail).

Usage:
    from training.lstm_inference import predict_conversation_risk

    risk = predict_conversation_risk(turn_features_list)
    # risk = {"score": 0.72, "label": "high_risk", "trend": "rising", ...}
"""

import os
import logging
import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "lstm_risk_model")

_model = None
_model_config = None

# Feature encoding maps (must match build_lstm_sequences.py)
STATE_LABELS = ["decision", "drop_off_risk", "evaluation", "interest", "objection", "trust"]
WILL_LABELS = ["disengaged", "engaged", "neutral"]
OBJ_LABELS = ["not_objection", "objection_authority", "objection_need", "objection_price",
              "objection_timing", "objection_trust", "objection_value"]
EMO_LABELS = ["anxious", "consultative", "demanding", "empathetic", "negative", "neutral", "positive", "urgent"]


class ConversationLSTM(nn.Module):
    def __init__(self, input_dim=27, hidden_dim=64, num_layers=2, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x, seq_lens):
        packed = nn.utils.rnn.pack_padded_sequence(
            x, seq_lens.cpu().clamp(min=1), batch_first=True, enforce_sorted=False
        )
        _, (hidden, _) = self.lstm(packed)
        final_hidden = hidden[-1]
        return self.classifier(final_hidden).squeeze(-1)


def _load_model():
    global _model, _model_config
    if _model is not None:
        return _model, _model_config

    model_path = os.path.join(MODEL_DIR, "model.pt")
    if not os.path.exists(model_path):
        logger.warning(f"LSTM risk model not found at {model_path}")
        return None, None

    checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
    config = {
        "input_dim": checkpoint.get("input_dim", 27),
        "hidden_dim": checkpoint.get("hidden_dim", 64),
        "num_layers": checkpoint.get("num_layers", 2),
    }

    model = ConversationLSTM(**config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    _model = model
    _model_config = config
    logger.info(f"LSTM risk model loaded (AUC: {checkpoint.get('val_auc', 'N/A')})")
    return model, config


def _encode_label(label, label_list):
    vec = [0.0] * len(label_list)
    if label in label_list:
        vec[label_list.index(label)] = 1.0
    return vec


def encode_turn(state, willingness, objection, emotion, position, obj_resolved=False, is_customer=True):
    """Encode a single turn's classifier outputs into a feature vector."""
    features = []
    features.extend(_encode_label(state, STATE_LABELS))
    features.extend(_encode_label(willingness, WILL_LABELS))
    features.extend(_encode_label(objection, OBJ_LABELS))
    features.extend(_encode_label(emotion, EMO_LABELS))
    features.append(float(position))
    features.append(1.0 if obj_resolved else 0.0)
    features.append(1.0 if is_customer else 0.0)
    return features


def predict_conversation_risk(turn_features_list):
    """
    Predict deal risk from a sequence of turn feature vectors.

    Args:
        turn_features_list: List of feature vectors (from encode_turn()),
                           one per turn so far.

    Returns:
        {
            "risk_score": float (0.0-1.0, higher = more likely to fail),
            "risk_label": "low" | "medium" | "high",
            "trend": "stable" | "rising" | "falling",
            "source": "lstm_sequence_model"
        }
    """
    model, config = _load_model()
    if model is None:
        return {
            "risk_score": 0.5,
            "risk_label": "unknown",
            "trend": "stable",
            "source": "unavailable",
        }

    seq_len = len(turn_features_list)
    if seq_len == 0:
        return {"risk_score": 0.5, "risk_label": "unknown", "trend": "stable", "source": "lstm_sequence_model"}

    # Pad to 30
    feat_dim = config["input_dim"]
    padded = np.zeros((1, 30, feat_dim), dtype=np.float32)
    actual_len = min(seq_len, 30)
    for i in range(actual_len):
        padded[0, i] = turn_features_list[i][:feat_dim]

    with torch.no_grad():
        features_tensor = torch.tensor(padded, dtype=torch.float32)
        seq_lens_tensor = torch.tensor([actual_len], dtype=torch.long)
        logit = model(features_tensor, seq_lens_tensor)
        # Model predicts outcome (1=converted), so risk = 1 - P(converted)
        conversion_prob = torch.sigmoid(logit).item()
        risk_score = round(1.0 - conversion_prob, 4)

    # Risk label
    if risk_score < 0.35:
        risk_label = "low"
    elif risk_score < 0.65:
        risk_label = "medium"
    else:
        risk_label = "high"

    # Trend detection (compare current risk to risk at 2 turns ago)
    trend = "stable"
    if seq_len >= 4:
        prev_features = turn_features_list[:seq_len - 2]
        prev_padded = np.zeros((1, 30, feat_dim), dtype=np.float32)
        prev_len = min(len(prev_features), 30)
        for i in range(prev_len):
            prev_padded[0, i] = prev_features[i][:feat_dim]

        with torch.no_grad():
            prev_tensor = torch.tensor(prev_padded, dtype=torch.float32)
            prev_lens = torch.tensor([prev_len], dtype=torch.long)
            prev_logit = model(prev_tensor, prev_lens)
            prev_risk = 1.0 - torch.sigmoid(prev_logit).item()

        diff = risk_score - prev_risk
        if diff > 0.08:
            trend = "rising"
        elif diff < -0.08:
            trend = "falling"

    return {
        "risk_score": risk_score,
        "risk_label": risk_label,
        "trend": trend,
        "source": "lstm_sequence_model",
    }
