"""
Embedding Feature Extractor for Conversion Prediction
Uses sentence-transformers (all-MiniLM-L6-v2) to generate dense 384-dim 
embeddings from conversation text.

These embeddings capture semantic meaning that keyword-based features miss.
"""

import numpy as np
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded model (80MB download on first use)
_model = None
EMBEDDING_DIM = 384
EMBEDDING_FEATURE_COUNT = EMBEDDING_DIM + 4  # 384 + 4 derived = 388


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Model loaded.")
        except ImportError:
            logger.warning("sentence-transformers not installed. pip install sentence-transformers")
            return None
    return _model


def extract_embedding_features(messages: List[Dict], turn_index: int = -1) -> Optional[np.ndarray]:
    """
    Extract embedding-based features from a conversation.
    
    Returns a feature vector of size EMBEDDING_FEATURE_COUNT (388):
      - 384: conversation embedding (all messages up to turn_index)
      - 1:   cosine similarity between trainee and customer embeddings
      - 1:   embedding magnitude (conversation intensity proxy)
      - 1:   customer embedding magnitude
      - 1:   trainee embedding magnitude
    
    Args:
        messages: List of {"sender": ..., "text": ...} dicts
        turn_index: Extract features up to this turn (-1 for all)
    """
    model = _get_model()
    if model is None:
        return None
    
    if turn_index == -1:
        turn_index = len(messages) - 1
    
    # Get messages up to turn_index
    msgs_subset = messages[:turn_index + 1]
    
    if not msgs_subset:
        return np.zeros(EMBEDDING_FEATURE_COUNT, dtype=np.float32)
    
    # Separate by speaker
    trainee_texts = []
    customer_texts = []
    all_texts = []
    
    for m in msgs_subset:
        text = m.get('text', '')
        sender = m.get('sender', '')
        all_texts.append(text)
        
        if sender == 'trainee':
            trainee_texts.append(text)
        elif sender == 'ai_customer':
            customer_texts.append(text)
    
    # Create combined texts
    full_text = " ".join(all_texts)
    trainee_text = " ".join(trainee_texts) if trainee_texts else ""
    customer_text = " ".join(customer_texts) if customer_texts else ""
    
    # Encode all three at once for efficiency
    texts_to_encode = [full_text, trainee_text, customer_text]
    embeddings = model.encode(texts_to_encode, show_progress_bar=False, normalize_embeddings=True)
    
    conv_emb = embeddings[0]     # 384-dim
    trainee_emb = embeddings[1]  # 384-dim
    customer_emb = embeddings[2] # 384-dim
    
    # Derived features
    # Cosine similarity (already normalized, so dot product = cosine sim)
    cos_sim = float(np.dot(trainee_emb, customer_emb))
    
    # Magnitudes (before normalization — encode again without normalize)
    conv_mag = float(np.linalg.norm(conv_emb))
    trainee_mag = float(np.linalg.norm(trainee_emb))  
    customer_mag = float(np.linalg.norm(customer_emb))
    
    # Combine: 384 embedding + 4 derived = 388 features
    features = np.concatenate([
        conv_emb.astype(np.float32),          # 384
        np.array([cos_sim, conv_mag, trainee_mag, customer_mag], dtype=np.float32),  # 4
    ])
    
    return features


def batch_extract_embeddings(conversations: List[Dict], multi_turn: bool = True) -> tuple:
    """
    Extract embedding features for a batch of conversations.
    More efficient than calling extract_embedding_features one-by-one.
    
    Returns: (X_embeddings, indices) where indices maps back to conversations.
    """
    model = _get_model()
    if model is None:
        return None, None
    
    # Collect all texts to encode in one batch
    all_items = []  # (conv_idx, turn_idx, full_text, trainee_text, customer_text)
    
    for conv_idx, conv in enumerate(conversations):
        msgs = conv['messages']
        
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
            subset = msgs[:turn_idx + 1]
            trainee = " ".join(m['text'] for m in subset if m.get('sender') == 'trainee')
            customer = " ".join(m['text'] for m in subset if m.get('sender') == 'ai_customer')
            full = " ".join(m['text'] for m in subset)
            all_items.append((conv_idx, turn_idx, full, trainee, customer))
    
    if not all_items:
        return np.array([]), []
    
    # Batch encode ALL texts at once (much faster)
    print(f"   Encoding {len(all_items)*3} texts with sentence-transformers...")
    texts = []
    for _, _, full, trainee, customer in all_items:
        texts.extend([full, trainee or "none", customer or "none"])
    
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True, batch_size=64)
    
    # Build feature matrix
    X = np.zeros((len(all_items), EMBEDDING_FEATURE_COUNT), dtype=np.float32)
    
    for i, (conv_idx, turn_idx, _, _, _) in enumerate(all_items):
        conv_emb = embeddings[i * 3]
        trainee_emb = embeddings[i * 3 + 1]
        customer_emb = embeddings[i * 3 + 2]
        
        cos_sim = float(np.dot(trainee_emb, customer_emb))
        X[i, :384] = conv_emb
        X[i, 384] = cos_sim
        X[i, 385] = float(np.linalg.norm(conv_emb))
        X[i, 386] = float(np.linalg.norm(trainee_emb))
        X[i, 387] = float(np.linalg.norm(customer_emb))
    
    indices = [(item[0], item[1]) for item in all_items]
    return X, indices
