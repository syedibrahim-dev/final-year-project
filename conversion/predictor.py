"""
Real-Time Conversion Predictor
Inspired by SalesRLAgent (arXiv:2503.23303) — Sections IV-B, IV-C

Provides:
  - Turn-by-turn conversion probability (0–1)
  - Meta-learning confidence estimation (KNN + ensemble + temporal)
  - Turning point detection (significant probability shifts)

Usage:
    predictor = ConversionPredictor()
    result = predictor.predict(agent_results, turn_number=3)
    # → {"probability": 0.62, "confidence": 0.85, "trend": "improving", ...}
"""

import pickle
import logging
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional

import xgboost as xgb

from conversion.feature_extractor import (
    extract_features_from_agent_results,
    extract_features_from_messages,
    NUM_FEATURES,
)

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"

# Turning point threshold: a probability shift > this = significant
TURNING_POINT_THRESHOLD = 0.12


class ConversionPredictor:
    """
    Real-time conversion probability predictor.
    
    Maintains per-session state to track probability evolution,
    detect turning points, and provide confidence estimates.
    
    Based on: SalesRLAgent (arXiv:2503.23303)
      - Sequential state tracking (Section III-C)
      - Policy network → probability estimation (Section IV-B)
      - Meta-learning confidence (Section IV-C)
    """
    
    def __init__(self):
        self._loaded = False
        self._xgb_model = None
        self._mlp_model = None
        self._scaler = None
        self._knn = None
        
        # Per-session state (session_id → state)
        self._sessions: Dict[int, dict] = {}
        
        # Try to load models
        self._load_models()
    
    def _load_models(self):
        """Load trained models from disk."""
        xgb_path = MODEL_DIR / "xgb_model.json"
        mlp_path = MODEL_DIR / "mlp_model.pkl"
        scaler_path = MODEL_DIR / "scaler.pkl"
        knn_path = MODEL_DIR / "knn_index.pkl"
        
        if not xgb_path.exists():
            logger.warning(
                "⚠️ Conversion predictor models not found. "
                "Run 'python -m conversion.data_prep' then "
                "'python -m conversion.train_model' first."
            )
            return
        
        try:
            # XGBoost
            self._xgb_model = xgb.XGBClassifier()
            self._xgb_model.load_model(str(xgb_path))
            
            # MLP
            with open(mlp_path, 'rb') as f:
                self._mlp_model = pickle.load(f)
            
            # Scaler
            with open(scaler_path, 'rb') as f:
                self._scaler = pickle.load(f)
            
            # KNN for confidence
            with open(knn_path, 'rb') as f:
                self._knn = pickle.load(f)
            
            self._loaded = True
            logger.info("✅ Conversion predictor models loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load conversion models: {e}")
            self._loaded = False
    
    @property
    def is_ready(self) -> bool:
        """Whether models are loaded and ready for prediction."""
        return self._loaded
    
    # ── Main prediction methods ─────────────────────────────────────
    
    def predict_from_agent_results(
        self,
        session_id: int,
        agent_results: Dict[str, Any],
        turn_number: int,
    ) -> Dict[str, Any]:
        """
        Predict conversion probability from live orchestrator agent results.
        This is the primary method called during roleplay.
        
        Args:
            session_id: current roleplay session ID
            agent_results: dict with eq_data, accuracy_data, stage_info, etc.
            turn_number: current message number in session
        
        Returns:
            {
                "probability": 0.62,
                "confidence": 0.85,
                "trend": "improving",
                "turning_points": [...],
                "momentum": 0.05,
            }
        """
        if not self._loaded:
            return self._default_response()
        
        # Initialize session state if needed
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                'probabilities': [],
                'features': [],
                'sentiments': [],
            }
        
        state = self._sessions[session_id]
        
        # Extract features
        features = extract_features_from_agent_results(
            agent_results=agent_results,
            turn_number=turn_number,
            sentiment_history=state['sentiments'],
            probability_history=state['probabilities'],
        )
        
        # Get prediction
        result = self._predict(features)
        
        # Update session state
        state['probabilities'].append(result['probability'])
        state['features'].append(features)
        
        # Track sentiment for slope calculation
        eq_data = agent_results.get('eq_data') or {}
        state['sentiments'].append(eq_data.get('sentiment_compound', 0.0))
        
        # Detect turning points
        result['turning_points'] = self._detect_turning_points(
            state['probabilities']
        )
        
        # Calculate trend
        result['trend'] = self._calculate_trend(state['probabilities'])
        result['momentum'] = self._calculate_momentum(state['probabilities'])
        result['turn_number'] = turn_number
        
        return result
    
    def predict_from_messages(
        self,
        messages: List[Dict[str, str]],
        expected_length: int = 12,
    ) -> Dict[str, Any]:
        """
        Predict conversion probability from raw message list.
        Used for batch evaluation or testing.
        """
        if not self._loaded:
            return self._default_response()
        
        features = extract_features_from_messages(
            messages, turn_index=-1, expected_length=expected_length,
        )
        return self._predict(features)
    
    # ── Core prediction logic ───────────────────────────────────────
    
    def _predict(self, features: np.ndarray) -> Dict[str, Any]:
        """
        Run ensemble prediction + confidence estimation.
        
        Based on: SalesRLAgent Section IV-B (Model Architecture)
        """
        # Scale features
        scaled = self._scaler.transform(features.reshape(1, -1))
        
        # Get probabilities from both models
        xgb_prob = float(self._xgb_model.predict_proba(scaled)[0][1])
        mlp_prob = float(self._mlp_model.predict_proba(scaled)[0][1])
        
        # Ensemble: average
        ensemble_prob = (xgb_prob + mlp_prob) / 2.0
        
        # Confidence estimation
        confidence = self._estimate_confidence(scaled, xgb_prob, mlp_prob)
        
        return {
            'probability': round(ensemble_prob, 4),
            'confidence': round(confidence, 4),
            'xgb_probability': round(xgb_prob, 4),
            'mlp_probability': round(mlp_prob, 4),
        }
    
    def _estimate_confidence(
        self, scaled_features: np.ndarray,
        xgb_prob: float, mlp_prob: float,
    ) -> float:
        """
        Meta-learning confidence estimation.
        
        Based on: SalesRLAgent Section IV-C
        
        Three signals:
          1. KNN distance to training data (familiarity)
          2. Ensemble agreement (model consensus)
          3. Prediction extremity (extreme predictions → higher confidence)
        """
        # 1. KNN distance — how similar is this to training data?
        try:
            distances, _ = self._knn.kneighbors(scaled_features, return_distance=True)
            avg_distance = float(np.mean(distances[0]))
            similarity = 1.0 / (1.0 + avg_distance)
        except Exception:
            similarity = 0.5
        
        # 2. Ensemble agreement — do both models agree?
        disagreement = abs(xgb_prob - mlp_prob)
        agreement = 1.0 - min(1.0, disagreement * 2)  # scale: 0.5 diff → 0 agreement
        
        # 3. Prediction extremity — extreme predictions are more confident
        ensemble_prob = (xgb_prob + mlp_prob) / 2.0
        extremity = abs(ensemble_prob - 0.5) * 2  # 0 at 0.5, 1 at 0.0/1.0
        
        # Weighted combination
        confidence = (
            similarity * 0.35     # How familiar is this conversation?
            + agreement * 0.45    # Do models agree?
            + extremity * 0.20    # How decisive is the prediction?
        )
        
        return max(0.0, min(1.0, confidence))
    
    # ── Turning point detection ─────────────────────────────────────
    
    def _detect_turning_points(
        self, probabilities: List[float],
    ) -> List[Dict[str, Any]]:
        """
        Identify conversation turning points — moments where
        probability shifted dramatically.
        
        Based on: SalesRLAgent Section VI-B
        "Sales conversations often pivot on specific exchanges"
        """
        if len(probabilities) < 2:
            return []
        
        turning_points = []
        for i in range(1, len(probabilities)):
            delta = probabilities[i] - probabilities[i - 1]
            if abs(delta) > TURNING_POINT_THRESHOLD:
                turning_points.append({
                    'turn': i,
                    'delta': round(delta, 4),
                    'direction': 'positive' if delta > 0 else 'negative',
                    'probability_before': round(probabilities[i - 1], 4),
                    'probability_after': round(probabilities[i], 4),
                })
        
        return turning_points
    
    def _calculate_trend(self, probabilities: List[float]) -> str:
        """Calculate overall probability trend."""
        if len(probabilities) < 2:
            return 'neutral'
        
        recent = probabilities[-3:] if len(probabilities) >= 3 else probabilities
        if recent[-1] > recent[0] + 0.05:
            return 'improving'
        elif recent[-1] < recent[0] - 0.05:
            return 'declining'
        return 'stable'
    
    def _calculate_momentum(self, probabilities: List[float]) -> float:
        """Calculate momentum (rate of change)."""
        if len(probabilities) < 2:
            return 0.0
        return round(probabilities[-1] - probabilities[-2], 4)
    
    # ── Session management ──────────────────────────────────────────
    
    def get_session_trajectory(self, session_id: int) -> Dict[str, Any]:
        """Get the full probability trajectory for a session."""
        state = self._sessions.get(session_id, {})
        probabilities = state.get('probabilities', [])
        
        return {
            'probabilities': probabilities,
            'turning_points': self._detect_turning_points(probabilities),
            'overall_trend': self._calculate_trend(probabilities),
            'final_probability': probabilities[-1] if probabilities else 0.5,
            'total_turns_analyzed': len(probabilities),
        }
    
    def clear_session(self, session_id: int):
        """Clear session state (called when session ends)."""
        self._sessions.pop(session_id, None)
    
    def _default_response(self) -> Dict[str, Any]:
        """Return when models aren't loaded."""
        return {
            'probability': 0.5,
            'confidence': 0.0,
            'trend': 'unknown',
            'turning_points': [],
            'momentum': 0.0,
            'model_not_loaded': True,
        }


# ── Module-level singleton ──────────────────────────────────────────

_predictor_instance: Optional[ConversionPredictor] = None


def get_predictor() -> ConversionPredictor:
    """Get or create the global ConversionPredictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = ConversionPredictor()
    return _predictor_instance
