from typing import Dict, List, Optional
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from config.settings import settings
from .rubric import EvaluationRubric

class MCQEvaluator:
    """Evaluates MCQ quality using LLM and rubric"""
    
    def __init__(
        self,
        rubric: Optional[EvaluationRubric] = None,
        llm_model: str = None
    ):
        self.rubric = rubric or EvaluationRubric()
        self.llm = OllamaLLM(
            model=llm_model or settings.MCQ_LLM_MODEL,
            temperature=0.3,  # Lower temperature for more consistent evaluation
            base_url=settings.LOCAL_LLM_BASE_URL,
            num_gpu=getattr(settings, 'EVAL_NUM_GPU', 0)  # GPU MODE (revert): set EVAL_NUM_GPU=22 in settings.py
        )
    
    def evaluate_mcq(
        self,
        question: str,
        options: List[Dict],
        correct_answer: str,
        context: str,
        concept: str,
        stage: str,
        persona: str,
        difficulty: str
    ) -> Dict:
        """
        Evaluate a single MCQ using the rubric
        
        Returns:
            Dict with scores, total_score, feedback, and pass/fail
        """
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            question, options, correct_answer, context,
            concept, stage, persona, difficulty
        )
        
        # Get LLM evaluation
        response = self.llm.invoke(prompt)
        
        # Parse scores
        scores = self._parse_evaluation_response(response)
        
        # Calculate total score
        total_score = self.rubric.calculate_total_score(scores)
        
        # Generate feedback
        feedback = self.rubric.get_feedback(scores)
        
        # Determine pass/fail (threshold: 70%)
        passed = total_score >= 70
        
        return {
            "scores": scores,
            "total_score": total_score,
            "feedback": feedback,
            "passed": passed,
            "raw_evaluation": response
        }
    
    def _build_evaluation_prompt(
        self,
        question: str,
        options: List[Dict],
        correct_answer: str,
        context: str,
        concept: str,
        stage: str,
        persona: str,
        difficulty: str
    ) -> str:
        """Build comprehensive evaluation prompt"""
        
        options_text = "\n".join([
            f"{'✓' if opt.get('is_correct') else ' '} {opt['text']}"
            for opt in options
        ])
        
        criteria_text = "\n".join([
            f"{name.upper()}: {criterion.description}"
            for name, criterion in self.rubric.criteria.items()
        ])
        
        template = f"""You are an expert in educational assessment. Evaluate the following multiple-choice question based on the rubric provided.

QUESTION:
{question}

OPTIONS:
{options_text}

CORRECT ANSWER: {correct_answer}

CONTEXT (Training Material):
{context[:1500]}

TARGET METADATA:
- Concept: {concept}
- Sales Stage: {stage}
- Target Persona: {persona}
- Difficulty: {difficulty}

EVALUATION RUBRIC (Score each 1-5, where 1=Poor, 3=Acceptable, 5=Excellent):
{criteria_text}

Evaluate the question on each criterion. For each criterion, provide:
1. A score (1-5)
2. Brief justification

Format your response as:
RELEVANCE: [score] - [justification]
CORRECTNESS: [score] - [justification]
STAGE_FIT: [score] - [justification]
PERSONA_FIT: [score] - [justification]
PLAUSIBILITY: [score] - [justification]
INDEPENDENCE: [score] - [justification]

Begin evaluation:"""
        
        return template
    
    def _parse_evaluation_response(self, response: str) -> Dict[str, int]:
        """Parse LLM evaluation response into scores"""
        scores = {}
        
        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for criterion names
            for criterion_name in self.rubric.criteria.keys():
                if line.upper().startswith(criterion_name.upper().replace("_", "")):
                    # Extract score (first number after colon)
                    try:
                        # Split by colon and get first part with numbers
                        parts = line.split(":")
                        if len(parts) > 1:
                            score_part = parts[1].split("-")[0].strip()
                            # Extract first digit
                            for char in score_part:
                                if char.isdigit():
                                    score = int(char)
                                    if 1 <= score <= 5:
                                        scores[criterion_name] = score
                                    break
                    except (ValueError, IndexError):
                        continue
        
        # Fill in missing scores with default (3 = acceptable)
        for criterion_name in self.rubric.criteria.keys():
            if criterion_name not in scores:
                scores[criterion_name] = 3
        
        return scores
    
    def evaluate_mcq_set(
        self,
        mcqs: List[Dict],
        context: str
    ) -> Dict:
        """
        Evaluate a set of MCQs
        
        Returns:
            Dict with overall metrics and individual evaluations
        """
        evaluations = []
        
        for i, mcq in enumerate(mcqs):
            try:
                # Extract data from MCQ
                question = mcq.get("question", "")
                options = mcq.get("options", [])
                correct_answer = next(
                    (opt["text"] for opt in options if opt.get("is_correct")),
                    ""
                )
                
                metadata = mcq.get("metadata", {})
                
                # Evaluate
                eval_result = self.evaluate_mcq(
                    question=question,
                    options=options,
                    correct_answer=correct_answer,
                    context=context,
                    concept=metadata.get("concept", "unknown"),
                    stage=metadata.get("stage", "general"),
                    persona=metadata.get("persona", "sales rep"),
                    difficulty=mcq.get("difficulty", "medium")
                )
                
                eval_result["question_index"] = i + 1
                evaluations.append(eval_result)
                
            except Exception as e:
                print(f"⚠️  Error evaluating MCQ {i+1}: {e}")
                continue
        
        # Calculate overall metrics
        if evaluations:
            avg_score = sum(e["total_score"] for e in evaluations) / len(evaluations)
            pass_rate = sum(1 for e in evaluations if e["passed"]) / len(evaluations) * 100
        else:
            avg_score = 0
            pass_rate = 0
        
        return {
            "evaluations": evaluations,
            "overall_metrics": {
                "average_score": avg_score,
                "pass_rate": pass_rate,
                "total_evaluated": len(evaluations),
                "passed": sum(1 for e in evaluations if e["passed"]),
                "failed": sum(1 for e in evaluations if not e["passed"])
            }
        }