from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class MCQGenerateRequest(BaseModel):
    topic: str
    difficulty: str = Field(..., pattern="^(easy|medium|hard)$")
    num_questions: int = Field(5, ge=1, le=20)

class MCQOption(BaseModel):
    option_text: str
    is_correct: bool

class MCQQuestion(BaseModel):
    question_text: str
    options: List[MCQOption]
    correct_answer: str
    explanation: str
    difficulty: str
    topic: str

class MCQTestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    topic: str
    difficulty: str
    questions: List[MCQQuestion]

class MCQTestOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    topic: str
    difficulty: str
    questions_json: List[Dict[str, Any]]
    created_by: int
    organization_id: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class MCQAttemptSubmit(BaseModel):
    test_id: int
    answers: List[str]
    time_taken_seconds: Optional[int] = None

class MCQAttemptOut(BaseModel):
    id: int
    test_id: int
    user_id: int
    score: float
    correct_answers: int
    total_questions: int
    time_taken_seconds: Optional[int]
    started_at: datetime
    completed_at: datetime
    
    class Config:
        from_attributes = True