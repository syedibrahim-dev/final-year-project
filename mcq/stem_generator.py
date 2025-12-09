"""
StemGenerator: Generates question stems (question text without options)
Uses LLM to create diverse, contextually relevant questions
"""

from typing import List, Dict, Any
import json
import re
from difflib import SequenceMatcher

from langchain_community.llms import Ollama
from config.settings import settings


class StemGenerator:
    """Generates question stems from context"""
    
    def __init__(self):
        self.llm = Ollama(
            model=settings.LOCAL_LLM_MODEL,
            base_url=settings.LOCAL_LLM_BASE_URL,
            temperature=0.7,
            num_ctx=4096
        )
    
    def generate_stems(
        self,
        context: str,
        topic: str,
        difficulty: str,
        num_questions: int
    ) -> List[Dict[str, Any]]:
        """
        Generate question stems from training content
        ✅ NEW: Ensures questions are unique and diverse
        
        Args:
            context: Training material text
            topic: Subject area
            difficulty: easy, medium, or hard
            num_questions: Number of questions to generate
        
        Returns:
            List of exactly num_questions unique stem objects
        """
        
        all_stems = []
        max_attempts = 10  # Increased attempts
        
        print(f"   ℹ️  Generating {num_questions} diverse stems")
        
        for attempt in range(max_attempts):
            if len(all_stems) >= num_questions:
                break
            
            remaining = num_questions - len(all_stems)
            print(f"   🔄 Attempt {attempt + 1}/{max_attempts} (need {remaining} more)...", end=" ", flush=True)
            
            # ✅ Generate with diversity enforcement
            batch_stems = self._generate_diverse_questions(
                context=context,
                topic=topic,
                difficulty=difficulty,
                existing_questions=[s['stem_text'] for s in all_stems],
                num_needed=remaining
            )
            
            if batch_stems:
                # ✅ Filter out duplicates
                unique_stems = self._filter_duplicates(batch_stems, all_stems)
                all_stems.extend(unique_stems)
                print(f"✅ Got {len(unique_stems)} unique (total: {len(all_stems)})")
            else:
                print("❌ Failed, retrying...")
        
        # ✅ GUARANTEED FALLBACK: If still not enough, generate diverse questions
        if len(all_stems) < num_questions:
            print(f"   ⚠️  Only got {len(all_stems)}, generating diverse fallback questions...")
            fallback_stems = self._generate_diverse_fallback_questions(
                topic=topic,
                difficulty=difficulty,
                existing_questions=[s['stem_text'] for s in all_stems],
                num_needed=num_questions - len(all_stems)
            )
            all_stems.extend(fallback_stems)
            print(f"   ✅ Added {len(fallback_stems)} fallback questions (total: {len(all_stems)})")
        
        return all_stems[:num_questions]
    
    def _generate_diverse_questions(
        self,
        context: str,
        topic: str,
        difficulty: str,
        existing_questions: List[str],
        num_needed: int
    ) -> List[Dict[str, Any]]:
        """
        ✅ NEW: Generate diverse questions with explicit anti-duplication instructions
        """
        
        difficulty_guide = self._get_difficulty_instructions(difficulty)
        
        # ✅ Show existing questions to avoid duplicates
        existing_text = ""
        if existing_questions:
            existing_text = "\n**EXISTING QUESTIONS (DO NOT REPEAT THESE):**\n"
            for i, q in enumerate(existing_questions[-3:], 1):  # Show last 3
                existing_text += f"{i}. {q}\n"
        
        prompt = f"""Generate {num_needed} UNIQUE and DIVERSE multiple-choice questions about {topic}.

**TRAINING MATERIAL:**
{context[:1000]}

**TOPIC:** {topic}
**DIFFICULTY:** {difficulty}

{existing_text}

{difficulty_guide}

**CRITICAL DIVERSITY RULES:**
1. Each question must test a DIFFERENT concept/aspect
2. Use DIFFERENT question words (what, how, why, which, when, where)
3. DO NOT repeat existing questions
4. DO NOT create variations of the same question
5. Questions must be 10-20 words
6. Each question must end with '?'

**Generate {num_needed} DIVERSE questions (JSON format):**
[
  {{"stem_text": "Different question 1?", "cognitive_level": "remember"}},
  {{"stem_text": "Different question 2?", "cognitive_level": "understand"}},
  ...
]

JSON only:"""

        try:
            response = self.llm.invoke(prompt).strip()
            stems = self._extract_json_from_response(response)
            
            if not stems:
                stems = self._extract_questions_manually(response, topic, difficulty)
            
            # Validate and add metadata
            valid_stems = []
            for stem in stems:
                if self._is_valid_question(stem.get('stem_text', '')):
                    stem['topic'] = topic
                    stem['difficulty'] = difficulty
                    if 'cognitive_level' not in stem:
                        stem['cognitive_level'] = self._determine_cognitive_level(stem['stem_text'])
                    if 'key_concept' not in stem:
                        stem['key_concept'] = self._extract_key_concept(stem['stem_text'])
                    valid_stems.append(stem)
            
            return valid_stems
            
        except Exception as e:
            print(f"\n      ⚠️  Error: {e}")
            return []
    
    def _filter_duplicates(
        self,
        new_stems: List[Dict[str, Any]],
        existing_stems: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        ✅ NEW: Filter out duplicate or too-similar questions
        Uses Levenshtein similarity
        """
        
        unique = []
        existing_texts = [s['stem_text'].lower() for s in existing_stems]
        
        for stem in new_stems:
            stem_text = stem['stem_text'].lower()
            
            # Check if it's too similar to any existing question
            is_duplicate = False
            for existing_text in existing_texts:
                similarity = self._calculate_similarity(stem_text, existing_text)
                
                if similarity > 0.75:  # 75% similarity threshold
                    is_duplicate = True
                    print(f"\n      🔄 Skipped similar: {stem['stem_text'][:60]}")
                    break
            
            if not is_duplicate:
                unique.append(stem)
                existing_texts.append(stem_text)
        
        return unique
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0.0 to 1.0)"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _extract_key_concept(self, question: str) -> str:
        """Extract key concept from question"""
        
        # Remove question words
        question_words = ['what', 'which', 'who', 'when', 'where', 'why', 'how', 'is', 'are', 'can', 'does']
        words = question.lower().split()
        
        # Get meaningful words (not question words)
        key_words = [w for w in words if w not in question_words and len(w) > 3]
        
        if key_words:
            return ' '.join(key_words[:3])
        
        return question[:50]
    
    def _generate_diverse_fallback_questions(
        self,
        topic: str,
        difficulty: str,
        existing_questions: List[str],
        num_needed: int
    ) -> List[Dict[str, Any]]:
        """
        ✅ IMPROVED: Generate diverse fallback questions with different aspects
        """
        
        # ✅ Diverse question templates covering different aspects
        templates = {
            'easy': [
                # Definition questions
                (f"What is {topic}?", "definition"),
                (f"What does {topic} stand for?", "acronym"),
                (f"What is the main purpose of {topic}?", "purpose"),
                (f"What are the key components of {topic}?", "components"),
                (f"What type of technology is {topic}?", "classification"),
                
                # Feature questions
                (f"What are the basic features of {topic}?", "features"),
                (f"What benefits does {topic} provide?", "benefits"),
                (f"Which industry commonly uses {topic}?", "industry"),
                (f"What problem does {topic} solve?", "problem"),
                (f"When is {topic} typically used?", "usage"),
                
                # Comparison questions
                (f"What distinguishes {topic} from similar technologies?", "distinction"),
                (f"Which organizations need {topic}?", "target_users"),
            ],
            'medium': [
                # Process questions
                (f"How does {topic} work?", "process"),
                (f"How is {topic} implemented in organizations?", "implementation"),
                (f"What steps are involved in {topic} deployment?", "steps"),
                (f"How do you configure {topic}?", "configuration"),
                
                # Relationship questions
                (f"Why is {topic} important for security?", "importance"),
                (f"What happens when {topic} fails?", "failure"),
                (f"How does {topic} integrate with existing systems?", "integration"),
                (f"What are the advantages of using {topic}?", "advantages"),
                
                # Application questions
                (f"When should organizations implement {topic}?", "timing"),
                (f"Which scenarios require {topic}?", "scenarios"),
                (f"How does {topic} improve operational efficiency?", "efficiency"),
            ],
            'hard': [
                # Analysis questions
                (f"How would you evaluate the effectiveness of {topic}?", "evaluation"),
                (f"What factors determine successful {topic} implementation?", "success_factors"),
                (f"How does {topic} compare to alternative solutions?", "comparison"),
                (f"What challenges arise when implementing {topic}?", "challenges"),
                
                # Optimization questions
                (f"How can {topic} be optimized for large enterprises?", "optimization"),
                (f"What trade-offs exist when choosing {topic}?", "tradeoffs"),
                (f"How does {topic} scale across different organization sizes?", "scalability"),
                
                # Strategic questions
                (f"What are the long-term implications of adopting {topic}?", "implications"),
                (f"How should organizations decide whether to adopt {topic}?", "decision"),
                (f"What criteria measure {topic} success?", "criteria"),
            ]
        }
        
        available_templates = templates.get(difficulty, templates['medium'])
        
        # ✅ Filter out templates similar to existing questions
        unique_templates = []
        existing_lower = [q.lower() for q in existing_questions]
        
        for template_text, concept_type in available_templates:
            is_similar = False
            for existing_q in existing_lower:
                if self._calculate_similarity(template_text.lower(), existing_q) > 0.75:
                    is_similar = True
                    break
            
            if not is_similar:
                unique_templates.append((template_text, concept_type))
        
        # Generate stems from unique templates
        stems = []
        for i in range(min(num_needed, len(unique_templates))):
            template_text, concept_type = unique_templates[i]
            stems.append({
                "stem_text": template_text,
                "topic": topic,
                "difficulty": difficulty,
                "cognitive_level": self._determine_cognitive_level(template_text),
                "key_concept": concept_type
            })
        
        return stems
    
    def _clean_question_text(self, text: str) -> str:
        """Clean and format question text"""
        
        text = re.sub(r'^(Question|Q\d+|Here is|Here\'s)[\s:\-\.]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\d+[\.\)]\s*', '', text)
        text = text.strip('"\'')
        text = ' '.join(text.split())
        
        if text and not text.endswith('?'):
            text += '?'
        
        return text.strip()
    
    def _is_valid_question(self, question: str) -> bool:
        """Check if question is valid"""
        
        if not question or len(question) < 10:
            return False
        
        if not question.endswith('?'):
            return False
        
        word_count = len(question.split())
        if word_count < 5 or word_count > 30:
            return False
        
        question_words = ['what', 'which', 'who', 'when', 'where', 'why', 'how', 'is', 'are', 'can', 'does', 'do']
        if not any(word in question.lower() for word in question_words):
            return False
        
        return True
    
    def _determine_cognitive_level(self, question: str) -> str:
        """Determine cognitive level from question text"""
        
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['analyze', 'evaluate', 'compare', 'contrast', 'justify', 'assess']):
            return 'analyze'
        elif any(word in question_lower for word in ['apply', 'demonstrate', 'solve', 'use', 'implement']):
            return 'apply'
        elif any(word in question_lower for word in ['explain', 'describe', 'summarize', 'interpret', 'how', 'why']):
            return 'understand'
        else:
            return 'remember'
    
    def _get_difficulty_instructions(self, difficulty: str) -> str:
        """Get difficulty-specific instructions"""
        
        if difficulty == "easy":
            return """**EASY QUESTIONS - Focus on:**
- Basic definitions and facts
- Simple recall
- Question starters: "What is...", "What are...", "Define...", "List..."
"""
        
        elif difficulty == "medium":
            return """**MEDIUM QUESTIONS - Focus on:**
- Concepts and relationships
- Understanding and application
- Question starters: "How does...", "Why is...", "What happens when...", "How do you..."
"""
        
        else:  # hard
            return """**HARD QUESTIONS - Focus on:**
- Analysis and evaluation
- Critical thinking
- Question starters: "How would you...", "Compare...", "What factors...", "Evaluate..."
"""
    
    def _extract_json_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Extract JSON array from LLM response"""
        
        try:
            json_match = re.search(r'\[[\s\S]*\]', response)
            
            if json_match:
                json_str = json_match.group(0)
                stems = json.loads(json_str)
                
                if isinstance(stems, list):
                    return stems
            
            stems = json.loads(response)
            if isinstance(stems, list):
                return stems
            
            return []
            
        except json.JSONDecodeError:
            return []
    
    def _extract_questions_manually(
        self,
        response: str,
        topic: str,
        difficulty: str
    ) -> List[Dict[str, Any]]:
        """Fallback: Extract questions manually from text"""
        
        stems = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if not line or not line.endswith('?'):
                continue
            
            line = re.sub(r'^[\d\.\)\-\*\"\'\s]+', '', line)
            line = line.strip('"\'')
            
            if len(line) > 10 and '?' in line:
                stems.append({
                    "stem_text": line,
                    "topic": topic,
                    "difficulty": difficulty,
                    "cognitive_level": self._determine_cognitive_level(line),
                    "key_concept": self._extract_key_concept(line)
                })
        
        return stems
    
    def _validate_stem(self, stem: Dict[str, Any]) -> bool:
        """Validate a question stem"""
        
        if not isinstance(stem, dict):
            return False
        
        stem_text = stem.get('stem_text', '').strip()
        
        if not stem_text:
            return False
        
        if not stem_text.endswith('?'):
            return False
        
        if len(stem_text) < 10 or len(stem_text) > 200:
            return False
        
        word_count = len(stem_text.split())
        if word_count < 5:
            return False
        
        if 'topic' not in stem:
            stem['topic'] = 'General'
        if 'difficulty' not in stem:
            stem['difficulty'] = 'medium'
        if 'cognitive_level' not in stem:
            stem['cognitive_level'] = 'understand'
        if 'key_concept' not in stem:
            stem['key_concept'] = stem_text[:50]
        
        return True