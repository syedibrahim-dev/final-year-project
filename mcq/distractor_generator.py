"""
DistractorGenerator: Generates plausible wrong answers (distractors)
Uses context and correct answer to create believable alternatives
"""

from typing import List, Dict, Any
import json
import re
from langchain_community.llms import Ollama
from config.settings import settings


class DistractorGenerator:
    """Generates plausible distractors for MCQ questions"""
    
    def __init__(self):
        self.llm = Ollama(
            model=settings.LOCAL_LLM_MODEL,
            base_url=settings.LOCAL_LLM_BASE_URL,
            temperature=0.8  # Higher temperature for diversity
        )
    
    def generate_distractors_simple(
        self,
        stem: str,
        correct_answer: str,
        context: str,
        num_distractors: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Simplified distractor generation method
        Called by pipeline.py
        
        Args:
            stem: The question text
            correct_answer: The correct answer
            context: Training material context
            num_distractors: Number of wrong answers to generate
        
        Returns:
            List of distractor dictionaries
        """
        return self.generate_distractors(
            stem=stem,
            correct_answer=correct_answer,
            context=context,
            num_distractors=num_distractors,
            difficulty="medium"
        )
    
    def generate_distractors(
        self,
        stem: str,
        correct_answer: str,
        context: str,
        num_distractors: int = 3,
        difficulty: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Generate distractors for a question
        ✅ FIX: Prevents generating correct answer as distractor
        
        Args:
            stem: The question text
            correct_answer: The correct answer
            context: Training material context
            num_distractors: Number of wrong answers to generate
            difficulty: Question difficulty level
        
        Returns:
            List of distractor options
        """
        
        prompt = self._create_distractor_prompt(
            stem, correct_answer, context, num_distractors, difficulty
        )
        
        try:
            response = self.llm.invoke(prompt)
            distractors = self._parse_distractor_response(response)
            
            # ✅ FIX: Remove any distractors that match correct answer
            distractors = self._remove_duplicate_answers(distractors, correct_answer)
            
            # Ensure we have the right number
            if len(distractors) < num_distractors:
                print(f"      ⚠️  Only generated {len(distractors)}/{num_distractors} distractors")
                # ✅ Generate contextual fallbacks instead of generic ones
                needed = num_distractors - len(distractors)
                fallbacks = self._generate_contextual_fallbacks(
                    correct_answer=correct_answer,
                    stem=stem,
                    existing_distractors=distractors,
                    count=needed
                )
                distractors.extend(fallbacks)
            
            return distractors[:num_distractors]
        
        except Exception as e:
            print(f"      ❌ Distractor generation failed: {e}")
            return self._generate_contextual_fallbacks(
                correct_answer=correct_answer,
                stem=stem,
                existing_distractors=[],
                count=num_distractors
            )
    
    def _remove_duplicate_answers(
        self,
        distractors: List[Dict[str, Any]],
        correct_answer: str
    ) -> List[Dict[str, Any]]:
        """
        ✅ NEW: Remove distractors that are too similar to correct answer
        """
        filtered = []
        correct_lower = correct_answer.lower().strip()
        correct_words = set(correct_lower.split())
        
        for dist in distractors:
            dist_text = dist.get('text', '').lower().strip()
            dist_words = set(dist_text.split())
            
            # Skip if exact match
            if dist_text == correct_lower:
                print(f"      🔄 Skipped duplicate: {dist.get('text', '')[:50]}")
                continue
            
            # Skip if >80% word overlap (Jaccard similarity)
            if correct_words and dist_words:
                intersection = len(correct_words.intersection(dist_words))
                union = len(correct_words.union(dist_words))
                similarity = intersection / union if union > 0 else 0
                
                if similarity > 0.8:
                    print(f"      🔄 Skipped similar: {dist.get('text', '')[:50]}")
                    continue
            
            filtered.append(dist)
        
        return filtered
    
    def _create_distractor_prompt(
        self,
        stem: str,
        correct_answer: str,
        context: str,
        num_distractors: int,
        difficulty: str
    ) -> str:
        """Create prompt for distractor generation"""
        
        return f"""You are an expert at creating plausible but INCORRECT answers for quiz questions.

**Question:**
{stem}

**Correct Answer (DO NOT REPEAT THIS):**
{correct_answer}

**Context:**
{context[:500]}...

**Task:** Generate {num_distractors} plausible WRONG answers (distractors).

**CRITICAL RULES:**
1. Distractors MUST be DIFFERENT from the correct answer
2. Distractors MUST be plausibly INCORRECT
3. DO NOT repeat or paraphrase the correct answer
4. Each distractor should represent a common misconception
5. Keep distractors similar length to correct answer

**Output Format (JSON ONLY - no explanations):**
{{
  "distractors": [
    {{
      "text": "First plausible wrong answer (different from correct)",
      "plausibility_score": 0.7,
      "misconception_type": "common_error"
    }},
    {{
      "text": "Second plausible wrong answer (different from correct)",
      "plausibility_score": 0.8,
      "misconception_type": "partial_knowledge"
    }},
    {{
      "text": "Third plausible wrong answer (different from correct)",
      "plausibility_score": 0.6,
      "misconception_type": "confusion"
    }}
  ]
}}

Generate the JSON now (WRONG answers only):"""
    
    def _parse_distractor_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response and extract distractors with robust JSON extraction"""
        
        try:
            # Method 1: Try direct JSON parsing
            try:
                parsed = json.loads(response)
                distractors = parsed.get("distractors", [])
                if distractors:
                    return self._validate_distractors(distractors)
            except json.JSONDecodeError:
                pass
            
            # Method 2: Extract JSON between first { and last }
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                
                try:
                    parsed = json.loads(json_str)
                    distractors = parsed.get("distractors", [])
                    if distractors:
                        return self._validate_distractors(distractors)
                except json.JSONDecodeError:
                    pass
            
            # Method 3: Extract JSON array directly
            match = re.search(r'"distractors"\s*:\s*(\[.*?\])', response, re.DOTALL)
            if match:
                try:
                    array_str = match.group(1)
                    distractors = json.loads(array_str)
                    return self._validate_distractors(distractors)
                except json.JSONDecodeError:
                    pass
            
            # Method 4: Extract text patterns
            text_matches = re.findall(r'"text"\s*:\s*"([^"]+)"', response)
            if text_matches and len(text_matches) >= 3:
                distractors = []
                for i, text in enumerate(text_matches[:3]):
                    distractors.append({
                        "text": text,
                        "plausibility_score": 0.6,
                        "misconception_type": "extracted"
                    })
                return distractors
            
            return []
        
        except Exception as e:
            return []
    
    def _validate_distractors(self, distractors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and clean distractor data"""
        validated = []
        
        for dist in distractors:
            if not isinstance(dist, dict):
                continue
            
            text = dist.get("text", "").strip()
            if not text:
                continue
            
            validated.append({
                "text": text,
                "plausibility_score": float(dist.get("plausibility_score", 0.5)),
                "misconception_type": dist.get("misconception_type", "general")
            })
        
        return validated
    
    def _generate_contextual_fallbacks(
        self,
        correct_answer: str,
        stem: str,
        existing_distractors: List[Dict[str, Any]],
        count: int
    ) -> List[Dict[str, Any]]:
        """
        ✅ IMPROVED: Generate contextual fallback distractors
        Instead of "Alternative answer N", create topic-relevant fallbacks
        """
        
        fallbacks = []
        existing_texts = [d.get('text', '') for d in existing_distractors]
        existing_texts.append(correct_answer)
        
        # Extract topic from question
        stem_words = stem.lower().split()
        
        # Contextual fallback templates
        templates = [
            "Applies only to specific enterprise scenarios",
            "Common misconception in this domain",
            "Partial understanding of the concept",
            "Confuses this with related technology",
            "Outdated approach no longer recommended",
            "Incomplete or oversimplified explanation",
            "Misinterpretation of key requirements",
            "Alternative but incorrect methodology"
        ]
        
        for i in range(count):
            if i < len(templates):
                text = templates[i]
            else:
                text = f"Not the primary purpose or function"
            
            # Ensure uniqueness
            if text not in existing_texts:
                fallbacks.append({
                    'text': text,
                    'plausibility_score': 0.5,
                    'misconception_type': 'fallback',
                    'is_fallback': True
                })
                existing_texts.append(text)
        
        return fallbacks
    
    def enhance_distractors(
        self,
        distractors: List[Dict[str, Any]],
        stem: str,
        correct_answer: str
    ) -> List[Dict[str, Any]]:
        """
        Enhance distractors by adding reasoning for why they're wrong
        """
        
        enhanced = []
        for dist in distractors:
            prompt = f"""Explain why this answer is incorrect:

**Question:** {stem}
**Correct Answer:** {correct_answer}
**Incorrect Answer:** {dist['text']}

Provide a brief explanation (1-2 sentences) of why this answer is wrong.

Output only the explanation text:"""
            
            try:
                explanation = self.llm.invoke(prompt).strip()
                dist['why_wrong'] = explanation
            except:
                dist['why_wrong'] = "This answer is incorrect based on the training material."
            
            enhanced.append(dist)
        
        return enhanced