"""
Test Conversion Predictor — end-to-end validation.

Run:  D:\\fyp-2026\\venv313\\Scripts\\python.exe test_conversion_predictor.py
"""
import sys
import numpy as np

# ── Test 1: Feature extraction from messages ──
print("=" * 60)
print("  Test 1: Feature extraction from messages")
print("=" * 60)

from conversion.feature_extractor import (
    extract_features_from_messages, NUM_FEATURES, FEATURE_NAMES,
)

mock_messages = [
    {"sender": "trainee", "text": "Hi, how are you? I'm excited to chat about our solution."},
    {"sender": "ai_customer", "text": "Hey, I'm doing well. What do you offer?"},
    {"sender": "trainee", "text": "Tell me about your current challenges with project management?"},
    {"sender": "ai_customer", "text": "We struggle with team coordination and deadlines."},
    {"sender": "trainee", "text": "I understand that challenge. Our platform can help you reduce delays by 30% and improve team efficiency."},
    {"sender": "ai_customer", "text": "That sounds interesting but I'm worried about the cost."},
    {"sender": "trainee", "text": "I hear that concern. Let me explain our ROI — most clients see a 3x return within 6 months. Would you like to schedule a demo?"},
    {"sender": "ai_customer", "text": "Sure, let's set up a demo next week."},
]

features = extract_features_from_messages(mock_messages)
assert features.shape == (NUM_FEATURES,), f"Expected {NUM_FEATURES} features, got {features.shape}"
assert not np.any(np.isnan(features)), "NaN values found in features"
print(f"  ✅ Extracted {NUM_FEATURES} features")
for i, (name, val) in enumerate(zip(FEATURE_NAMES, features)):
    print(f"     {name:25s} = {val:.4f}")


# ── Test 2: ConversionPredictor prediction ──
print("\n" + "=" * 60)
print("  Test 2: ConversionPredictor from messages")
print("=" * 60)

from conversion.predictor import ConversionPredictor

predictor = ConversionPredictor()
assert predictor.is_ready, "Predictor models not loaded! Run train_model.py first."
print("  ✅ Predictor models loaded")

result = predictor.predict_from_messages(mock_messages)
print(f"  Probability:     {result['probability']:.4f}")
print(f"  Confidence:      {result['confidence']:.4f}")
print(f"  XGB Probability: {result['xgb_probability']:.4f}")
print(f"  MLP Probability: {result['mlp_probability']:.4f}")

assert 0.0 <= result['probability'] <= 1.0, "Probability out of range"
assert 0.0 <= result['confidence'] <= 1.0, "Confidence out of range"
print("  ✅ Probability and confidence in valid range")


# ── Test 3: Session-based prediction + turning points ──
print("\n" + "=" * 60)
print("  Test 3: Session-based prediction + turning points")
print("=" * 60)

SESSION_ID = 99999

# Simulate 4 turns of agent results
for turn in range(1, 5):
    mock_agent_results = {
        'eq_data': {
            'eq_score': 60 + turn * 5,
            'sentiment_compound': 0.2 + turn * 0.1,
            'empathy_signals': turn,
            'pushy_signals': 0,
        },
        'accuracy_data': {
            'claims_found': turn,
            'claims_verified': turn - 1,
        },
        'stage_info': {
            'current_stage': ['opening', 'discovery', 'presentation', 'closing'][turn - 1],
            'progress_pct': turn * 25,
        },
    }
    
    result = predictor.predict_from_agent_results(
        session_id=SESSION_ID,
        agent_results=mock_agent_results,
        turn_number=turn,
    )
    print(f"  Turn {turn}: prob={result['probability']:.4f}, conf={result['confidence']:.4f}, trend={result['trend']}")

# Get session trajectory
trajectory = predictor.get_session_trajectory(SESSION_ID)
print(f"\n  Session trajectory: {trajectory['probabilities']}")
print(f"  Turning points: {trajectory['turning_points']}")
print(f"  Overall trend: {trajectory['overall_trend']}")
print(f"  Total turns:   {trajectory['total_turns_analyzed']}")

assert trajectory['total_turns_analyzed'] == 4, "Expected 4 turns"
assert len(trajectory['probabilities']) == 4, "Expected 4 probabilities"
print("  ✅ Session tracking works correctly")

# Clean up
predictor.clear_session(SESSION_ID)


# ── Test 4: Default response when models not loaded ──
print("\n" + "=" * 60)
print("  Test 4: Default response (graceful degradation)")
print("=" * 60)

empty_predictor = ConversionPredictor.__new__(ConversionPredictor)
empty_predictor._loaded = False
empty_predictor._sessions = {}

default = empty_predictor._default_response()
assert default['probability'] == 0.5
assert default['confidence'] == 0.0
assert default['model_not_loaded'] == True
print("  ✅ Graceful degradation works (returns 0.5 probability)")


# ── Summary ──
print("\n" + "=" * 60)
print("  ✅ ALL TESTS PASSED")
print("=" * 60)
