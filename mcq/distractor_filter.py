"""
DistractorFilter: Filters out low-quality distractors
Ensures distractors are plausible and not too obvious
"""

from typing import List, Dict, Any
import re


class DistractorFilter:
    """Filters and validates distractors for quality"""
    
    def __init__(self, min_plausibility: float = 0.4):
        self.min_plausibility = min_plausibility
    
    def filter_distractors(
        self,
        distractors: List[Dict[str, Any]],
        correct_answer: str,
        stem: str
    ) -> List[Dict[str, Any]]:
        """
        Filter distractors based on quality criteria
        
        Args:
            distractors: List of generated distractors
            correct_answer: The correct answer text
            stem: The question stem
        
        Returns:
            Filtered list of high-quality distractors
        """
        
        filtered = []
        
        for dist in distractors:
            if self._is_valid_distractor(dist, correct_answer, stem):
                filtered.append(dist)
        
        # Sort by plausibility score
        filtered.sort(key=lambda x: x.get('plausibility_score', 0.5), reverse=True)
        
        return filtered
    
    def _is_valid_distractor(
        self,
        distractor: Dict[str, Any],
        correct_answer: str,
        stem: str
    ) -> bool:
        """Check if distractor meets quality criteria"""
        
        dist_text = distractor.get('text', '').strip()
        
        # Check 1: Not empty
        if not dist_text:
            return False
        
        # ✅ FIX: Check if distractor is same as correct answer
        if self._are_too_similar(dist_text, correct_answer):
            return False
        
        # Check 3: Minimum plausibility score
        plausibility = distractor.get('plausibility_score', 0.5)
        if plausibility < self.min_plausibility:
            return False
        
        # Check 4: Not too obvious (no "none of the above", "all of the above" alone)
        if self._is_obvious_distractor(dist_text):
            return False
        
        # Check 5: Appropriate length (not too short or too long)
        if not self._has_appropriate_length(dist_text, correct_answer):
            return False
        
        # Check 6: No contradictory words that make it obviously wrong
        if self._has_obvious_wrong_keywords(dist_text, stem):
            return False
        
        return True
    
    def _are_too_similar(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """Check if two texts are too similar (Jaccard similarity)"""
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        
        # ✅ FIX: Lowered threshold to catch more duplicates
        return similarity > threshold
    
    def _is_obvious_distractor(self, text: str) -> bool:
        """Check if distractor is obviously wrong"""
        
        obvious_patterns = [
            r'^none of the above$',
            r'^all of the above$',
            r'^i don\'?t know$',
            r'^maybe$',
            r'^uncertain$',
            r'^invalid answer$',
            r'^alternative (answer|option) \d+$'  # ✅ FIX: Catch "Alternative answer N"
        ]
        
        text_lower = text.lower().strip()
        
        for pattern in obvious_patterns:
            if re.match(pattern, text_lower):
                return True
        
        return False
    
    def _has_appropriate_length(
        self,
        distractor: str,
        correct_answer: str,
        max_ratio: float = 3.0
    ) -> bool:
        """Check if distractor length is appropriate compared to correct answer"""
        
        dist_len = len(distractor.split())
        correct_len = len(correct_answer.split())
        
        if correct_len == 0:
            return True
        
        ratio = dist_len / correct_len
        
        # Distractor shouldn't be more than 3x longer or shorter
        return 1/max_ratio <= ratio <= max_ratio
    
    def _has_obvious_wrong_keywords(self, distractor: str, stem: str) -> bool:
        """Check for keywords that make answer obviously wrong"""
        
        wrong_keywords = [
            'never', 'always', 'impossible', 'definitely not',
            'completely wrong', 'totally incorrect', 'absolutely not'
        ]
        
        dist_lower = distractor.lower()
        
        for keyword in wrong_keywords:
            if keyword in dist_lower:
                return True
        
        return False
    
    def rank_distractors(
        self,
        distractors: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rank distractors by quality score
        Quality = plausibility_score * length_score * uniqueness_score
        """
        
        for dist in distractors:
            quality_score = self._calculate_quality_score(dist)
            dist['quality_score'] = quality_score
        
        # Sort by quality score
        ranked = sorted(distractors, key=lambda x: x.get('quality_score', 0), reverse=True)
        
        return ranked
    
    def _calculate_quality_score(self, distractor: Dict[str, Any]) -> float:
        """Calculate overall quality score for distractor"""
        
        plausibility = distractor.get('plausibility_score', 0.5)
        text = distractor.get('text', '')
        
        # Length score (prefer moderate length)
        word_count = len(text.split())
        if word_count < 3:
            length_score = 0.5
        elif word_count > 30:
            length_score = 0.7
        else:
            length_score = 1.0
        
        # Combine scores
        quality = plausibility * length_score
        
        return quality
    
    def ensure_minimum_distractors(
        self,
        distractors: List[Dict[str, Any]],
        minimum: int = 3,
        correct_answer: str = "",
        stem_text: str = "",
        topic: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Ensure we have at least the minimum number of distractors
        ✅ FIX: Generate contextual fallbacks instead of "Alternative answer N"
        """
        
        if len(distractors) >= minimum:
            return distractors[:minimum]
        
        needed = minimum - len(distractors)
        print(f"      ⚠️  Only {len(distractors)} distractors, generating {needed} contextual fallbacks...")
        
        # ✅ Generate contextual fallbacks
        existing_texts = [d.get('text', '') for d in distractors]
        existing_texts.append(correct_answer)
        
        contextual_fallbacks = self._generate_contextual_fallbacks(
            existing_texts=existing_texts,
            stem_text=stem_text,
            topic=topic,
            count=needed
        )
        
        distractors.extend(contextual_fallbacks)
        
        return distractors
    
    def _generate_contextual_fallbacks(
        self,
        existing_texts: List[str],
        stem_text: str,
        topic: str,
        count: int
    ) -> List[Dict[str, Any]]:
        """
        ✅ NEW: Generate contextual fallback distractors
        These look more realistic than "Alternative answer N"
        """
        
        # Extract key concepts from question
        stem_lower = stem_text.lower()
        
        # Contextual fallback templates
        templates = [
            f"Applies only to specific {topic} implementations",
            f"Common misconception about {topic}",
            f"Partial understanding of {topic} concept",
            f"Confuses {topic} with related technology",
            f"Outdated approach to {topic}",
            f"Incomplete description of {topic} functionality",
            f"Misinterpretation of {topic} requirements",
            f"Alternative but incorrect {topic} method"
        ]
        
        fallbacks = []
        template_index = 0
        
        for i in range(count):
            # Cycle through templates
            text = templates[template_index % len(templates)]
            template_index += 1
            
            # Ensure uniqueness
            while text in existing_texts and template_index < len(templates) * 2:
                text = templates[template_index % len(templates)]
                template_index += 1
            
            if text not in existing_texts:
                fallbacks.append({
                    'text': text,
                    'plausibility_score': 0.5,
                    'misconception_type': 'fallback',
                    'quality_score': 0.5,
                    'is_fallback': True
                })
                existing_texts.append(text)
        
        return fallbacks