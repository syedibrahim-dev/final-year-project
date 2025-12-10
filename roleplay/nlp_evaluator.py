"""
Tier 1 NLP Analyzers for Sales Conversation Evaluation
Fast, rule-based metrics with zero dependencies
"""
import re
from typing import List, Dict, Any


class QuestionAnalyzer:
    """Analyze questions in trainee messages"""
    
    # Question patterns
    WH_WORDS = r'\b(what|how|why|when|where|who|which|whose)\b'
    OPEN_INDICATORS = r'\b(tell me|walk me through|explain|describe|share|talk about)\b'
    CLOSED_INDICATORS = r'\b(do you|are you|is it|can you|will you|would you|have you)\b'
    
    def analyze_questions(self, trainee_messages: List[str]) -> Dict[str, Any]:
        """
        Analyze question quality and quantity
        
        Args:
            trainee_messages: List of text messages from trainee
            
        Returns:
            Dict with question metrics and discovery score
        """
        total_q = 0
        open_q = 0
        closed_q = 0
        
        for msg in trainee_messages:
            # Check if message is a question
            if '?' in msg:
                total_q += 1
                
                # Classify question type
                msg_lower = msg.lower()
                
                # Open question indicators (prioritize)
                if (re.search(self.WH_WORDS, msg_lower, re.IGNORECASE) or
                    re.search(self.OPEN_INDICATORS, msg_lower, re.IGNORECASE)):
                    open_q += 1
                # Closed question indicators  
                elif re.search(self.CLOSED_INDICATORS, msg_lower, re.IGNORECASE):
                    closed_q += 1
                else:
                    # Default to open if ambiguous
                    open_q += 1
        
        open_ratio = open_q / total_q if total_q > 0 else 0
        
        # Scoring logic (0-20 scale)
        score = 0
        
        # Quantity score (max 10 points)
        if total_q >= 6:
            score += 10
        elif total_q >= 4:
            score += 7
        elif total_q >= 2:
            score += 4
        elif total_q >= 1:
            score += 2
        
        # Quality score (max 10 points)
        if open_ratio >= 0.75:
            score += 10  # Mostly open questions
        elif open_ratio >= 0.60:
            score += 7
        elif open_ratio >= 0.40:
            score += 4
        elif open_ratio > 0:
            score += 2
        
        return {
            "total_questions": total_q,
            "open_questions": open_q,
            "closed_questions": closed_q,
            "open_ratio": round(open_ratio, 2),
            "score": min(20, score),
            "interpretation": self._interpret_score(total_q, open_ratio)
        }
    
    def _interpret_score(self, total: int, ratio: float) -> str:
        """Generate human-readable interpretation"""
        if total >= 5 and ratio >= 0.7:
            return "Excellent discovery - many open-ended questions"
        elif total >= 3 and ratio >= 0.5:
            return "Good discovery approach"
        elif total >= 2:
            return "Some discovery, could ask more questions"
        elif total >= 1:
            return "Minimal discovery questioning"
        else:
            return "No discovery questions asked"


