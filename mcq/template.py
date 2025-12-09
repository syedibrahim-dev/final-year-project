from langchain_core.prompts import PromptTemplate

MCQ_STEM_TEMPLATE = PromptTemplate(
    input_variables=["context", "concept", "difficulty", "stage", "persona"],
    template="""You are an expert sales training question creator. Generate ONE high-quality multiple-choice question stem (question without options).

Context (Training Material):
{context}

Target Concept: {concept}
Sales Stage: {stage}
Target Persona: {persona}
Difficulty: {difficulty}

Requirements:
1. Question MUST be directly based on the provided context
2. Question should test understanding of {concept}
3. Appropriate for {persona} at {difficulty} difficulty
4. Relevant to {stage} sales stage
5. Clear and unambiguous
6. No trick questions

Format:
QUESTION: [Your question here - should be 1-2 sentences]
LEARNING_OBJECTIVE: [What this question tests]
BLOOM_LEVEL: [Remember/Understand/Apply/Analyze]

Generate the question stem now:"""
)

MCQ_DISTRACTOR_TEMPLATE = PromptTemplate(
    input_variables=["question", "correct_answer", "context", "num_distractors"],
    template="""You are an expert at creating plausible but incorrect answer options (distractors) for sales training MCQs.

Question: {question}
Correct Answer: {correct_answer}

Context:
{context}

Generate {num_distractors} plausible but INCORRECT distractors that:
1. Are realistic and could fool someone who doesn't know the material
2. Are at a similar level of detail as the correct answer
3. Don't contain obvious errors or absurdities
4. Are grammatically parallel to the correct answer
5. Test common misconceptions

Format each distractor as:
DISTRACTOR: [distractor text]
REASONING: [why someone might choose this]
---

Generate {num_distractors} distractors now:"""
)

MCQ_EXPLANATION_TEMPLATE = PromptTemplate(
    input_variables=["question", "correct_answer", "context"],
    template="""Create a brief, clear explanation for why the correct answer is right.

Question: {question}
Correct Answer: {correct_answer}

Context:
{context}

Requirements:
1. Explain WHY the answer is correct (not just repeat it)
2. Reference the training material
3. Keep it concise (2-3 sentences)
4. Educational and constructive

EXPLANATION: """
)