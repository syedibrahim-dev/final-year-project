"""
LLM prompt templates for MCQ generation
"""

def get_mcq_generation_prompt(context: str, topic: str, difficulty: str, num_questions: int) -> str:
    """Generate MCQ prompt with context"""
    
    return f"""You are an expert sales trainer creating a multiple-choice quiz.

**Context from training materials:**
{context}

**Task:** Generate {num_questions} multiple-choice questions about "{topic}" at {difficulty} difficulty level.

**Requirements:**
1. Each question must have 4 options (A, B, C, D)
2. Only ONE correct answer per question
3. Include a brief explanation for the correct answer
4. Base questions on the provided context
5. Difficulty: {difficulty}
6. Make questions practical and scenario-based

**Output Format (JSON):**
{{
  "questions": [
    {{
      "question_text": "Question text here?",
      "options": [
        {{"option_text": "Option A text", "is_correct": false}},
        {{"option_text": "Option B text", "is_correct": true}},
        {{"option_text": "Option C text", "is_correct": false}},
        {{"option_text": "Option D text", "is_correct": false}}
      ],
      "correct_answer": "B",
      "explanation": "Explanation of why B is correct based on the training material",
      "difficulty": "{difficulty}",
      "topic": "{topic}"
    }}
  ]
}}

Generate the questions now:"""


def get_scenario_based_prompt(scenario: str, difficulty: str) -> str:
    """Generate scenario-based MCQ prompt"""
    
    return f"""You are an expert sales trainer. Based on the following scenario, create a challenging multiple-choice question.

**Scenario:**
{scenario}

**Difficulty:** {difficulty}

**Task:** Create ONE multiple-choice question that tests the trainee's understanding of this scenario.

**Output Format (JSON):**
{{
  "question_text": "Based on the scenario, what should you do?",
  "options": [
    {{"option_text": "Option A", "is_correct": false}},
    {{"option_text": "Option B", "is_correct": true}},
    {{"option_text": "Option C", "is_correct": false}},
    {{"option_text": "Option D", "is_correct": false}}
  ],
  "correct_answer": "B",
  "explanation": "Detailed explanation",
  "difficulty": "{difficulty}",
  "topic": "scenario_analysis"
}}

Generate the question now:"""