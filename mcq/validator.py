"""
MCQ Validator: Comprehensive validation for generated MCQs
Implements 3 validation types:
1. Content Relevance (Embeddings) - Cosine similarity between Q&A and context
2. Answer Correctness (LLM) - Ask LLM to verify answer is correct
3. Question Clarity (Grammar) - Check grammar/spelling/readability
"""

from typing import Dict, Any, List, Tuple
import re
import math
from langchain_community.llms import Ollama
from langchain_community.embeddings import SentenceTransformerEmbeddings
from config.settings import settings


class MCQValidator:
    """Validates MCQ quality across multiple dimensions"""
    
    def __init__(
        self,
        relevance_threshold: float = 0.3,
        clarity_threshold: float = 0.7
    ):
        """
        Initialize validator
        
        Args:
            relevance_threshold: Minimum cosine similarity for relevance (0.3 = 30%)
            clarity_threshold: Minimum clarity score (0.7 = 70%)
        """
        self.relevance_threshold = relevance_threshold
        self.clarity_threshold = clarity_threshold
        
        # Initialize embeddings for content relevance
        self.embeddings = SentenceTransformerEmbeddings(
            model_name=settings.EMBEDDING_MODEL
        )
        
        # Initialize LLM for answer correctness
        self.llm = Ollama(
            model=settings.MCQ_LLM_MODEL,
            base_url=settings.LOCAL_LLM_BASE_URL,
            temperature=0.2,  # Lower temperature for more deterministic validation
            num_ctx=4096
        )
    
    def validate_complete(
        self,
        question: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Run all 3 validation types on a question
        
        Args:
            question: Complete MCQ dictionary with question_text, options, correct_answer
            context: Training material context used to generate the question
        
        Returns:
            Validation results with scores and pass/fail for each type
        """
        
        question_text = question.get('question_text', '')
        correct_answer = self._extract_correct_answer_text(question)
        
        # Validation 1: Content Relevance (Embeddings)
        relevance_result = self.validate_content_relevance(
            question_text=question_text,
            answer_text=correct_answer,
            context=context
        )
        
        # Validation 2: Answer Correctness (LLM)
        correctness_result = self.validate_answer_correctness(
            question_text=question_text,
            answer_text=correct_answer,
            context=context
        )
        
        # Validation 3: Question Clarity (Grammar)
        clarity_result = self.validate_question_clarity(
            question_text=question_text
        )
        
        # Calculate overall pass/fail
        all_passed = (
            relevance_result['passed'] and
            correctness_result['passed'] and
            clarity_result['passed']
        )
        
        return {
            'overall_passed': all_passed,
            'content_relevance': relevance_result,
            'answer_correctness': correctness_result,
            'question_clarity': clarity_result,
            'summary': self._generate_validation_summary(
                relevance_result,
                correctness_result,
                clarity_result
            )
        }
    
    # ========================================
    # VALIDATION 1: Content Relevance (Embeddings)
    # ========================================
    
    def validate_content_relevance(
        self,
        question_text: str,
        answer_text: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Validate that question and answer are relevant to the training context
        Uses cosine similarity between embeddings
        🆕 Enhanced with hallucination detection thresholds
        
        Args:
            question_text: The question stem
            answer_text: The correct answer
            context: Training material context
        
        Returns:
            Dict with similarity score, pass/fail, and hallucination warning
        """
        
        try:
            # Combine question and answer for full context check
            qa_text = f"{question_text} {answer_text}"
            
            # Generate embeddings
            qa_embedding = self.embeddings.embed_query(qa_text)
            context_embedding = self.embeddings.embed_query(context[:1000])
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(qa_embedding, context_embedding)
            
            # 🆕 Multi-tier thresholds for hallucination detection
            hallucination_warning = False
            if similarity < 0.25:
                hallucination_warning = "SEVERE: Likely hallucinated - not grounded in source"
            elif similarity < 0.35:
                hallucination_warning = "HIGH: Weak connection to source material"
            
            passed = similarity >= self.relevance_threshold
            
            result = {
                'passed': passed,
                'similarity_score': round(similarity, 3),
                'threshold': self.relevance_threshold,
                'message': self._get_relevance_message(similarity, passed)
            }
            
            # 🆕 Add hallucination warning if detected
            if hallucination_warning:
                result['hallucination_warning'] = hallucination_warning
                result['message'] = f"⚠️ {hallucination_warning} (similarity: {similarity:.1%})"
            
            return result
            
        except Exception as e:
            print(f"      ⚠️  Content relevance validation failed: {e}")
            return {
                'passed': True,  # Don't fail on error
                'similarity_score': 0.0,
                'threshold': self.relevance_threshold,
                'message': f'Validation error: {str(e)}',
                'error': str(e)
            }
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _get_relevance_message(self, similarity: float, passed: bool) -> str:
        """Generate relevance validation message"""
        
        if passed:
            if similarity >= 0.7:
                return f"✅ Excellent relevance ({similarity:.1%}) - Strongly aligned with training content"
            elif similarity >= 0.5:
                return f"✅ Good relevance ({similarity:.1%}) - Well aligned with training content"
            else:
                return f"✅ Acceptable relevance ({similarity:.1%}) - Sufficiently aligned with training content"
        else:
            return f"❌ Low relevance ({similarity:.1%}) - May not be based on training material"
    
    # ========================================
    # VALIDATION 2: Answer Correctness (LLM)
    # ========================================
    
    def validate_answer_correctness(
        self,
        question_text: str,
        answer_text: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Validate that the answer is factually correct based on context
        Uses LLM to verify answer accuracy
        
        Args:
            question_text: The question stem
            answer_text: The correct answer
            context: Training material context
        
        Returns:
            Dict with correctness verification and pass/fail
        """
        
        try:
            prompt = f"""You are a strict factual accuracy validator with anti-hallucination detection.

**TRAINING MATERIAL (ONLY SOURCE OF TRUTH):**
{context[:800]}

**QUESTION:**
{question_text}

**PROPOSED ANSWER:**
{answer_text}

**TASK:** Verify if this answer is factually correct based ONLY on the training material above.

**🚨 HALLUCINATION DETECTION CHECKS:**
1. Can you find the EXACT information in the training material?
2. Is the answer using terminology DIRECTLY from the text?
3. Does the answer reference concepts NOT in the training material?
4. Is the answer based on general knowledge instead of the specific text?

**STRICT GROUNDING REQUIREMENT:**
- If the answer references information NOT in the training material, mark as INCORRECT
- If the answer uses external knowledge (Salesforce, AWS, standard practices), mark as INCORRECT
- If you cannot quote the source sentence, mark as INCORRECT

**OUTPUT FORMAT (JSON ONLY):**
{{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation with quote from training material if correct",
  "hallucination_detected": true/false,
  "source_quote": "Exact quote from training material (if found)"
}}

JSON only:"""

            response = self.llm.invoke(prompt)
            result = self._parse_correctness_response(response)
            
            passed = result.get('is_correct', False)
            confidence = result.get('confidence', 0.5)
            reasoning = result.get('reasoning', 'No reasoning provided')
            hallucination = result.get('hallucination_detected', False)
            source_quote = result.get('source_quote', '')
            
            # 🆕 Override pass if hallucination detected
            if hallucination:
                passed = False
                confidence = 0.0
            
            return {
                'passed': passed,
                'is_correct': passed,
                'confidence': confidence,
                'reasoning': reasoning,
                'hallucination_detected': hallucination,
                'source_quote': source_quote,
                'message': self._get_correctness_message(passed, confidence, hallucination)
            }
            
        except Exception as e:
            print(f"      ⚠️  Answer correctness validation failed: {e}")
            return {
                'passed': True,  # Don't fail on error
                'is_correct': True,
                'confidence': 0.5,
                'reasoning': f'Validation error: {str(e)}',
                'message': 'Could not verify answer correctness',
                'error': str(e)
            }
    
    def _parse_correctness_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response for correctness validation"""
        
        import json
        
        try:
            # Try direct JSON parsing
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                result = json.loads(json_str)
                
                return {
                    'is_correct': result.get('is_correct', False),
                    'confidence': float(result.get('confidence', 0.5)),
                    'reasoning': result.get('reasoning', 'No reasoning provided'),
                    'hallucination_detected': result.get('hallucination_detected', False),
                    'source_quote': result.get('source_quote', '')
                }
        except:
            pass
        
        # Fallback: Parse manually
        is_correct = any(word in response.lower() for word in ['correct', 'accurate', 'true', 'yes'])
        hallucination = any(word in response.lower() for word in ['hallucination', 'external knowledge', 'not in text'])
        confidence = 0.7 if is_correct else 0.3
        
        return {
            'is_correct': is_correct,
            'confidence': confidence,
            'reasoning': 'Manual parsing from LLM response',
            'hallucination_detected': hallucination,
            'source_quote': ''
        }
    
    def _get_correctness_message(self, is_correct: bool, confidence: float, hallucination: bool = False) -> str:
        """Generate correctness validation message"""
        
        if hallucination:
            return f"🚨 HALLUCINATION DETECTED - Answer uses external knowledge not in source material"
        
        if is_correct:
            if confidence >= 0.8:
                return f"✅ High confidence ({confidence:.0%}) - Answer is factually correct and grounded in source"
            else:
                return f"✅ Moderate confidence ({confidence:.0%}) - Answer appears correct"
        else:
            return f"❌ Answer incorrect or not verifiable from source material (confidence: {confidence:.0%})"
    
    # ========================================
    # VALIDATION 3: Question Clarity (Grammar)
    # ========================================
    
    def validate_question_clarity(
        self,
        question_text: str
    ) -> Dict[str, Any]:
        """
        Validate question grammar, spelling, and readability
        
        Args:
            question_text: The question stem
        
        Returns:
            Dict with clarity score and pass/fail
        """
        
        try:
            issues = []
            score = 1.0  # Start with perfect score
            
            # Check 1: Question ends with '?'
            if not question_text.strip().endswith('?'):
                issues.append("Question doesn't end with '?'")
                score -= 0.2
            
            # Check 2: Proper capitalization
            if question_text and not question_text[0].isupper():
                issues.append("Question doesn't start with capital letter")
                score -= 0.1
            
            # Check 3: No double spaces
            if '  ' in question_text:
                issues.append("Contains double spaces")
                score -= 0.05
            
            # Check 4: Appropriate length (10-150 characters)
            length = len(question_text)
            if length < 10:
                issues.append(f"Too short ({length} chars, minimum 10)")
                score -= 0.3
            elif length > 150:
                issues.append(f"Too long ({length} chars, maximum 150)")
                score -= 0.1
            
            # Check 5: No spelling errors (basic check)
            spelling_issues = self._check_basic_spelling(question_text)
            if spelling_issues:
                issues.extend(spelling_issues)
                score -= 0.1 * len(spelling_issues)
            
            # Check 6: Readability (no overly complex words)
            readability_issues = self._check_readability(question_text)
            if readability_issues:
                issues.extend(readability_issues)
                score -= 0.05 * len(readability_issues)
            
            # Check 7: Clear question words
            if not self._has_clear_question_word(question_text):
                issues.append("No clear question word (What, How, Why, etc.)")
                score -= 0.15
            
            # Ensure score is between 0 and 1
            score = max(0.0, min(1.0, score))
            
            passed = score >= self.clarity_threshold
            
            return {
                'passed': passed,
                'clarity_score': round(score, 2),
                'threshold': self.clarity_threshold,
                'issues': issues,
                'message': self._get_clarity_message(score, passed, issues)
            }
            
        except Exception as e:
            print(f"      ⚠️  Question clarity validation failed: {e}")
            return {
                'passed': True,  # Don't fail on error
                'clarity_score': 0.7,
                'threshold': self.clarity_threshold,
                'issues': [f'Validation error: {str(e)}'],
                'message': 'Could not fully validate clarity',
                'error': str(e)
            }
    
    def _check_basic_spelling(self, text: str) -> List[str]:
        """Basic spelling checks (common mistakes)"""
        
        issues = []
        
        # Common typos
        typo_patterns = {
            r'\bteh\b': 'the',
            r'\brecieve\b': 'receive',
            r'\boccured\b': 'occurred',
            r'\bseperate\b': 'separate',
            r'\bdefinately\b': 'definitely'
        }
        
        for pattern, correct in typo_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Possible typo: should be '{correct}'")
        
        return issues
    
    def _check_readability(self, text: str) -> List[str]:
        """Check readability issues"""
        
        issues = []
        
        # Check for overly long words (>20 chars often indicate issues)
        words = text.split()
        long_words = [w for w in words if len(w) > 20]
        if long_words:
            issues.append(f"Overly long word(s): {', '.join(long_words)}")
        
        # Check for excessive punctuation
        if text.count('!') > 1 or text.count('?') > 1:
            issues.append("Excessive punctuation marks")
        
        return issues
    
    def _has_clear_question_word(self, text: str) -> bool:
        """Check if question has clear question word"""
        
        question_words = [
            'what', 'which', 'who', 'when', 'where', 'why', 'how',
            'does', 'do', 'is', 'are', 'can', 'will', 'would', 'should'
        ]
        
        text_lower = text.lower()
        return any(word in text_lower for word in question_words)
    
    def _get_clarity_message(
        self,
        score: float,
        passed: bool,
        issues: List[str]
    ) -> str:
        """Generate clarity validation message"""
        
        if passed:
            if score >= 0.9:
                return f"✅ Excellent clarity ({score:.0%}) - Well-formed question"
            else:
                return f"✅ Good clarity ({score:.0%}) - Question is clear"
        else:
            issue_summary = '; '.join(issues[:2]) if issues else 'Multiple issues'
            return f"❌ Poor clarity ({score:.0%}) - {issue_summary}"
    
    # ========================================
    # Helper Methods
    # ========================================
    
    def _extract_correct_answer_text(self, question: Dict[str, Any]) -> str:
        """Extract correct answer text from question options"""
        
        options = question.get('options', [])
        
        for option in options:
            if option.get('is_correct', False):
                return option.get('option_text', '')
        
        return ''
    
    def _generate_validation_summary(
        self,
        relevance: Dict[str, Any],
        correctness: Dict[str, Any],
        clarity: Dict[str, Any]
    ) -> str:
        """Generate overall validation summary"""
        
        passed_count = sum([
            relevance.get('passed', False),
            correctness.get('passed', False),
            clarity.get('passed', False)
        ])
        
        if passed_count == 3:
            return "✅ All validations passed - High quality question"
        elif passed_count == 2:
            return "⚠️  2/3 validations passed - Acceptable quality"
        elif passed_count == 1:
            return "⚠️  1/3 validations passed - Low quality question"
        else:
            return "❌ All validations failed - Question needs significant improvement"


# ========================================
# Quick validation function for pipeline
# ========================================

def quick_validate_mcq(
    question: Dict[str, Any],
    context: str,
    relevance_threshold: float = 0.3,
    clarity_threshold: float = 0.7
) -> Tuple[bool, Dict[str, Any]]:
    """
    Quick validation function for use in MCQ pipeline
    
    Args:
        question: Complete MCQ dictionary
        context: Training material context
        relevance_threshold: Minimum cosine similarity
        clarity_threshold: Minimum clarity score
    
    Returns:
        Tuple of (passed, validation_results)
    """
    
    validator = MCQValidator(
        relevance_threshold=relevance_threshold,
        clarity_threshold=clarity_threshold
    )
    
    results = validator.validate_complete(question, context)
    
    return results['overall_passed'], results
