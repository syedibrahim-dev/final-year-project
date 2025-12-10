"""
Tier 2 NLP Analyzers for Sales Conversation Evaluation
Requires: transformers, spacy
"""
from typing import List, Dict, Any
import re


class SentimentAnalyzer:
    """Analyze emotional tone using transformer model"""
    
    def __init__(self):
        try:
            from transformers import pipeline
            # Use lightweight sentiment model
            self.sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                device=-1  # CPU
            )
        except ImportError:
            print("⚠️ transformers not installed. Sentiment analysis will be disabled.")
            self.sentiment_pipeline = None
    
    def analyze_sentiment(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analyze sentiment trajectory throughout conversation
        
        Returns:
            {
                'trainee_avg_sentiment': 0.72,
                'sentiment_trend': 'improving',
                'early_sentiment': 0.68,
                'late_sentiment': 0.76,
                'rapport_contribution': 5
            }
        """
        if not self.sentiment_pipeline:
            return {'trainee_avg_sentiment': 0.5, 'rapport_contribution': 0, 'sentiment_trend': 'unknown'}
        
        trainee_msgs = [m['text'] for m in messages if m['sender'] == 'trainee']
        
        if not trainee_msgs:
            return {'trainee_avg_sentiment': 0.5, 'rapport_contribution': 0}
        
        # Analyze each message
        sentiments = []
        for msg in trainee_msgs:
            # Truncate to 512 chars for model
            result = self.sentiment_pipeline(msg[:512])[0]
            
            # Convert to 0-1 scale (0=negative, 0.5=neutral, 1=positive)
            if result['label'] in ['POSITIVE', 'POS', 'positive']:
                score = 0.5 + (result['score'] * 0.5)
            elif result['label'] in ['NEGATIVE', 'NEG', 'negative']:
                score = 0.5 - (result['score'] * 0.5)
            else:  # NEUTRAL
                score = 0.5
            
            sentiments.append(score)
        
        # Calculate metrics
        avg_sentiment = sum(sentiments) / len(sentiments)
        
        # Trajectory (early vs late)
        split_point = max(1, len(sentiments) // 3)
        early_sentiment = sum(sentiments[:split_point]) / split_point if split_point > 0 else avg_sentiment
        late_sentiment = sum(sentiments[-split_point:]) / split_point if split_point > 0 else avg_sentiment
        
        if late_sentiment > early_sentiment + 0.1:
            trend = "improving"
        elif late_sentiment < early_sentiment - 0.1:
            trend = "declining"
        else:
            trend = "stable"
        
        # Score contribution to rapport (0-8 points)
        rapport_contribution = 0
        if early_sentiment > 0.65:
            rapport_contribution += 3  # Started positive
        if avg_sentiment > 0.60:
            rapport_contribution += 3  # Overall positive
        if trend == "improving":
            rapport_contribution += 2  # Got better
        
        return {
            'trainee_avg_sentiment': round(avg_sentiment, 2),
            'sentiment_trend': trend,
            'early_sentiment': round(early_sentiment, 2),
            'late_sentiment': round(late_sentiment, 2),
            'rapport_contribution': min(8, rapport_contribution)
        }


class NamedEntityAnalyzer:
    """Extract concrete facts using spaCy NER"""
    
    def __init__(self):
        try:
            import spacy
            # Load small English model
            self.nlp = spacy.load("en_core_web_sm")
        except (ImportError, OSError):
            print("⚠️ spaCy not installed or model not downloaded. Run: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    def analyze_entities(self, trainee_messages: List[str]) -> Dict[str, Any]:
        """
        Extract and count named entities
        
        Returns:
            {
                'entity_counts': {'MONEY': 2, 'PERCENT': 3, 'DATE': 2, ...},
                'entities': [('$199', 'MONEY'), ('30%', 'PERCENT'), ...],
                'presentation_contribution': 6,
                'closing_contribution': 4
            }
        """
        if not self.nlp:
            return {'entity_counts': {}, 'entities': [], 'presentation_contribution': 0, 'closing_contribution': 0}
        
        # Combine all trainee messages
        full_text = ' '.join(trainee_messages)
        doc = self.nlp(full_text)
        
        # Extract entities
        entity_counts = {
            'MONEY': 0,
            'PERCENT': 0,
            'DATE': 0,
            'TIME': 0,
            'CARDINAL': 0,
            'ORG': 0
        }
        
        entities_list = []
        for ent in doc.ents:
            if ent.label_ in entity_counts:
                entity_counts[ent.label_] += 1
                entities_list.append((ent.text, ent.label_))
        
        # Presentation scoring: Value quantification
        value_entities = entity_counts['PERCENT'] + entity_counts['MONEY'] + entity_counts['TIME']
        if value_entities >= 5:
            presentation_contribution = 8  # Highly specific
        elif value_entities >= 3:
            presentation_contribution = 6  # Good specificity
        elif value_entities >= 1:
            presentation_contribution = 4  # Some specificity
        else:
            presentation_contribution = 0  # Too vague
        
        # Closing scoring: Timeline mentioned
        timeline_entities = entity_counts['DATE']
        if timeline_entities >= 2:
            closing_contribution = 6  # Clear timeline
        elif timeline_entities >= 1:
            closing_contribution = 4  # Some timeline
        else:
            closing_contribution = 0  # No timeline
        
        return {
            'entity_counts': entity_counts,
            'entities': entities_list[:10],  # Return first 10 for display
            'total_entities': sum(entity_counts.values()),
            'presentation_contribution': presentation_contribution,
            'closing_contribution': closing_contribution
        }


class DialogueActAnalyzer:
    """Classify dialogue acts using rule-based approach"""
    
    def classify_act(self, message: str) -> str:
        """Classify a single message into dialogue act"""
        msg_lower = message.lower()
        
        # Question detection (highest priority)
        if '?' in message:
            # Open questions
            if any(w in msg_lower for w in ['what', 'how', 'why', 'when', 'where', 'who', 'which']):
                return 'OPEN_QUESTION'
            # Closed questions
            elif any(w in msg_lower for w in ['do you', 'are you', 'can you', 'could you', 'would you', 'will you', 'have you', 'is it', 'does it']):
                return 'CLOSED_QUESTION'
            else:
                return 'QUESTION'
        
        # Acknowledgment
        elif any(phrase in msg_lower for phrase in ['i understand', 'i see', 'makes sense', 'i hear', 'got it', 'that makes sense']):
            return 'ACKNOWLEDGMENT'
        
        # Offer/Proposal
        elif any(phrase in msg_lower for phrase in ['would you like', 'should we', 'let me show', 'can i show', 'want to see', 'interested in']):
            return 'OFFER'
        
        # Commitment
        elif any(phrase in msg_lower for phrase in ["i'll", "i will", "we'll", "we will", "let me send", "i can send"]):
            return 'COMMITMENT'
        
        # Greeting/Appreciation
        elif any(phrase in msg_lower for phrase in ['thank', 'appreciate', 'pleasure', 'great to', 'nice to', 'good to']):
            return 'GREETING'
        
        # Imperative (requests)
        elif any(phrase in msg_lower for phrase in ['tell me', 'walk me through', 'explain', 'describe', 'show me']):
            return 'REQUEST'
        
        # Default: Statement
        else:
            return 'STATEMENT'
    
    def analyze_acts(self, trainee_messages: List[str]) -> Dict[str, Any]:
        """
        Analyze dialogue act distribution
        
        Returns:
            {
                'act_counts': {'OPEN_QUESTION': 3, 'ACKNOWLEDGMENT': 2, ...},
                'act_distribution': [...],
                'discovery_contribution': 7,
                'rapport_contribution': 5,
                'closing_contribution': 4
            }
        """
        # Classify each message
        acts = [self.classify_act(msg) for msg in trainee_messages]
        
        # Count acts
        act_counts = {
            'OPEN_QUESTION': acts.count('OPEN_QUESTION'),
            'CLOSED_QUESTION': acts.count('CLOSED_QUESTION'),
            'QUESTION': acts.count('QUESTION'),
            'ACKNOWLEDGMENT': acts.count('ACKNOWLEDGMENT'),
            'OFFER': acts.count('OFFER'),
            'COMMITMENT': acts.count('COMMITMENT'),
            'GREETING': acts.count('GREETING'),
            'REQUEST': acts.count('REQUEST'),
            'STATEMENT': acts.count('STATEMENT')
        }
        
        total_msgs = len(acts) if acts else 1
        
        # Discovery: Question ratio
        total_questions = act_counts['OPEN_QUESTION'] + act_counts['CLOSED_QUESTION'] + act_counts['QUESTION']
        question_ratio = total_questions / total_msgs
        
        if question_ratio >= 0.40:
            discovery_contribution = 8  # Lots of discovery
        elif question_ratio >= 0.25:
            discovery_contribution = 6  # Good discovery
        elif question_ratio >= 0.15:
            discovery_contribution = 4  # Some discovery
        else:
            discovery_contribution = 0  # Minimal discovery
        
        # Rapport: Acknowledgments + Greetings
        rapport_acts = act_counts['ACKNOWLEDGMENT'] + act_counts['GREETING']
        if rapport_acts >= 3:
            rapport_contribution = 6  # Professional & empathetic
        elif rapport_acts >= 2:
            rapport_contribution = 4
        elif rapport_acts >= 1:
            rapport_contribution = 2
        else:
            rapport_contribution = 0
        
        # Closing: Offers + Commitments
        closing_acts = act_counts['OFFER'] + act_counts['COMMITMENT']
        if closing_acts >= 2:
            closing_contribution = 6  # Clear call to action
        elif closing_acts >= 1:
            closing_contribution = 4
        else:
            closing_contribution = 0
        
        return {
            'act_counts': act_counts,
            'act_distribution': acts,
            'question_ratio': round(question_ratio, 2),
            'discovery_contribution': discovery_contribution,
            'rapport_contribution': rapport_contribution,
            'closing_contribution': closing_contribution
        }
