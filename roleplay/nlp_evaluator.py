"""
Tier 1 NLP Analyzers for Sales Conversation Evaluation
Fast, rule-based metrics with zero dependencies
Enhanced with: Sales Flow Analysis, Sequence-Aware Scoring, Conversation Length Normalization
"""
import re
import math
from typing import List, Dict, Any


class QuestionAnalyzer:
    """Analyze questions in trainee messages"""

    # Question patterns
    WH_WORDS = r'\b(what|how|why|when|where|who|which|whose)\b'
    OPEN_INDICATORS = r'\b(tell me|walk me through|explain|describe|share|talk about|help me understand)\b'
    CLOSED_INDICATORS = r'\b(do you|are you|is it|can you|will you|would you|have you|did you|has it|does it)\b'

    # Follow-up question patterns (shows active listening)
    FOLLOW_UP_PATTERNS = [
        r"you mentioned.*\?",
        r"can you (tell|explain|elaborate).*\?",
        r"what (do you mean|did you mean).*\?",
        r"how (does|did|would) that.*\?",
        r"why (is|was|do|did).*\?",
        r"could you give.*example.*\?",
        r"interesting.*\?"
    ]

    # SPIN Selling question classification (Rackham, 1988)
    SPIN_PATTERNS = {
        "situation": [
            r'\b(what|how) (do|does|is|are) (your|the|you)\b',  # "What is your current..."
            r'\b(currently|right now|at the moment)\b.*\?',
            r'\b(how many|how much|how long|how often)\b.*\?',
            r'\b(using|use|have|running)\b.*\?',
        ],
        "problem": [
            r'\b(challenge|problem|issue|difficulty|struggle|pain|frustrat|concern|worry)\b.*\?',
            r'\b(what.*(wrong|difficult|challenging|hard))\b.*\?',
            r'\b(any (issues|problems|concerns|challenges))\b',
        ],
        "implication": [
            r'\b(what happens|what would happen|if .* (don.t|doesn.t|can.t))\b.*\?',
            r'\b(impact|affect|consequence|cost of not|risk)\b.*\?',
            r'\b(how (does|would) that (affect|impact|cost))\b',
            r'\b(what does that mean for)\b',
        ],
        "need_payoff": [
            r'\b(would it help|how (would|could) .* (help|benefit|improve|solve))\b',
            r'\b(what if (you|we) could)\b',
            r'\b(imagine|picture|think about|envision)\b.*\?',
            r'\b(value|worth|benefit|advantage)\b.*\b(to you|for you|for your)\b.*\?',
        ],
    }
    
    def analyze_questions(self, trainee_messages: List[str]) -> Dict[str, Any]:
        """
        Analyze question quality, quantity, follow-up behavior, and SPIN classification.
        Normalized by conversation length.
        """
        total_q = 0
        open_q = 0
        closed_q = 0
        follow_up_q = 0

        # SPIN question counts
        spin_counts = {"situation": 0, "problem": 0, "implication": 0, "need_payoff": 0}

        for msg in trainee_messages:
            if '?' in msg:
                total_q += 1
                msg_lower = msg.lower()

                # Check for follow-up patterns
                if any(re.search(pattern, msg_lower) for pattern in self.FOLLOW_UP_PATTERNS):
                    follow_up_q += 1

                # Classify question type
                if (re.search(self.WH_WORDS, msg_lower, re.IGNORECASE) or
                    re.search(self.OPEN_INDICATORS, msg_lower, re.IGNORECASE)):
                    open_q += 1
                elif re.search(self.CLOSED_INDICATORS, msg_lower, re.IGNORECASE):
                    closed_q += 1
                else:
                    open_q += 1  # Default to open

                # SPIN classification — assign to highest-value matching category
                self._classify_spin(msg_lower, spin_counts)

        num_messages = max(1, len(trainee_messages))
        question_rate = total_q / num_messages  # Questions per message
        open_ratio = open_q / total_q if total_q > 0 else 0

        # Scoring logic (0-20 scale) - normalized by conversation length
        score = 0

        # Quantity score (max 8 points) - rate-based instead of absolute
        if question_rate >= 0.5:
            score += 8
        elif question_rate >= 0.35:
            score += 6
        elif question_rate >= 0.2:
            score += 4
        elif question_rate > 0:
            score += 2

        # Quality score (max 8 points) - open question ratio
        if open_ratio >= 0.75:
            score += 8
        elif open_ratio >= 0.60:
            score += 6
        elif open_ratio >= 0.40:
            score += 4
        elif open_ratio > 0:
            score += 2

        # Follow-up bonus (max 4 points) - shows active listening
        if follow_up_q >= 3:
            score += 4
        elif follow_up_q >= 2:
            score += 3
        elif follow_up_q >= 1:
            score += 2

        # Build SPIN analysis
        spin_analysis = {
            "situation": spin_counts["situation"],
            "problem": spin_counts["problem"],
            "implication": spin_counts["implication"],
            "need_payoff": spin_counts["need_payoff"],
            "spin_quality": self._assess_spin_quality(spin_counts)
        }

        return {
            "total_questions": total_q,
            "open_questions": open_q,
            "closed_questions": closed_q,
            "follow_up_questions": follow_up_q,
            "question_rate": round(question_rate, 2),
            "open_ratio": round(open_ratio, 2),
            "spin_analysis": spin_analysis,
            "score": min(20, score),
            "interpretation": self._interpret_score(total_q, open_ratio, follow_up_q)
        }

    def _classify_spin(self, msg_lower: str, spin_counts: Dict[str, int]) -> None:
        """Classify a question into the highest-value SPIN category that matches."""
        # Check in reverse priority order so higher-value categories win
        # Priority: need_payoff > implication > problem > situation
        priority_order = ["need_payoff", "implication", "problem", "situation"]
        for category in priority_order:
            patterns = self.SPIN_PATTERNS[category]
            if any(re.search(pattern, msg_lower) for pattern in patterns):
                spin_counts[category] += 1
                return  # Only count in highest-priority matching category

    def _assess_spin_quality(self, counts: Dict[str, int]) -> str:
        """Assess SPIN question usage quality."""
        total_spin = sum(counts.values())
        if total_spin == 0:
            return "Questions lack SPIN structure — try sequencing: Situation -> Problem -> Implication -> Need-Payoff"

        if counts["implication"] + counts["need_payoff"] >= 2:
            return "Strong SPIN technique — using implication and need-payoff questions to build urgency"

        if counts["problem"] >= 1 and counts["implication"] == 0:
            return "Good problem identification but missing implication questions — ask 'what happens if this isn't fixed?'"

        # Mostly situation questions
        if counts["situation"] >= total_spin * 0.6:
            return "Too many situation questions — move to problem and implication questions sooner"

        return "Questions lack SPIN structure — try sequencing: Situation -> Problem -> Implication -> Need-Payoff"
    
    def _interpret_score(self, total: int, ratio: float, follow_ups: int) -> str:
        if total >= 5 and ratio >= 0.7 and follow_ups >= 2:
            return "Excellent discovery - many open-ended and follow-up questions"
        elif total >= 5 and ratio >= 0.7:
            return "Strong questioning - good use of open-ended questions"
        elif total >= 3 and ratio >= 0.5:
            return "Good discovery approach, could add more follow-up questions"
        elif total >= 2:
            return "Some discovery, needs more probing and open-ended questions"
        elif total >= 1:
            return "Minimal discovery questioning - ask more questions"
        else:
            return "No discovery questions asked - critical gap"


