from typing import Dict, List
from pydantic import BaseModel, Field

class RubricCriterion(BaseModel):
    """Single evaluation criterion"""
    name: str
    description: str
    weight: float = Field(ge=0, le=1)  # 0-1
    max_score: int = Field(ge=1, le=5)  # 1-5

class EvaluationRubric:
    """Rubric for evaluating MCQ quality"""
    
    def __init__(self):
        self.criteria = {
            "relevance": RubricCriterion(
                name="Relevance",
                description="Question tests the intended concept and aligns with learning objectives",
                weight=0.25,
                max_score=5
            ),
            "correctness": RubricCriterion(
                name="Correctness",
                description="Correct answer is indisputably correct and grounded in training material",
                weight=0.25,
                max_score=5
            ),
            "stage_fit": RubricCriterion(
                name="Stage Fit",
                description="Question is appropriate for the target sales stage",
                weight=0.15,
                max_score=5
            ),
            "persona_fit": RubricCriterion(
                name="Persona Fit",
                description="Question difficulty and content match target persona's level",
                weight=0.15,
                max_score=5
            ),
            "plausibility": RubricCriterion(
                name="Distractor Plausibility",
                description="Distractors are plausible and test understanding (not obviously wrong)",
                weight=0.15,
                max_score=5
            ),
            "independence": RubricCriterion(
                name="Independence",
                description="Question can be answered without external knowledge or trick reasoning",
                weight=0.05,
                max_score=5
            )
        }
    
    def get_criteria(self) -> Dict[str, RubricCriterion]:
        """Get all evaluation criteria"""
        return self.criteria
    
    def calculate_total_score(self, scores: Dict[str, int]) -> float:
        """
        Calculate weighted total score
        
        Args:
            scores: Dict mapping criterion name to score (1-5)
            
        Returns:
            Weighted total score (0-100)
        """
        if not scores:
            return 0.0
        
        total = 0.0
        for criterion_name, score in scores.items():
            if criterion_name in self.criteria:
                criterion = self.criteria[criterion_name]
                # Normalize score to 0-1, then apply weight
                normalized_score = (score - 1) / (criterion.max_score - 1)
                total += normalized_score * criterion.weight
        
        return total * 100  # Convert to 0-100 scale
    
    def get_feedback(self, scores: Dict[str, int]) -> List[str]:
        """
        Generate feedback based on scores
        
        Args:
            scores: Dict mapping criterion name to score
            
        Returns:
            List of feedback strings
        """
        feedback = []
        
        for criterion_name, score in scores.items():
            if criterion_name not in self.criteria:
                continue
            
            criterion = self.criteria[criterion_name]
            
            if score < 3:
                feedback.append(
                    f"❌ {criterion.name}: Needs improvement - {criterion.description}"
                )
            elif score == 3:
                feedback.append(
                    f"⚠️  {criterion.name}: Acceptable but could be better"
                )
            else:
                feedback.append(
                    f"✅ {criterion.name}: Good quality"
                )
        
        return feedback