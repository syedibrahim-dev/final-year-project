"""
Simple MCQ service - now only used for evaluation
Generation is handled by mcq.pipeline
"""

from typing import List, Dict, Any

def evaluate_mcq_attempt(
    questions: List[Dict[str, Any]],
    user_answers: List[str]
) -> Dict[str, Any]:
    """
    Evaluate user's MCQ attempt
    Returns: {score, correct_answers, total_questions, detailed_results}
    """
    if len(questions) != len(user_answers):
        raise ValueError("Number of answers must match number of questions")
    
    correct_count = 0
    detailed_results = []
    
    for i, question in enumerate(questions):
        user_answer = user_answers[i]
        correct_answer = question["correct_answer"]
        
        is_correct = user_answer.upper() == correct_answer.upper()
        if is_correct:
            correct_count += 1
        
        detailed_results.append({
            "question_index": i,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "explanation": question.get("explanation", "")
        })
    
    total = len(questions)
    score = (correct_count / total) * 100
    
    return {
        "score": score,
        "correct_answers": correct_count,
        "total_questions": total,
        "detailed_results": detailed_results
    }