class SalesFlowAnalyzer:
    """
    NEW: Analyze whether the trainee follows proper sales conversation flow.
    Checks: Opening → Discovery → Presentation → Objection Handling → Closing
    """
    
    PHASE_KEYWORDS = {
        "opening": {
            'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'how are you',
            'nice to meet', 'pleasure', 'thank you for', 'thanks for taking'
        },
        "discovery": {
            'tell me', 'what challenges', 'currently', 'pain point', 'goal', 'struggling',
            'issue', 'what do you', 'how do you', 'walk me through', 'help me understand',
            'situation', 'workflow', 'process', 'what are you using'
        },
        "presentation": {
            'benefit', 'value', 'roi', 'save', 'improve', 'solution', 'feature',
            'help you', 'increase', 'reduce', 'efficiency', 'productivity', 'advantage',
            'our product', 'our platform', 'what we offer', 'how it works'
        },
        "objection_handling": {
            'understand your concern', 'hear you', 'valid point', 'makes sense',
            'let me address', 'i understand', 'hear that', 'great question',
            'fair point', 'appreciate your honesty', 'clarify'
        },
        "closing": {
            'next step', 'move forward', 'get started', 'schedule', 'demo',
            'trial', 'pilot', 'follow up', 'meeting', 'commitment', 'timeline',
            'shall we', 'would you like to', 'ready to'
        }
    }
    
    IDEAL_FLOW = ["opening", "discovery", "presentation", "objection_handling", "closing"]
    
    def analyze_flow(self, trainee_messages: List[str]) -> Dict[str, Any]:
        """
        Analyze sales conversation flow quality.
        Returns flow score (0-20) and detected phase sequence.
        """
        if len(trainee_messages) < 3:
            return {
                "detected_phases": [],
                "flow_score": 0,
                "flow_quality": "Too few messages to analyze",
                "phase_coverage": {},
                "missing_phases": self.IDEAL_FLOW.copy()
            }
        
        # Split conversation into thirds and detect dominant phase in each
        third = max(1, len(trainee_messages) // 3)
        segments = {
            "early": trainee_messages[:third],
            "middle": trainee_messages[third:third*2],
            "late": trainee_messages[third*2:]
        }
        
        # Detect phases per message
        phase_sequence = []
        phase_coverage = {phase: 0 for phase in self.IDEAL_FLOW}
        
        for msg in trainee_messages:
            msg_lower = msg.lower()
            detected = self._detect_phase(msg_lower)
            if detected:
                phase_sequence.append(detected)
                phase_coverage[detected] += 1
        
        # Analyze flow quality
        score = 0
        
        # 1. Phase coverage (max 8 points) - how many phases were hit
        phases_hit = sum(1 for count in phase_coverage.values() if count > 0)
        score += min(8, phases_hit * 2)  # 2 points per phase, max 8
        
        # 2. Correct ordering (max 8 points)
        if len(phase_sequence) >= 2:
            order_score = self._calculate_order_score(phase_sequence)
            score += round(order_score * 8)
        
        # 3. Phase timing (max 4 points) - right phases at right time
        timing_score = self._check_timing(segments)
        score += min(4, timing_score)
        
        missing_phases = [p for p in self.IDEAL_FLOW if phase_coverage[p] == 0]
        
        return {
            "detected_phases": phase_sequence,
            "flow_score": min(20, score),
            "flow_quality": self._interpret_flow(score, missing_phases),
            "phase_coverage": phase_coverage,
            "missing_phases": missing_phases,
            "phases_hit": phases_hit
        }
    
    def _detect_phase(self, msg_lower: str) -> str:
        """Detect dominant phase of a message."""
        best_phase = None
        best_count = 0
        
        for phase, keywords in self.PHASE_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in msg_lower)
            if count > best_count:
                best_count = count
                best_phase = phase
        
        return best_phase
    
    def _calculate_order_score(self, sequence: List[str]) -> float:
        """Calculate how well the sequence follows the ideal order (0.0 to 1.0)."""
        if not sequence:
            return 0.0
        
        # Map phases to numeric order
        order_map = {phase: i for i, phase in enumerate(self.IDEAL_FLOW)}
        numeric_sequence = [order_map.get(p, 2) for p in sequence]
        
        # Count correctly ordered pairs (Kendall tau-like)
        correct_pairs = 0
        total_pairs = 0
        for i in range(len(numeric_sequence)):
            for j in range(i + 1, len(numeric_sequence)):
                total_pairs += 1
                if numeric_sequence[j] >= numeric_sequence[i]:
                    correct_pairs += 1
        
        return correct_pairs / total_pairs if total_pairs > 0 else 0.0
    
    def _check_timing(self, segments: Dict[str, List[str]]) -> int:
        """Check if phases appear at appropriate times."""
        score = 0
        
        # Early segment should have opening/discovery keywords
        early_text = " ".join(segments["early"]).lower()
        if any(kw in early_text for kw in self.PHASE_KEYWORDS["opening"]):
            score += 1
        if any(kw in early_text for kw in self.PHASE_KEYWORDS["discovery"]):
            score += 1
        
        # Late segment should have closing keywords
        late_text = " ".join(segments["late"]).lower()
        if any(kw in late_text for kw in self.PHASE_KEYWORDS["closing"]):
            score += 1
        if any(kw in late_text for kw in self.PHASE_KEYWORDS["objection_handling"]):
            score += 1
        
        return score
    
    def _interpret_flow(self, score: int, missing: List[str]) -> str:
        if score >= 16:
            return "Excellent sales flow - natural progression through all phases"
        elif score >= 12:
            return f"Good flow with minor gaps. Consider adding: {', '.join(missing[:2])}" if missing else "Good sales flow"
        elif score >= 8:
            return f"Moderate flow. Missing: {', '.join(missing[:3])}" if missing else "Moderate sales flow"
        elif score >= 4:
            return f"Weak flow - skipped key phases: {', '.join(missing)}" if missing else "Weak sales flow"
        else:
            return "No clear sales structure - conversation lacked direction"


