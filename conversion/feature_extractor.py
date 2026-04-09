"""
Feature Extractor for Conversion Prediction
Inspired by SalesRLAgent (arXiv:2503.23303) — Section III-C State Representation

Extracts 28 numerical features per conversation turn from:
  1. Dataset conversations (for training)
  2. Live agent results (for real-time prediction)

Features are designed to match the state representation in the paper:
  - Conversation history features (question density, sentiment)
  - Turn-specific features (speaking ratio, message length)
  - Sales technique identification (keywords, sales flow)
  - Objection and interest detection
  - Customer engagement signals (NEW)
  - Conversation dynamics (NEW)
"""

import re
import math
import numpy as np
from typing import List, Dict, Any, Optional

# VADER for sentiment (already a project dependency)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
except ImportError:
    _vader = None


# ── Keyword dictionaries (aligned with nlp_evaluator.py) ───────────

EMPATHY_KEYWORDS = {
    'understand', 'appreciate', 'hear you', 'makes sense', 'valid point',
    'thank you', 'great question', 'absolutely', 'i see', 'that helps',
}
PUSHY_KEYWORDS = {
    'just', 'honestly', 'trust me', 'you need', 'you should', 'obviously',
    'no brainer', 'guarantee', 'promise', 'must have', 'definitely',
}
RAPPORT_KEYWORDS = {
    'appreciate', 'thank you', 'thanks', 'understand', 'hear you',
    'great to', 'pleasure', 'excited', 'looking forward', 'happy to help',
}
DISCOVERY_KEYWORDS = {
    'challenge', 'currently', 'pain point', 'goal', 'objective',
    'tell me', 'how do you', 'walk me through', 'help me understand',
}
VALUE_KEYWORDS = {
    'benefit', 'value', 'roi', 'save', 'improve', 'increase', 'reduce',
    'efficiency', 'solution', 'results', 'outcome', 'advantage',
}
OBJECTION_KEYWORDS = {
    'concern', 'understand your', 'hear that', 'valid point', 'clarify',
    'let me address', 'great question', 'fair point',
}
CLOSING_KEYWORDS = {
    'next step', 'move forward', 'get started', 'schedule', 'demo',
    'trial', 'follow up', 'meeting', 'shall we', 'ready to',
}

# ── NEW: Customer-side keyword dictionaries ─────────────────────────

CUSTOMER_OBJECTION_KEYWORDS = {
    'too expensive', 'not sure', 'concerned', 'worried', 'budget',
    'already have', 'competitor', 'not interested', 'not convinced',
    'think about it', 'not ready', 'too risky', 'no need', 'happy with',
    'can\'t afford', 'don\'t see', 'what about',
}
CUSTOMER_INTEREST_KEYWORDS = {
    'sounds good', 'interesting', 'tell me more', 'how does', 'what if',
    'can you show', 'demo', 'pricing', 'next steps', 'when can',
    'impressed', 'like that', 'makes sense', 'definitely', 'great',
    'love to', 'want to', 'need this', 'sign up',
}
URGENCY_KEYWORDS = {
    'asap', 'deadline', 'urgent', 'quickly', 'soon', 'immediately',
    'right away', 'this week', 'this month', 'time sensitive',
    'running out', 'before', 'end of quarter',
}

# Sales stage mapping
STAGE_MAP = {
    'opening': 0, 'discovery': 1, 'presentation': 2,
    'objection_handling': 3, 'closing': 4,
}
STAGE_KEYWORDS = {
    'opening': {'hello', 'hi', 'hey', 'nice to meet', 'how are you'},
    'discovery': DISCOVERY_KEYWORDS,
    'presentation': VALUE_KEYWORDS,
    'objection_handling': OBJECTION_KEYWORDS,
    'closing': CLOSING_KEYWORDS,
}


# ── Helper functions ────────────────────────────────────────────────

