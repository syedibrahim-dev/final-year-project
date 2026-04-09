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
            model=settings.MCQ_LLM_MODEL,
            base_url=settings.LOCAL_LLM_BASE_URL,
            temperature=0.6,  # Balanced: diverse but coherent
            num_gpu=getattr(settings, 'LLM_NUM_GPU', 22)
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
        """Create prompt for distractor generation with external knowledge allowed"""
        
        return f"""You are an expert at creating plausible but INCORRECT answers for quiz questions.
Your goal: each wrong answer should target a SPECIFIC MISCONCEPTION that a trainee
might genuinely hold. This is based on research showing misconception-targeted
distractors are significantly more effective at identifying knowledge gaps
(arXiv:2506.00612, Knowledge-Guided Distractor Generation, 2025).

**Question:**
{stem}

**Correct Answer (DO NOT REPEAT THIS):**
{correct_answer}

**Context:**
{context[:500]}...

**Task:** Generate {num_distractors} plausible WRONG answers. Each MUST target a
different misconception from the list below.

**MISCONCEPTION CATEGORIES (use exactly one per distractor):**
1. **confused_metric** — Swaps a specific number/stat with a plausible but wrong one
   (e.g., correct is "99.7%" → distractor uses "99.9%" or "97%")
2. **wrong_scope** — Applies a real fact to the wrong context
   (e.g., a feature that exists in Enterprise plan attributed to Starter plan)
3. **partial_truth** — Combines a correct concept with an incorrect detail
   (e.g., "Auto-renewal with 99.7% success rate and zero configuration" — the rate is right but the rest is wrong)
4. **competitor_confusion** — Attributes a competitor's feature or practice to this product
   (e.g., confuses with Venafi, DigiCert, or general industry tools)
5. **overgeneralization** — Takes a specific, limited capability and claims it's universal
   (e.g., "works with all operating systems" when it only supports specific ones)
6. **outdated_practice** — References an older approach that seems plausible but isn't what the text says

**CRITICAL RULES:**
1. Each distractor MUST target a DIFFERENT misconception category
2. Distractors MUST be plausible — a real trainee could believe them
3. DO NOT repeat or paraphrase the correct answer
4. Keep distractors similar length to correct answer
5. The "why_wrong" field MUST explain what specific misconception the trainee holds if they pick this

**Output Format (JSON ONLY):**
{{
  "distractors": [
    {{
      "text": "Plausible wrong answer targeting a specific misconception",
      "misconception_type": "confused_metric",
      "why_wrong": "Confuses the 99.7% renewal rate with a 99.9% uptime SLA — these are different metrics"
    }},
    {{
      "text": "Another wrong answer targeting different misconception",
      "misconception_type": "wrong_scope",
      "why_wrong": "This feature is only available in Enterprise plan, not Starter"
    }},
    {{
      "text": "Third wrong answer targeting yet another misconception",
      "misconception_type": "competitor_confusion",
      "why_wrong": "This is how Venafi works, not CloudVault — confuses the two vendors"
    }}
  ]
}}

Generate the JSON now (WRONG answers only — start with {{):"""
    
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
        Generate contextual fallback distractors by mutating the correct answer.
        """
        import re as _re
        
        fallbacks = []
        existing_texts = [d.get('text', '').lower() for d in existing_distractors]
        existing_texts.append(correct_answer.lower())
        ca = correct_answer.strip()
        
        candidates = []
        
        # Strategy 1: Numeric mutations
        nums = _re.findall(r'\\d+', ca)
        if nums:
            for n in nums[:2]:
                val = int(n)
                for mult in [2, 0.5, 1.5]:
                    candidates.append(ca.replace(n, str(int(val * mult)), 1))
        
        # Strategy 2: Negation / word swap
        swaps = {
            'increase': 'decrease', 'before': 'after', 'internal': 'external',
            'all': 'some', 'always': 'sometimes', 'required': 'optional',
            'maximum': 'minimum', 'primary': 'secondary', 'first': 'last',
            'enable': 'disable', 'include': 'exclude', 'accept': 'reject',
        }
        ca_lower = ca.lower()
        for old, new in swaps.items():
            if old in ca_lower:
                idx = ca_lower.find(old)
                candidates.append(ca[:idx] + new + ca[idx + len(old):])
        
        # Strategy 3: Partial answer (first half)
        words = ca.split()
        if len(words) > 4:
            candidates.append(' '.join(words[:len(words)//2]))
            candidates.append(' '.join(words[len(words)//2:]))
        
        # Strategy 4: Extract key nouns from stem for context-aware fallback
        stem_words = [w for w in stem.split() if len(w) > 4 and w[0].isupper()]
        if stem_words:
            candidates.append(f"Related to {stem_words[0]} but applied differently")
        
        for c in candidates:
            if len(fallbacks) >= count:
                break
            c_clean = c.strip()
            if c_clean.lower() not in existing_texts and c_clean.lower() != ca.lower() and len(c_clean) > 3:
                fallbacks.append({
                    'text': c_clean,
                    'plausibility_score': 0.5,
                    'misconception_type': 'contextual_fallback',
                    'is_fallback': True
                })
                existing_texts.append(c_clean.lower())
        
        # Last resort if still short
        while len(fallbacks) < count:
            text = f"Alternative approach not supported by the material"
            if text.lower() not in existing_texts:
                fallbacks.append({
                    'text': text,
                    'plausibility_score': 0.4,
                    'misconception_type': 'generic_fallback',
                    'is_fallback': True
                })
                existing_texts.append(text.lower())
                text = f"Commonly confused with a different concept"
            else:
                break
        
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