class ConversationDynamicsAnalyzer:
    """Analyze conversation balance and flow"""
    
    def analyze_dynamics(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Calculate speaking patterns and balance
        
        Args:
            messages: Full conversation with sender and text
            
        Returns:
            Dict with dynamics metrics and rapport score
        """
        trainee_msgs = [m for m in messages if m['sender'] == 'trainee']
        customer_msgs = [m for m in messages if m['sender'] == 'ai_customer']
        
        if not trainee_msgs or not customer_msgs:
            return {
                "trainee_speaking_ratio": 0.0,
                "score": 5,
                "interpretation": "Insufficient conversation data"
            }
        
        # Word counts
        trainee_words = sum(len(m['text'].split()) for m in trainee_msgs)
        customer_words = sum(len(m['text'].split()) for m in customer_msgs)
        total_words = trainee_words + customer_words
        
        speaking_ratio = trainee_words / total_words if total_words > 0 else 0
        
        # Average message lengths
        avg_trainee_len = trainee_words / len(trainee_msgs)
        avg_customer_len = customer_words / len(customer_msgs)
        
        # Scoring based on balance (0-20 scale)
        # Ideal: 40-60% trainee speaking (balanced)
        score = 0
        if 0.45 <= speaking_ratio <= 0.55:
            score = 20  # Perfect balance
        elif 0.40 <= speaking_ratio <= 0.60:
            score = 17  # Very good balance
        elif 0.35 <= speaking_ratio <= 0.65:
            score = 14  # Acceptable balance
        elif 0.30 <= speaking_ratio <= 0.70:
            score = 10  # Poor balance
        else:
            score = 6   # Very imbalanced
        
        return {
            "trainee_speaking_ratio": round(speaking_ratio, 2),
            "avg_trainee_length": round(avg_trainee_len, 1),
            "avg_customer_length": round(avg_customer_len, 1),
            "turn_count": len(messages),
            "trainee_turns": len(trainee_msgs),
            "score": score,
            "interpretation": self._interpret_balance(speaking_ratio)
        }
    
    def _interpret_balance(self, ratio: float) -> str:
        """Generate human-readable interpretation"""
        if 0.45 <= ratio <= 0.55:
            return "Excellent balance - active listening"
        elif 0.40 <= ratio <= 0.60:
            return "Good conversational balance"
        elif ratio > 0.60:
            return "Speaking too much - listen more"
        elif ratio < 0.40:
            return "Too passive - engage more actively"
        else:
            return "Acceptable balance"


class KeywordAnalyzer:
    """Detect sales-specific keywords and phrases"""
    
    # Sales vocabulary by category
    RAPPORT_KEYWORDS = {
        'appreciate', 'thank you', 'thanks', 'understand', 'hear you',
        'great to', 'pleasure', 'excited', 'looking forward', 'good to'
    }
    
    DISCOVERY_KEYWORDS = {
        'challenge', 'currently', 'pain point', 'goal', 'objective',
        'struggling', 'issue', 'problem', 'need', 'want', 'process',
        'workflow', 'situation', 'experience', 'current', 'now'
    }
    
    VALUE_KEYWORDS = {
        'benefit', 'value', 'roi', 'return', 'save', 'saving',
        'improve', 'increase', 'reduce', 'efficiency', 'productivity',
        'revenue', 'profit', 'cost-effective', 'advantage', 'solution'
    }
    
    OBJECTION_KEYWORDS = {
        'concern', 'worry', 'hesitant', 'unclear', 'understand your',
        'hear that', 'makes sense', 'valid point', 'clarify', 'address'
    }
    
    CLOSING_KEYWORDS = {
        'next step', 'move forward', 'get started', 'schedule', 'demo',
        'trial', 'pilot', 'implementation', 'onboard', 'sign up',
        'commitment', 'timeline', 'follow up', 'meeting'
    }
    
    def analyze_keywords(self, trainee_messages: List[str]) -> Dict[str, Any]:
        """
        Count keyword usage by category
        
        Returns:
            Dict with keyword counts and category scores
        """
        # Combine all messages to lowercase
        full_text = ' '.join(trainee_messages).lower()
        
        # Count matches for each category
        rapport_count = sum(1 for kw in self.RAPPORT_KEYWORDS if kw in full_text)
        discovery_count = sum(1 for kw in self.DISCOVERY_KEYWORDS if kw in full_text)
        value_count = sum(1 for kw in self.VALUE_KEYWORDS if kw in full_text)
        objection_count = sum(1 for kw in self.OBJECTION_KEYWORDS if kw in full_text)
        closing_count = sum(1 for kw in self.CLOSING_KEYWORDS if kw in full_text)
        
        # Score each category (0-20)
        def score_from_count(count: int, excellent: int, good: int, fair: int) -> int:
            """Convert count to score based on thresholds"""
            if count >= excellent:
                return 18
            elif count >= good:
                return 14
            elif count >= fair:
                return 10
            elif count >= 1:
                return 6
            else:
                return 3  # Default minimum
        
        return {
            "rapport_count": rapport_count,
            "discovery_count": discovery_count,
            "value_count": value_count,
            "objection_count": objection_count,
            "closing_count": closing_count,
            "category_scores": {
                "rapport_building": score_from_count(rapport_count, 4, 3, 2),
                "needs_discovery": score_from_count(discovery_count, 6, 4, 2),
                "product_presentation": score_from_count(value_count, 5, 3, 2),
                "objection_handling": score_from_count(objection_count, 3, 2, 1),
                "closing": score_from_count(closing_count, 3, 2, 1)
            }
        }


class NLPEvaluator:
    """Combines all Tier 1 + Tier 2 NLP analyzers"""
    
    def __init__(self, include_tier2: bool = True):
        # Tier 1 (always available - no dependencies)
        self.question_analyzer = QuestionAnalyzer()
        self.dynamics_analyzer = ConversationDynamicsAnalyzer()
        self.keyword_analyzer = KeywordAnalyzer()
        
        # Tier 2 (optional - requires dependencies)
        self.include_tier2 = include_tier2
        if include_tier2:
            try:
                from roleplay.nlp_tier2 import (
                    SentimentAnalyzer,
                    NamedEntityAnalyzer,
                    DialogueActAnalyzer
                )
                self.sentiment_analyzer = SentimentAnalyzer()
                self.ner_analyzer = NamedEntityAnalyzer()
                self.dialogue_analyzer = DialogueActAnalyzer()
                print("✅ Tier 2 NLP analyzers loaded successfully")
            except Exception as e:
                print(f"⚠️ Tier 2 NLP not available: {e}")
                print("   Install: pip install transformers torch spacy")
                print("   Then run: python -m spacy download en_core_web_sm")
                self.include_tier2 = False
    
    def evaluate(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Run all available NLP analyses
        
        Args:
            messages: List of conversation messages with 'sender' and 'text'
        
        Returns:
            Complete NLP evaluation results
        """
        # Extract trainee messages
        trainee_msgs = [m['text'] for m in messages if m['sender'] == 'trainee']
        
        # Tier 1 Analysis (always run)
        question_metrics = self.question_analyzer.analyze_questions(trainee_msgs)
        dynamics_metrics = self.dynamics_analyzer.analyze_dynamics(messages)
        keyword_metrics = self.keyword_analyzer.analyze_keywords(trainee_msgs)
        
        # Tier 2 Analysis (if available)
        tier2_metrics = {}
        if self.include_tier2:
            try:
                sentiment_metrics = self.sentiment_analyzer.analyze_sentiment(messages)
                ner_metrics = self.ner_analyzer.analyze_entities(trainee_msgs)
                dialogue_metrics = self.dialogue_analyzer.analyze_acts(trainee_msgs)
                
                tier2_metrics = {
                    'sentiment': sentiment_metrics,
                    'entities': ner_metrics,
                    'dialogue_acts': dialogue_metrics
                }
            except Exception as e:
                print(f"Tier 2 analysis failed: {e}")
                tier2_metrics = {}
        
        # Combine scores
        category_scores = self._combine_scores(
            question_metrics,
            dynamics_metrics,
            keyword_metrics,
            tier2_metrics
        )
        
        overall_score = sum(category_scores.values())
        
        return {
            "overall_score": overall_score,
            "category_scores": category_scores,
            "detailed_metrics": {
                "tier1": {
                    "questions": question_metrics,
                    "dynamics": dynamics_metrics,
                    "keywords": keyword_metrics
                },
                "tier2": tier2_metrics if tier2_metrics else None
            }
        }
    
    def _combine_scores(
        self, 
        questions: Dict, 
        dynamics: Dict, 
        keywords: Dict,
        tier2: Dict
    ) -> Dict[str, int]:
        """
        Combine Tier 1 + Tier 2 scores into category scores
        
        Tier 1 weight: 60%
        Tier 2 weight: 40% (if available)
        """
        
        # Tier 1 base scores
        tier1_rapport = int(dynamics['score'] * 0.6 + keywords['category_scores']['rapport_building'] * 0.4)
        tier1_discovery = int(questions['score'] * 0.7 + keywords['category_scores']['needs_discovery'] * 0.3)
        tier1_presentation = keywords['category_scores']['product_presentation']
        tier1_objection = keywords['category_scores']['objection_handling']
        tier1_closing = keywords['category_scores']['closing']
        
        # If no Tier 2, return Tier 1 only
        if not tier2:
            return {
                "rapport_building": tier1_rapport,
                "needs_discovery": tier1_discovery,
                "product_presentation": tier1_presentation,
                "objection_handling": tier1_objection,
                "closing": tier1_closing
            }
        
        # Tier 2 contributions
        sentiment = tier2.get('sentiment', {})
        entities = tier2.get('entities', {})
        dialogue = tier2.get('dialogue_acts', {})
        
        # Rapport: Tier 1 (60%) + Sentiment (25%) + Dialogue Acts (15%)
        rapport_tier2 = sentiment.get('rapport_contribution', 0) + dialogue.get('rapport_contribution', 0)
        rapport = int(tier1_rapport * 0.6 + rapport_tier2 * 0.4)
        
        # Discovery: Tier 1 (70%) + Dialogue Acts (30%)
        discovery_tier2 = dialogue.get('discovery_contribution', 0)
        discovery = int(tier1_discovery * 0.7 + discovery_tier2 * 0.3)
        
        # Presentation: Tier 1 (50%) + NER (50%)
        presentation_tier2 = entities.get('presentation_contribution', 0)
        presentation = int(tier1_presentation * 0.5 + presentation_tier2 * 0.5)
        
        # Objection: Mostly Tier 1 (no strong Tier 2 signal)
        objection = tier1_objection
        
        # Closing: Tier 1 (50%) + NER (30%) + Dialogue Acts (20%)
        closing_tier2 = entities.get('closing_contribution', 0) + dialogue.get('closing_contribution', 0)
        closing = int(tier1_closing * 0.5 + closing_tier2 * 0.5)
        
        return {
            "rapport_building": min(20, rapport),
            "needs_discovery": min(20, discovery),
            "product_presentation": min(20, presentation),
            "objection_handling": min(20, objection),
            "closing": min(20, closing)
        }