def _count_keywords(text: str, keywords: set) -> int:
    """Count how many keywords appear in text."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


def _is_question(text: str) -> bool:
    return '?' in text


def _is_open_question(text: str) -> bool:
    if not _is_question(text):
        return False
    wh = r'\b(what|how|why|when|where|who|which)\b'
    open_ind = r'\b(tell me|explain|describe|walk me through)\b'
    t = text.lower()
    return bool(re.search(wh, t) or re.search(open_ind, t))


def _count_specifics(text: str) -> int:
    """Count concrete specifics: dollar amounts, percentages, dates."""
    dollars = len(re.findall(r'\$[\d,]+', text))
    pcts = len(re.findall(r'\d+%', text))
    numbers = len(re.findall(r'\b\d{2,}\b', text))
    return dollars + pcts + numbers


def _sentiment_score(text: str) -> float:
    """Get VADER compound sentiment (-1 to 1)."""
    if _vader is None:
        return 0.0
    return _vader.polarity_scores(text)['compound']


def _detect_stage(text: str) -> int:
    """Detect dominant sales stage from text. Returns stage index 0-4."""
    text_lower = text.lower()
    best_stage = 'discovery'  # default
    best_count = 0
    for stage, keywords in STAGE_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > best_count:
            best_count = count
            best_stage = stage
    return STAGE_MAP.get(best_stage, 1)


def _avg_word_count(messages: list) -> float:
    """Average words per message."""
    if not messages:
        return 0.0
    return sum(len(m.split()) for m in messages) / len(messages)


def _substantive_ratio(messages: list) -> float:
    """Ratio of substantive messages (>10 words) vs filler/small-talk."""
    if not messages:
        return 0.0
    substantive = sum(1 for m in messages if len(m.split()) > 10)
    return substantive / len(messages)


# ── Main extraction functions ───────────────────────────────────────

FEATURE_NAMES = [
    # Original 18 features
    'question_rate',          # 0: questions / total trainee messages so far
    'open_question_ratio',    # 1: open questions / total questions
    'empathy_count_norm',     # 2: empathy keywords / message count
    'pushy_count_norm',       # 3: pushy keywords / message count
    'speaking_ratio',         # 4: trainee words / total words
    'avg_trainee_msg_len',    # 5: average words per trainee message
    'rapport_hits',           # 6: rapport keyword hits (normalized)
    'discovery_hits',         # 7: discovery keyword hits (normalized)
    'value_hits',             # 8: value proposition hits (normalized)
    'objection_hits',         # 9: objection handling hits (normalized)
    'closing_hits',           # 10: closing keyword hits (normalized)
    'turn_progress',          # 11: current turn / total expected turns (0-1)
    'sentiment_current',      # 12: VADER sentiment of latest trainee message
    'sentiment_slope',        # 13: linear slope of sentiment over last 5 turns
    'stage_index',            # 14: detected sales stage (0-4)
    'stage_progress_pct',     # 15: how far through the stages (0-1)
    'specifics_count',        # 16: concrete specifics (numbers, $, %)
    'momentum',               # 17: rolling average of recent feature deltas
    # NEW: 10 additional features for improved accuracy
    'customer_sentiment',     # 18: VADER sentiment of latest customer message
    'sentiment_divergence',   # 19: gap between trainee and customer sentiment
    'customer_objection_count',  # 20: objections raised by customer (normalized)
    'customer_interest_count',   # 21: interest signals from customer (normalized)
    'avg_response_length_ratio', # 22: trainee msg length / customer msg length
    'question_response_rate',    # 23: how often trainee answers customer questions
    'conversation_depth',        # 24: ratio of substantive messages
    'urgency_signals',           # 25: urgency keywords detected
    'topic_consistency',         # 26: how consistent the conversation topic is
    'engagement_trend',          # 27: is customer getting more or less engaged?
]

NUM_FEATURES = len(FEATURE_NAMES)


def extract_features_from_messages(
    messages: List[Dict[str, str]],
    turn_index: int = -1,
    expected_length: int = 12,
) -> np.ndarray:
    """
    Extract feature vector from a list of conversation messages.
    
    Args:
        messages: list of {"sender": "trainee"|"ai_customer", "text": "..."}
        turn_index: which turn to compute features for (-1 = latest)
        expected_length: expected conversation length for normalization
    
    Returns:
        np.ndarray of shape (NUM_FEATURES,)
    """
    if turn_index == -1:
        turn_index = len(messages) - 1
    
    # Get messages up to this turn
    msgs_so_far = messages[:turn_index + 1]
    
    trainee_msgs = [m['text'] for m in msgs_so_far if m['sender'] == 'trainee']
    customer_msgs = [m['text'] for m in msgs_so_far if m['sender'] in ('ai_customer', 'customer', 'sales_rep')]
    
    if not trainee_msgs:
        return np.zeros(NUM_FEATURES)
    
    num_trainee = len(trainee_msgs)
    num_customer = max(1, len(customer_msgs))
    all_trainee_text = ' '.join(trainee_msgs)
    all_customer_text = ' '.join(customer_msgs) if customer_msgs else ''
    latest_trainee = trainee_msgs[-1] if trainee_msgs else ""
    latest_customer = customer_msgs[-1] if customer_msgs else ""
    
    # Word counts
    trainee_words = sum(len(m.split()) for m in trainee_msgs)
    customer_words = sum(len(m.split()) for m in customer_msgs)
    total_words = trainee_words + customer_words
    
    # Questions
    total_questions = sum(1 for m in trainee_msgs if _is_question(m))
    open_questions = sum(1 for m in trainee_msgs if _is_open_question(m))
    customer_questions = sum(1 for m in customer_msgs if _is_question(m))
    
    # Sentiment trajectory (trainee)
    trainee_sentiments = [_sentiment_score(m) for m in trainee_msgs]
    recent_sentiments = trainee_sentiments[-5:] if len(trainee_sentiments) >= 2 else trainee_sentiments
    if len(recent_sentiments) >= 2:
        x = np.arange(len(recent_sentiments))
        slope = np.polyfit(x, recent_sentiments, 1)[0]
    else:
        slope = 0.0
    
    # NEW: Customer sentiment trajectory
    customer_sentiments = [_sentiment_score(m) for m in customer_msgs] if customer_msgs else [0.0]
    latest_customer_sentiment = customer_sentiments[-1] if customer_sentiments else 0.0
    latest_trainee_sentiment = trainee_sentiments[-1] if trainee_sentiments else 0.0
    
    # NEW: Customer engagement trend (are they writing more/less?)
    if len(customer_msgs) >= 4:
        first_half_avg = _avg_word_count(customer_msgs[:len(customer_msgs)//2])
        second_half_avg = _avg_word_count(customer_msgs[len(customer_msgs)//2:])
        engagement_trend = (second_half_avg - first_half_avg) / max(1.0, first_half_avg)
    elif len(customer_msgs) >= 2:
        engagement_trend = (len(customer_msgs[-1].split()) - len(customer_msgs[0].split())) / max(1, len(customer_msgs[0].split()))
    else:
        engagement_trend = 0.0
    
    # Stage detection (use recent messages for stage)
    recent_text = ' '.join(trainee_msgs[-3:])
    stage = _detect_stage(recent_text)
    
    # Momentum: compare last 3 sentiments average to previous 3
    if len(trainee_sentiments) >= 6:
        recent_avg = np.mean(trainee_sentiments[-3:])
        prev_avg = np.mean(trainee_sentiments[-6:-3])
        momentum = recent_avg - prev_avg
    elif len(trainee_sentiments) >= 2:
        momentum = trainee_sentiments[-1] - trainee_sentiments[0]
    else:
        momentum = 0.0
    
    # NEW: Topic consistency (how similar are consecutive messages?)
    if len(trainee_msgs) >= 3:
        overlaps = []
        for i in range(1, min(len(trainee_msgs), 5)):
            words_prev = set(trainee_msgs[i-1].lower().split())
            words_curr = set(trainee_msgs[i].lower().split())
            if words_prev and words_curr:
                overlap = len(words_prev & words_curr) / max(1, len(words_prev | words_curr))
                overlaps.append(overlap)
        topic_consistency = np.mean(overlaps) if overlaps else 0.0
    else:
        topic_consistency = 0.0
    
    features = np.array([
        # Original 18 features
        total_questions / max(1, num_trainee),              # question_rate
        open_questions / max(1, total_questions),            # open_question_ratio
        _count_keywords(all_trainee_text, EMPATHY_KEYWORDS) / max(1, num_trainee),
        _count_keywords(all_trainee_text, PUSHY_KEYWORDS) / max(1, num_trainee),
        trainee_words / max(1, total_words),                 # speaking_ratio
        trainee_words / max(1, num_trainee),                 # avg message length
        _count_keywords(all_trainee_text, RAPPORT_KEYWORDS) / max(1, num_trainee),
        _count_keywords(all_trainee_text, DISCOVERY_KEYWORDS) / max(1, num_trainee),
        _count_keywords(all_trainee_text, VALUE_KEYWORDS) / max(1, num_trainee),
        _count_keywords(all_trainee_text, OBJECTION_KEYWORDS) / max(1, num_trainee),
        _count_keywords(all_trainee_text, CLOSING_KEYWORDS) / max(1, num_trainee),
        min(1.0, (turn_index + 1) / max(1, expected_length)),  # turn_progress
        latest_trainee_sentiment,                              # current sentiment
        slope,                                                 # sentiment slope
        stage / 4.0,                                           # stage index (normalized 0-1)
        stage / 4.0,                                           # stage progress pct
        _count_specifics(all_trainee_text) / max(1, num_trainee),
        momentum,                                              # momentum
        # NEW: 10 additional features
        latest_customer_sentiment,                             # customer_sentiment
        latest_trainee_sentiment - latest_customer_sentiment,  # sentiment_divergence
        _count_keywords(all_customer_text, CUSTOMER_OBJECTION_KEYWORDS) / max(1, num_customer),
        _count_keywords(all_customer_text, CUSTOMER_INTEREST_KEYWORDS) / max(1, num_customer),
        (trainee_words / max(1, num_trainee)) / max(1.0, customer_words / max(1, num_customer)),
        customer_questions / max(1, num_customer),             # question_response_rate
        _substantive_ratio(trainee_msgs + customer_msgs),      # conversation_depth
        _count_keywords(all_trainee_text + ' ' + all_customer_text, URGENCY_KEYWORDS) / max(1, num_trainee + num_customer),
        topic_consistency,                                     # topic_consistency
        engagement_trend,                                      # engagement_trend
    ], dtype=np.float32)
    
    return features


def extract_features_from_agent_results(
    agent_results: Dict[str, Any],
    turn_number: int,
    total_expected_turns: int = 12,
    sentiment_history: Optional[List[float]] = None,
    probability_history: Optional[List[float]] = None,
    trainee_message: str = "",
    customer_message: str = "",
) -> np.ndarray:
    """
    Extract feature vector from live orchestrator agent results.
    Used during real-time roleplay for on-the-fly conversion prediction.
    
    Args:
        agent_results: dict with keys from orchestrator (eq_data, accuracy_data, etc.)
        turn_number: current message number in session
        total_expected_turns: expected conversation length
        sentiment_history: list of VADER scores from previous turns
        probability_history: list of previous conversion probabilities
        trainee_message: latest trainee message text (for real-time feature extraction)
        customer_message: latest customer message text (for real-time feature extraction)
    
    Returns:
        np.ndarray of shape (NUM_FEATURES,)
    """
    eq_data = agent_results.get('eq_data') or {}
    accuracy_data = agent_results.get('accuracy_data') or {}
    stage_info = agent_results.get('stage_info') or {}
    
    # Extract EQ scores
    eq_score = eq_data.get('eq_score', 50.0) / 100.0  # normalize to 0-1
    empathy_count = eq_data.get('empathy_signals', 0)
    pushy_count = eq_data.get('pushy_signals', 0)
    
    # Sentiment from EQ
    sentiment_current = eq_data.get('sentiment_compound', 0.0)
    
    # Build sentiment history for slope
    if sentiment_history and len(sentiment_history) >= 2:
        recent = sentiment_history[-5:]
        x = np.arange(len(recent))
        slope = float(np.polyfit(x, recent, 1)[0])
    else:
        slope = 0.0
    
    # Stage info
    stage_name = (stage_info.get('current_stage') or 'discovery').lower()
    stage_idx = STAGE_MAP.get(stage_name, 1)
    progress_pct = stage_info.get('progress_pct', 30) / 100.0
    
    # Knowledge accuracy
    claims_made = accuracy_data.get('claims_found', 0)
    claims_verified = accuracy_data.get('claims_verified', 0)
    
    # Momentum from probability history
    if probability_history and len(probability_history) >= 2:
        momentum = probability_history[-1] - probability_history[-2]
    else:
        momentum = 0.0
    
    # ── NEW: Extract real features from actual messages ──
    trainee_text = trainee_message or ""
    customer_text = customer_message or ""
    
    # Real question rate from trainee message
    question_rate = 1.0 if _is_question(trainee_text) else 0.0
    open_q_ratio = 1.0 if _is_open_question(trainee_text) else 0.0
    
    # Real speaking ratio
    t_words = len(trainee_text.split()) if trainee_text else 25
    c_words = len(customer_text.split()) if customer_text else 25
    speaking_ratio = t_words / max(1, t_words + c_words)
    
    # Real keyword counts from messages
    rapport = _count_keywords(trainee_text, RAPPORT_KEYWORDS)
    discovery = _count_keywords(trainee_text, DISCOVERY_KEYWORDS)
    value = _count_keywords(trainee_text, VALUE_KEYWORDS)
    objection_h = _count_keywords(trainee_text, OBJECTION_KEYWORDS)
    closing = _count_keywords(trainee_text, CLOSING_KEYWORDS)
    
    # Customer sentiment (real)
    customer_sentiment = _sentiment_score(customer_text) if customer_text else 0.0
    
    # Customer engagement signals
    cust_objections = _count_keywords(customer_text, CUSTOMER_OBJECTION_KEYWORDS) if customer_text else 0
    cust_interest = _count_keywords(customer_text, CUSTOMER_INTEREST_KEYWORDS) if customer_text else 0
    
    # Response length ratio
    resp_len_ratio = t_words / max(1.0, c_words)
    
    # Customer question rate
    cust_question_rate = 1.0 if (_is_question(customer_text) if customer_text else False) else 0.0
    
    # Conversation depth
    depth = 1.0 if t_words > 10 else 0.5
    
    # Urgency
    urgency = _count_keywords(trainee_text + ' ' + customer_text, URGENCY_KEYWORDS)
    
    # Topic consistency (can't measure well with single turn, estimate from stage)
    topic_consistency = 0.3 if stage_idx <= 1 else 0.5
    
    # Engagement trend from sentiment history
    if sentiment_history and len(sentiment_history) >= 4:
        first_half = np.mean(sentiment_history[:len(sentiment_history)//2])
        second_half = np.mean(sentiment_history[len(sentiment_history)//2:])
        engagement_trend = second_half - first_half
    else:
        engagement_trend = 0.0
    
    features = np.array([
        # Original 18 features (now using real values where possible)
        question_rate,                                  # question_rate
        open_q_ratio,                                   # open_question_ratio
        empathy_count / max(1, turn_number),            # empathy normalized
        pushy_count / max(1, turn_number),              # pushy normalized
        speaking_ratio,                                 # speaking_ratio (REAL)
        float(t_words),                                 # avg message length (REAL)
        rapport / max(1, turn_number),                  # rapport (REAL)
        discovery / max(1, turn_number),                # discovery (REAL)
        value / max(1, turn_number),                    # value (REAL)
        objection_h / max(1, turn_number),              # objection (REAL)
        closing / max(1, turn_number),                  # closing (REAL)
        min(1.0, turn_number / max(1, total_expected_turns)),
        sentiment_current,
        slope,
        stage_idx / 4.0,
        progress_pct,
        claims_made / max(1, turn_number),
        momentum,
        # NEW: 10 additional features
        customer_sentiment,                              # customer_sentiment
        sentiment_current - customer_sentiment,          # sentiment_divergence
        cust_objections / max(1, turn_number),           # customer_objection_count
        cust_interest / max(1, turn_number),             # customer_interest_count
        resp_len_ratio,                                  # avg_response_length_ratio
        cust_question_rate,                              # question_response_rate
        depth,                                           # conversation_depth
        urgency / max(1, turn_number),                   # urgency_signals
        topic_consistency,                               # topic_consistency
        engagement_trend,                                # engagement_trend
    ], dtype=np.float32)
    
    return features
