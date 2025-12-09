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
from services.rag_service import retrieve_relevant_chunks


class MCQPipeline:
    """Complete MCQ generation pipeline"""
    
    def __init__(self):
        self.stem_generator = StemGenerator()
        self.distractor_generator = DistractorGenerator()
        self.distractor_filter = DistractorFilter(min_plausibility=0.4)
    
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
            k=3
        )
        
        if not context_chunks:
            raise ValueError("No training content found for this topic. Please upload training materials first.")
        
        # Limit context to 1500 chars for faster processing
        context = "\n\n".join([chunk["chunk"] for chunk in context_chunks])[:1500]
        print(f"   ✅ Retrieved {len(context_chunks)} context chunks ({len(context)} chars)")
        
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
        
        final_questions = complete_questions[:num_questions]
        
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
        raw_distractors = self.distractor_generator.generate_distractors_simple(
            stem=stem_text,
            correct_answer=correct_answer,
            context=context,
            num_distractors=3
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
            model=settings.LOCAL_LLM_MODEL,
            base_url=settings.LOCAL_LLM_BASE_URL,
            temperature=0.3,
            num_ctx=2048
        )
        
        prompt = f"""Based on the training material below, provide a SHORT and CONCISE answer to the question.

IMPORTANT RULES:
- Maximum 15 words
- Be specific and factual
- Use simple language
- Answer directly

Training Material:
{context[:800]}

Question: {stem}

Provide ONLY the answer (maximum 15 words):"""
        
        try:
            answer = llm.invoke(prompt).strip()
            
            # Clean up the answer
            answer = answer.replace('\n', ' ').strip()
            answer = answer.strip('"\'')
            
            # Truncate if too long
            if len(answer) > 120:
                sentences = answer.split('.')
                answer = sentences[0].strip()
                if len(answer) > 120:
                    answer = answer[:117] + "..."
            
            return answer
            
        except Exception as e:
            print(f"\n      ⚠️  Answer generation failed: {e}")
            return "Correct answer based on training material"
    
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
        if len(correct_text) > 120:
            correct_text = correct_text[:117] + "..."
        
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
            
            # Truncate if too long
            if len(distractor_text) > 120:
                distractor_text = distractor_text[:117] + "..."
            
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
        ✅ NEW: Generate emergency contextual distractor
        Used when we absolutely need more options
        """
        
        templates = [
            f"Related to {topic} but not applicable here",
            f"Common misconception in {topic}",
            f"Partial understanding of {topic}",
            f"Applies to different {topic} scenario",
            f"Outdated {topic} approach",
            f"Incomplete {topic} explanation",
            f"Confusion with related concept",
            "Not the primary purpose"
        ]
        
        for template in templates:
            if template.lower() not in [t.lower() for t in existing_texts]:
                return template
        
        # Last resort
        return f"Alternative but incorrect interpretation"
    
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
        """Generate a simple explanation"""
        
        answer_preview = correct_answer[:80] + "..." if len(correct_answer) > 80 else correct_answer
        
        return f"The correct answer is based on the training material covering {topic}. {answer_preview}"
    
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
            if len(opt.get('option_text', '')) > 150:
                issues.append(f"Option {i+1} is too long (>150 chars)")
        
        # Check question text length
        if len(question.get('question_text', '')) < 10:
            issues.append("Question text is too short")
        
        return (len(issues) == 0, issues)