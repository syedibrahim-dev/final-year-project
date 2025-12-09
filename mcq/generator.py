"""
Extended MCQ generation utilities
Can be used for advanced MCQ generation features
"""

from typing import List, Dict, Any

def validate_mcq_structure(questions: List[Dict[str, Any]]) -> bool:
    """Validate MCQ structure"""
    required_keys = ["question_text", "options", "correct_answer", "explanation"]
    
    for q in questions:
        if not all(key in q for key in required_keys):
            return False
        
        if len(q["options"]) != 4:
            return False
        
        correct_count = sum(1 for opt in q["options"] if opt.get("is_correct", False))
        if correct_count != 1:
            return False
    
    return True


def calculate_difficulty_score(attempt_results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate difficulty scores based on user performance"""
    difficulty_stats = {
        "easy": {"total": 0, "correct": 0},
        "medium": {"total": 0, "correct": 0},
        "hard": {"total": 0, "correct": 0}
    }
    
    for result in attempt_results:
        difficulty = result.get("difficulty", "medium")
        difficulty_stats[difficulty]["total"] += 1
        if result.get("is_correct", False):
            difficulty_stats[difficulty]["correct"] += 1
    
    scores = {}
    for diff, stats in difficulty_stats.items():
        if stats["total"] > 0:
            scores[diff] = (stats["correct"] / stats["total"]) * 100
        else:
            scores[diff] = 0.0
    
    return scores