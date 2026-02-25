"""
MCQPipeline: Orchestrates the complete MCQ generation process
Coordinates stem generation, distractor generation, and filtering
"""

from typing import List, Dict, Any
import json
import random

from mcq.stem_generator import StemGenerator
from mcq.distractor_generator import DistractorGenerator
from mcq.distractor_filter import DistractorFilter
from mcq.validator import MCQValidator
from services.rag_service import retrieve_relevant_chunks


class MCQPipeline:
    """Complete MCQ generation pipeline"""
    
    def __init__(self):
        self.stem_generator = StemGenerator()
        self.distractor_generator = DistractorGenerator()
        self.distractor_filter = DistractorFilter(min_plausibility=0.4)
        self.validator = MCQValidator(
            relevance_threshold=0.3,  # 30% minimum relevance
            clarity_threshold=0.7     # 70% minimum clarity
        )
    
    def generate_mcqs(
        self,
        topic: str,
        difficulty: str,
        num_questions: int,
        org_id: int,
        include_explanations: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate complete MCQs with questions and answers
        
        Args:
            topic: Topic/subject area
            difficulty: easy, medium, hard
            num_questions: Number of questions to generate
            org_id: Organization ID (for RAG retrieval)
            include_explanations: Whether to include answer explanations
        
        Returns:
            List of complete MCQ questions with options
        """
        
        print(f"🚀 Starting MCQ generation pipeline...")
        print(f"   📝 Requested questions: {num_questions}")
        print(f"   🎯 Topic: {topic}")
        print(f"   ⭐ Difficulty: {difficulty}")
        
        # STEP 1: Retrieve relevant context from RAG
        print(f"\n📚 Step 1: Retrieving training content...")
        context_chunks = retrieve_relevant_chunks(
            query=topic,
            org_id=org_id,
            k=3  # Safe value for llama3.1:8b
        )
        
        if not context_chunks:
            raise ValueError("No training content found for this topic. Please upload training materials first.")
        
        # Increased context for richer question generation
        context = "\n\n".join([chunk["chunk"] for chunk in context_chunks])[:3000]
        print(f"   ✅ Retrieved {len(context_chunks)} context chunks ({len(context)} chars)")
        
        # ✅ Validate context has substantial content
        if len(context.strip()) < 200:
            raise ValueError(f"Retrieved context too short ({len(context)} chars). Need more detailed training material.")
        
        # STEP 2: Generate question stems
        print(f"\n❓ Step 2: Generating question stems...")
        
        stems = self.stem_generator.generate_stems(
            context=context,
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions
        )
        
        if not stems:
            raise ValueError("Failed to generate question stems")
        
        if len(stems) < num_questions:
            print(f"   ⚠️  Only generated {len(stems)}/{num_questions} stems")
        else:
            print(f"   ✅ Generated {num_questions} question stems")
        
        # STEP 3: Generate complete questions
        print(f"\n🎯 Step 3: Generating answers and distractors...")
        print(f"   ℹ️  Processing {len(stems)} questions...")
        
        complete_questions = []
        
        for i, stem in enumerate(stems):
            print(f"   📝 Question {i+1}/{len(stems)}...", end=" ", flush=True)
            
            try:
                question = self._generate_complete_question(
                    stem=stem,
                    context=context,
                    difficulty=difficulty,
                    topic=topic,
                    include_explanations=include_explanations
                )
                
                if question:
                    complete_questions.append(question)
                    print("✅")
            
            except Exception as e:
                print(f"❌ Error: {str(e)[:50]}")
                continue
        
        if not complete_questions:
            raise ValueError("Failed to generate any valid questions. Please try again.")
        
        # STEP 4: Validate questions (new step)
        print(f"\n✅ Step 4: Validating question quality...")
        print(f"   ℹ️  Running 3 validation types: Relevance, Correctness, Clarity")
        
        validated_questions = []
        
        for i, question in enumerate(complete_questions):
            print(f"   🔍 Validating Q{i+1}...", end=" ", flush=True)
            
            try:
                validation_result = self.validator.validate_complete(
                    question=question,
                    context=context
                )
                
                # Add validation results to question metadata
                question['validation'] = validation_result
                
                if validation_result['overall_passed']:
                    validated_questions.append(question)
                    print("✅ PASS")
                else:
                    print(f"⚠️  FAIL - {validation_result['summary']}")
                    # Still include the question but mark it as low quality
                    question['quality_warning'] = True
                    validated_questions.append(question)
            
            except Exception as e:
                print(f"⚠️  Validation error: {str(e)[:40]}")
                # Include question even if validation fails
                question['validation'] = {'error': str(e)}
                validated_questions.append(question)
        
        if not validated_questions:
            raise ValueError("Failed to generate any valid questions. Please try again.")
        
        final_questions = validated_questions[:num_questions]
        
        print(f"\n✅ Pipeline complete! Generated {len(final_questions)} questions")
        
        if len(final_questions) < num_questions:
            print(f"   ⚠️  Note: Requested {num_questions} but only {len(final_questions)} were valid")
        
        print()
        
        return final_questions
    
    def _generate_complete_question(
        self,
        stem: Dict[str, Any],
        context: str,
        difficulty: str,
        topic: str,
        include_explanations: bool
    ) -> Dict[str, Any]:
        """Generate a complete question with options"""
        
        stem_text = stem.get('stem_text', '')
        
        # Generate correct answer first
        correct_answer = self._generate_correct_answer(stem_text, context)
        
        # Generate distractors (they will NOT repeat correct answer)
        raw_distractors = self.distractor_generator.generate_distractors(
            stem=stem_text,
            correct_answer=correct_answer,
            context=context,
            num_distractors=3,
            difficulty=difficulty
        )
        
        # Filter distractors (removes duplicates and low quality)
        filtered_distractors = self.distractor_filter.filter_distractors(
            distractors=raw_distractors,
            correct_answer=correct_answer,
            stem=stem_text
        )
        
        # ✅ UPDATED: Pass context for better fallbacks
        filtered_distractors = self.distractor_filter.ensure_minimum_distractors(
            distractors=filtered_distractors,
            minimum=3,
            correct_answer=correct_answer,
            stem_text=stem_text,
            topic=topic
        )
        
        # ✅ UPDATED: Pass stem and topic for contextual fallbacks
        options = self._build_options_formatted(
            correct_answer=correct_answer,
            distractors=filtered_distractors,
            stem_text=stem_text,
            topic=topic
        )
        
        # Generate explanation
        explanation = ""
        if include_explanations:
            explanation = self._generate_simple_explanation(
                stem_text, correct_answer, topic
            )
        
        # Determine correct answer letter
        correct_letter = self._find_correct_letter(options)
        
        return {
            "question_text": stem_text,
            "options": options,
            "correct_answer": correct_letter,
            "explanation": explanation,
            "difficulty": difficulty,
            "topic": stem.get('topic', topic),
            "cognitive_level": stem.get('cognitive_level', 'understand'),
            "key_concept": stem.get('key_concept', '')
        }
    
    def _generate_correct_answer(self, stem: str, context: str) -> str:
        """Generate the correct answer for a question"""
        
        from langchain_community.llms import Ollama
        from config.settings import settings
        
        llm = Ollama(
            model=settings.MCQ_LLM_MODEL,
            base_url=settings.LOCAL_LLM_BASE_URL,
            temperature=0.3,
            num_ctx=4096
        )
        
        prompt = f"""Based STRICTLY on the training material below, provide a SHORT and CONCISE answer.

**TRAINING MATERIAL (YOUR ONLY SOURCE):**
{context[:1000]}

**QUESTION:**
{stem}

**🚨 STRICT GROUNDING REQUIREMENTS:**
1. Answer MUST come from the training material above - NOT from your general knowledge
2. If the answer is NOT explicitly in the text, respond with: "SKIP_QUESTION"
3. DO NOT use external knowledge about products, services, or standard practices
4. DO NOT assume or infer information not directly stated
5. Quote the exact phrase or number from the training material

**NEGATIVE CONSTRAINTS:**
- ❌ NO Salesforce/AWS/platform-specific knowledge unless in text
- ❌ NO standard business practices unless explicitly stated
- ❌ NO industry terminology unless used in the training material
- ❌ NO invented features, processes, or terms
- ❌ NO assumptions based on "typical" or "common" approaches

**ANSWER REQUIREMENTS:**
- Maximum 30 words (increased to prevent truncation)
- Must be factual and directly from text
- Use exact terminology from training material
- Include specific numbers, names, or technical terms
- Must be a COMPLETE sentence or phrase (no truncation)
- ❌ AVOID generic answers like "based on training material" or "to manage risks"
- ❌ AVOID vague answers like "no further details provided"
- ✅ PREFER specific answers like "Net 30 payment terms" or "85% uptime SLA"

**EXAMPLES:**
Question: "What are the payment terms?"
❌ BAD: "Payment terms from the contract"
✅ GOOD: "Net 30 days from invoice date"

Question: "What is the purpose of Risk Management?"
❌ BAD: "To manage risks"
✅ GOOD: "Identify, assess, and mitigate project delivery risks"

Provide ONLY the specific answer (maximum 20 words):"""
        
        try:
            answer = llm.invoke(prompt).strip()
            
            # ✅ REJECT only critical failure indicators (reduced for phi3:mini)
            failure_indicators = [
                "skip_question",                # LLM signaling unanswerable
                "cannot answer",
                "cannot find",
                "not found",
                "not mentioned",
                "no further details",           # Vague answer
                "based on training material",  # Generic fallback without specifics
                "cannot be determined"          # Explicitly saying it's unanswerable
            ]
            
            answer_lower = answer.lower()
            for indicator in failure_indicators:
                if indicator in answer_lower:
                    raise ValueError(f"Question unanswerable or generic answer: {stem}")
            
            # ✅ REJECT if answer is too short (likely generic)
            if len(answer.strip()) < 5:
                raise ValueError(f"Answer too short/generic: {answer}")
            
            # Clean up the answer
            answer = answer.replace('\n', ' ').strip()
            answer = answer.strip('"\'')
            
            # Truncate if too long (increased limit)
            if len(answer) > 180:
                sentences = answer.split('.')
                answer = sentences[0].strip()
                if len(answer) > 180:
                    answer = answer[:177] + "..."
            
            return answer
            
        except Exception as e:
            # ✅ DON'T return generic fallback - raise exception to skip this question
            raise ValueError(f"Answer generation failed: {str(e)[:100]}")
    
    def _build_options_formatted(
        self,
        correct_answer: str,
        distractors: List[Dict[str, Any]],
        stem_text: str = "",
        topic: str = ""
    ) -> List[Dict[str, str]]:
        """
        ✅ IMPROVED: Build properly formatted options with duplicate prevention
        """
        
        options = []
        used_texts = set()
        
        # Add correct answer
        correct_text = correct_answer.strip()
        if len(correct_text) > 180:  # ✅ Increased to match new 30-word limit
            correct_text = correct_text[:177] + "..."
        
        correct_text = correct_text.strip('"\'')
        options.append({
            "option_text": correct_text,
            "is_correct": True
        })
        used_texts.add(correct_text.lower())
        
        # ✅ Add distractors with duplicate checking
        added_distractors = 0
        for dist in distractors:
            if added_distractors >= 3:
                break
            
            distractor_text = dist.get('text', '').strip()
            
            # Skip if empty
            if not distractor_text:
                continue
            
            # ✅ Skip if duplicate of correct answer
            if distractor_text.lower() in used_texts:
                print(f"\n      🔄 Skipped duplicate distractor")
                continue
            
            # Truncate if too long (increased limit)
            if len(distractor_text) > 180:
                distractor_text = distractor_text[:177] + "..."
            
            distractor_text = distractor_text.strip('"\'')
            
            # ✅ Double-check not a duplicate
            if distractor_text.lower() not in used_texts:
                options.append({
                    "option_text": distractor_text,
                    "is_correct": False
                })
                used_texts.add(distractor_text.lower())
                added_distractors += 1
        
        # ✅ If still need more distractors, generate contextual ones
        while len(options) < 4:
            fallback_text = self._generate_emergency_distractor(
                correct_answer=correct_text,
                existing_texts=list(used_texts),
                topic=topic,
                index=len(options)
            )
            
            if fallback_text.lower() not in used_texts:
                options.append({
                    "option_text": fallback_text,
                    "is_correct": False
                })
                used_texts.add(fallback_text.lower())
        
        # Shuffle options
        random.shuffle(options)
        
        return options
    
    def _generate_emergency_distractor(
        self,
        correct_answer: str,
        existing_texts: List[str],
        topic: str,
        index: int
    ) -> str:
        """
        Generate emergency distractor by mutating the correct answer
        to produce a plausible but incorrect variant.
        """
        import re as _re
        
        # Strategy 1: Negate or modify the correct answer
        mutations = []
        ca = correct_answer.strip()
        
        # Numeric mutation: change numbers in the answer
        nums = _re.findall(r'\d+', ca)
        if nums:
            for n in nums[:1]:
                alt_n = str(int(n) * 2) if int(n) < 50 else str(int(n) // 2)
                mutations.append(ca.replace(n, alt_n, 1))
        
        # Word-level mutations
        word_swaps = {
            'increase': 'decrease', 'decrease': 'increase',
            'before': 'after', 'after': 'before',
            'internal': 'external', 'external': 'internal',
            'first': 'last', 'last': 'first',
            'primary': 'secondary', 'secondary': 'primary',
            'all': 'some', 'always': 'sometimes',
            'required': 'optional', 'optional': 'required',
            'maximum': 'minimum', 'minimum': 'maximum',
        }
        ca_lower = ca.lower()
        for old, new in word_swaps.items():
            if old in ca_lower:
                idx = ca_lower.find(old)
                mutations.append(ca[:idx] + new + ca[idx + len(old):])
                break
        
        # Truncation: use only the first half of the answer
        words = ca.split()
        if len(words) > 4:
            mutations.append(' '.join(words[:len(words)//2]))
        
        # Topic-based fallbacks as last resort
        mutations.extend([
            f"A different aspect of {topic}",
            f"Not directly related to this {topic} requirement",
        ])
        
        existing_lower = {t.lower() for t in existing_texts}
        for m in mutations:
            if m.strip().lower() not in existing_lower and m.strip().lower() != ca.lower():
                return m.strip()
        
        return f"Alternative interpretation in {topic}"
    
    def _find_correct_letter(self, options: List[Dict[str, str]]) -> str:
        """Find which letter (A, B, C, D) is the correct answer"""
        
        letters = ['A', 'B', 'C', 'D']
        
        for i, option in enumerate(options):
            if option.get('is_correct', False):
                return letters[i] if i < len(letters) else 'A'
        
        return 'A'
    
    def _generate_simple_explanation(
        self,
        stem: str,
        correct_answer: str,
        topic: str
    ) -> str:
        """Generate a simple explanation with proper context"""
        
        # ✅ Create contextual explanation instead of generic template
        if len(correct_answer) < 10:
            # Short answer - provide context
            return f"According to the training material, the answer is '{correct_answer}'."
        else:
            # Longer answer - use it directly (remove duplicate prefix if present)
            answer_preview = correct_answer[:150] + "..." if len(correct_answer) > 150 else correct_answer
            
            # ✅ Check if answer already starts with "According to"
            if answer_preview.lower().startswith("according to"):
                return answer_preview.capitalize()
            else:
                return f"According to the training material, {answer_preview}"
    
    def validate_questions(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate generated questions for quality"""
        
        total = len(questions)
        valid = 0
        issues = []
        
        for i, q in enumerate(questions):
            is_valid, question_issues = self._validate_single_question(q)
            
            if is_valid:
                valid += 1
            else:
                issues.append({
                    "question_index": i + 1,
                    "issues": question_issues
                })
        
        return {
            "total_questions": total,
            "valid_questions": valid,
            "invalid_questions": total - valid,
            "validation_rate": round((valid / total * 100), 2) if total > 0 else 0,
            "issues": issues
        }
    
    def _validate_single_question(self, question: Dict[str, Any]) -> tuple:
        """Validate a single question"""
        
        issues = []
        
        # Check required fields
        required_fields = ['question_text', 'options', 'correct_answer']
        for field in required_fields:
            if field not in question or not question[field]:
                issues.append(f"Missing or empty field: {field}")
        
        # Check options count
        options = question.get('options', [])
        if len(options) != 4:
            issues.append(f"Expected 4 options, got {len(options)}")
        
        # ✅ Check for duplicate options
        option_texts = [opt.get('option_text', '').lower() for opt in options]
        if len(option_texts) != len(set(option_texts)):
            issues.append("Duplicate options detected")
        
        # Check exactly one correct answer
        correct_count = sum(1 for opt in options if opt.get('is_correct', False))
        if correct_count != 1:
            issues.append(f"Expected 1 correct answer, got {correct_count}")
        
        # Check option text lengths
        for i, opt in enumerate(options):
            if len(opt.get('option_text', '')) > 200:  # ✅ Increased to match new limit
                issues.append(f"Option {i+1} is too long (>200 chars)")
        
        # Check question text length
        if len(question.get('question_text', '')) < 10:
            issues.append("Question text is too short")
        
        return (len(issues) == 0, issues)