class ConversationDynamicsAnalyzer:
    """Analyze conversation balance and flow"""

    # Gong Labs research: top performers have ~43% seller talk time (43:57 ratio)
    MONOLOGUE_WORD_LIMIT = 120  # Gong Labs: long monologues are negative predictors of deal success

    def analyze_dynamics(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Calculate speaking patterns, balance, and engagement.
        Enhanced with message count normalization, Gong Labs talk ratio, and monologue tracking.
        """
        trainee_msgs = [m for m in messages if m['sender'] == 'trainee']
        customer_msgs = [m for m in messages if m['sender'] == 'ai_customer']

        if not trainee_msgs or not customer_msgs:
            return {
                "trainee_speaking_ratio": 0.0,
                "score": 0,
                "interpretation": "Insufficient conversation data",
                "talk_ratio_assessment": "Insufficient data",
                "longest_monologue_words": 0,
                "monologue_penalty": 0
            }

        # Word counts
        trainee_words = sum(len(m['text'].split()) for m in trainee_msgs)
        customer_words = sum(len(m['text'].split()) for m in customer_msgs)
        total_words = trainee_words + customer_words

        speaking_ratio = trainee_words / total_words if total_words > 0 else 0

        # Average message lengths
        avg_trainee_len = trainee_words / len(trainee_msgs)
        avg_customer_len = customer_words / len(customer_msgs)

        # Longest monologue tracking (Gong Labs: negative predictor of success)
        trainee_msg_lengths = [len(m['text'].split()) for m in trainee_msgs]
        longest_monologue_words = max(trainee_msg_lengths) if trainee_msg_lengths else 0
        monologue_penalty = -2 if longest_monologue_words > self.MONOLOGUE_WORD_LIMIT else 0

        # Message count check - penalize very short conversations
        turn_count = len(messages)
        length_penalty = 0
        if turn_count < 6:
            length_penalty = 4  # Significant penalty for very short conversations
        elif turn_count < 10:
            length_penalty = 2  # Mild penalty

        # Scoring based on balance (0-20 scale)
        # Shifted toward Gong Labs optimal: 43% seller talk time (43:57 ratio)
        score = 0
        if 0.40 <= speaking_ratio <= 0.50:
            score = 20  # Best: trainee talks 40-50%, Gong optimal is 43%
        elif 0.35 <= speaking_ratio <= 0.55:
            score = 17  # Good
        elif 0.30 <= speaking_ratio <= 0.60:
            score = 14  # Acceptable
        elif 0.25 <= speaking_ratio <= 0.65:
            score = 10
        else:
            score = 6

        # Apply length penalty
        score = max(0, score - length_penalty)

        # Apply monologue penalty
        score = max(0, score + monologue_penalty)

        # Engagement bonus: good average message length (15-40 words)
        if 15 <= avg_trainee_len <= 40:
            score = min(20, score + 2)

        # Talk ratio assessment (Gong Labs research-referenced)
        talk_ratio_assessment = self._assess_talk_ratio(speaking_ratio)

        return {
            "trainee_speaking_ratio": round(speaking_ratio, 2),
            "avg_trainee_length": round(avg_trainee_len, 1),
            "avg_customer_length": round(avg_customer_len, 1),
            "turn_count": turn_count,
            "trainee_turns": len(trainee_msgs),
            "longest_monologue_words": longest_monologue_words,
            "monologue_penalty": monologue_penalty,
            "talk_ratio_assessment": talk_ratio_assessment,
            "score": score,
            "interpretation": self._interpret_balance(speaking_ratio, turn_count)
        }

    def _assess_talk_ratio(self, ratio: float) -> str:
        """Assess talk ratio against Gong Labs research (optimal: 43% seller talk time)."""
        pct = round(ratio * 100)
        if 0.40 <= ratio <= 0.50:
            return "Optimal range (research shows 43-57% seller talk time correlates with highest win rates)"
        elif ratio > 0.50:
            return f"Talking too much — top performers talk 43% of the time, you're at {pct}%"
        elif 0.35 <= ratio < 0.40:
            return f"Slightly passive — aim for 40-50% talk time (you're at {pct}%)"
        else:
            return f"Too passive — aim for 40-50% talk time (you're at {pct}%)"

    def _interpret_balance(self, ratio: float, turns: int) -> str:
        if turns < 6:
            return "Conversation too short for meaningful balance analysis"
        if 0.40 <= ratio <= 0.50:
            return "Excellent balance - aligned with research-backed optimal ratio"
        elif 0.35 <= ratio <= 0.55:
            return "Good conversational balance"
        elif ratio > 0.55:
            return "Speaking too much - practice listening more"
        elif ratio < 0.35:
            return "Too passive - engage more actively"
        else:
            return "Acceptable balance"


class KeywordAnalyzer:
    """Detect sales-specific keywords and phrases - Enhanced with bigrams"""
    
    # Sales vocabulary by category (expanded with bigrams for context)
    RAPPORT_KEYWORDS = {
        'appreciate', 'thank you', 'thanks', 'understand', 'hear you',
        'great to', 'pleasure', 'excited', 'looking forward', 'good to',
        'glad to hear', 'nice to meet', 'wonderful', 'happy to help',
        'i appreciate', 'that makes sense', 'absolutely'
    }
    
    DISCOVERY_KEYWORDS = {
        'challenge', 'currently', 'pain point', 'goal', 'objective',
        'struggling', 'issue', 'problem', 'need', 'want', 'process',
        'workflow', 'situation', 'experience', 'current', 'now',
        'tell me about', 'how do you', 'walk me through', 'what are you',
        'help me understand', 'what does your', 'biggest challenge'
    }
    
    VALUE_KEYWORDS = {
        'benefit', 'value', 'roi', 'return', 'save', 'saving',
        'improve', 'increase', 'reduce', 'efficiency', 'productivity',
        'revenue', 'profit', 'cost-effective', 'advantage', 'solution',
        'results', 'outcome', 'impact', 'transform', 'streamline',
        'help you', 'enable you', 'our platform'
    }
    
    OBJECTION_KEYWORDS = {
        'concern', 'worry', 'hesitant', 'unclear', 'understand your',
        'hear that', 'makes sense', 'valid point', 'clarify', 'address',
        'let me address', 'great question', 'fair point', 'i understand that',
        'that is a valid', 'appreciate your honesty'
    }
    
    CLOSING_KEYWORDS = {
        'next step', 'move forward', 'get started', 'schedule', 'demo',
        'trial', 'pilot', 'implementation', 'onboard', 'sign up',
        'commitment', 'timeline', 'follow up', 'meeting',
        'shall we', 'would you like to', 'ready to', 'set up a',
        'action item', 'let me send you'
    }
    
    def analyze_keywords(self, trainee_messages: List[str]) -> Dict[str, Any]:
        """
        Count keyword usage by category.
        Enhanced: normalized by conversation length, no default minimum.
        """
        full_text = ' '.join(trainee_messages).lower()
        num_messages = max(1, len(trainee_messages))
        
        # Count matches for each category
        rapport_count = sum(1 for kw in self.RAPPORT_KEYWORDS if kw in full_text)
        discovery_count = sum(1 for kw in self.DISCOVERY_KEYWORDS if kw in full_text)
        value_count = sum(1 for kw in self.VALUE_KEYWORDS if kw in full_text)
        objection_count = sum(1 for kw in self.OBJECTION_KEYWORDS if kw in full_text)
        closing_count = sum(1 for kw in self.CLOSING_KEYWORDS if kw in full_text)
        
        # Normalize by conversation length (keywords per 5 messages)
        norm_factor = 5 / num_messages if num_messages > 0 else 1
        
        def score_from_count(count: int, excellent: int, good: int, fair: int) -> int:
            """Convert count to score - NO default minimum (don't reward inaction)"""
            normalized = round(count * norm_factor)
            if normalized >= excellent:
                return 18
            elif normalized >= good:
                return 14
            elif normalized >= fair:
                return 10
            elif normalized >= 1:
                return 5
            else:
                return 0  # No default minimum - earn your score
        
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
    """Combines all Tier 1 + Tier 2 NLP analyzers. Enhanced with Sales Flow Analysis."""
    
    def __init__(self, include_tier2: bool = True):
        # Tier 1 (always available - no dependencies)
        self.question_analyzer = QuestionAnalyzer()
        self.dynamics_analyzer = ConversationDynamicsAnalyzer()
        self.keyword_analyzer = KeywordAnalyzer()
        self.flow_analyzer = SalesFlowAnalyzer()  # NEW
        
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
        Run all available NLP analyses.
        Enhanced with sales flow scoring.
        """
        # Extract trainee messages
        trainee_msgs = [m['text'] for m in messages if m['sender'] == 'trainee']
        
        # Tier 1 Analysis (always run)
        question_metrics = self.question_analyzer.analyze_questions(trainee_msgs)
        dynamics_metrics = self.dynamics_analyzer.analyze_dynamics(messages)
        keyword_metrics = self.keyword_analyzer.analyze_keywords(trainee_msgs)
        flow_metrics = self.flow_analyzer.analyze_flow(trainee_msgs)  # NEW
        
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
            flow_metrics,
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
                    "keywords": keyword_metrics,
                    "sales_flow": flow_metrics  # NEW
                },
                "tier2": tier2_metrics if tier2_metrics else None
            }
        }
    
    def _combine_scores(
        self, 
        questions: Dict, 
        dynamics: Dict, 
        keywords: Dict,
        flow: Dict,
        tier2: Dict
    ) -> Dict[str, int]:
        """
        Combine Tier 1 + Tier 2 scores into category scores.
        Enhanced: Uses round() instead of int(), includes flow scoring.
        
        Tier 1 weight: 60% (50% when flow is factored in)
        Tier 2 weight: 40% (if available)
        Flow contributes across categories as a quality multiplier.
        """
        
        # Flow quality multiplier (0.7 to 1.1)
        flow_score = flow.get('flow_score', 10)
        flow_multiplier = 0.7 + (flow_score / 20) * 0.4  # Maps 0-20 to 0.7-1.1
        
        # Tier 1 base scores
        tier1_rapport = round(dynamics['score'] * 0.6 + keywords['category_scores']['rapport_building'] * 0.4)
        tier1_discovery = round(questions['score'] * 0.7 + keywords['category_scores']['needs_discovery'] * 0.3)
        tier1_presentation = keywords['category_scores']['product_presentation']
        tier1_objection = keywords['category_scores']['objection_handling']
        tier1_closing = keywords['category_scores']['closing']
        
        # Apply flow multiplier (reward good sales structure)
        tier1_rapport = round(tier1_rapport * flow_multiplier)
        tier1_discovery = round(tier1_discovery * flow_multiplier)
        tier1_presentation = round(tier1_presentation * flow_multiplier)
        tier1_objection = round(tier1_objection * flow_multiplier)
        tier1_closing = round(tier1_closing * flow_multiplier)
        
        # If no Tier 2, return Tier 1 only
        if not tier2:
            return {
                "rapport_building": min(20, tier1_rapport),
                "needs_discovery": min(20, tier1_discovery),
                "product_presentation": min(20, tier1_presentation),
                "objection_handling": min(20, tier1_objection),
                "closing": min(20, tier1_closing)
            }
        
        # Tier 2 contributions
        sentiment = tier2.get('sentiment', {})
        entities = tier2.get('entities', {})
        dialogue = tier2.get('dialogue_acts', {})
        
        # Rapport: Tier 1 (60%) + Sentiment (25%) + Dialogue Acts (15%)
        rapport_tier2 = sentiment.get('rapport_contribution', 0) + dialogue.get('rapport_contribution', 0)
        rapport = round(tier1_rapport * 0.6 + rapport_tier2 * 0.4)
        
        # Discovery: Tier 1 (70%) + Dialogue Acts (30%)
        discovery_tier2 = dialogue.get('discovery_contribution', 0)
        discovery = round(tier1_discovery * 0.7 + discovery_tier2 * 0.3)
        
        # Presentation: Tier 1 (50%) + NER (50%)
        presentation_tier2 = entities.get('presentation_contribution', 0)
        presentation = round(tier1_presentation * 0.5 + presentation_tier2 * 0.5)
        
        # Objection: Mostly Tier 1 (no strong Tier 2 signal)
        objection = tier1_objection
        
        # Closing: Tier 1 (50%) + NER (30%) + Dialogue Acts (20%)
        closing_tier2 = entities.get('closing_contribution', 0) + dialogue.get('closing_contribution', 0)
        closing = round(tier1_closing * 0.5 + closing_tier2 * 0.5)
        
        return {
            "rapport_building": min(20, rapport),
            "needs_discovery": min(20, discovery),
            "product_presentation": min(20, presentation),
            "objection_handling": min(20, objection),
            "closing": min(20, closing)
        }
