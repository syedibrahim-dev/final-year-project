"""
Conversation evaluation module for roleplay sessions
Uses LLM to analyze sales conversations and provide structured feedback
Enhanced with: hybrid scoring, difficulty-aware evaluation, per-category insights,
and document-grounded product accuracy fact-checking
"""
from typing import Dict, Any, List, Optional
from models.roleplay import RoleplayPersona, RoleplayMessage
from roleplay.llm_client import OllamaClient
from config.settings import settings
import json
import logging

logger = logging.getLogger(__name__)


class ConversationEvaluator:
    """Evaluates roleplay conversations and generates structured feedback"""
    
    def __init__(self):
        self.llm_client = OllamaClient()
    
    def evaluate_conversation(
        self,
        messages: List[RoleplayMessage],
        persona: RoleplayPersona,
        org_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a completed conversation with hybrid LLM scoring.
        When org_id is provided, includes product accuracy fact-checking.
        
        Returns:
            Dict with summary, strengths, improvements, and per-category LLM scores
        """
        
        # Build conversation transcript (summarize if too long)
        transcript = self._build_transcript(messages, persona.name)
        
        # Create evaluation prompt (with document context if available)
        evaluation_prompt = self._build_evaluation_prompt(transcript, persona, org_id=org_id)
        
        # Get LLM evaluation
        try:
            response = self.llm_client.generate_response(
                system_prompt=self._get_system_prompt(),
                user_message=evaluation_prompt,
                max_tokens=700,  # Slightly more tokens for product_accuracy category
                timeout=None
            )
            
            # Parse JSON response
            evaluation = self._parse_evaluation(response)
            
            return evaluation
            
        except Exception as e:
            raise Exception(f"Evaluation failed: {str(e)}")
    
    def _build_transcript(self, messages: List[RoleplayMessage], persona_name: str) -> str:
        """Format messages into readable transcript. Summarize if too long."""
        
        # If conversation is very long, use a summary approach
        if len(messages) > 20:
            # Include first 4, middle 4, and last 8 messages
            key_messages = messages[:4] + messages[len(messages)//2-2:len(messages)//2+2] + messages[-8:]
            transcript_lines = []
            for i, msg in enumerate(key_messages):
                speaker = "Trainee" if msg.sender == "trainee" else persona_name
                transcript_lines.append(f"{speaker}: {msg.message_text}")
                if i == 3:
                    transcript_lines.append(f"[... {len(messages) - 16} messages omitted for brevity ...]")
                elif i == 7:
                    transcript_lines.append("[... end of middle section ...]")
            return "\n".join(transcript_lines)
        
        transcript_lines = []
        for msg in messages:
            speaker = "Trainee" if msg.sender == "trainee" else persona_name
            transcript_lines.append(f"{speaker}: {msg.message_text}")
        
        return "\n".join(transcript_lines)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for evaluation"""
        
        return """You are an expert sales coach evaluating a trainee's performance. 
Analyze the conversation and respond ONLY with valid JSON in the exact format specified.

Your evaluation should be:
1. SPECIFIC - reference actual things said in the conversation
2. ACTIONABLE - give concrete suggestions, not vague advice
3. BALANCED - acknowledge good moments even in weak performances
4. DIFFICULTY-AWARE - consider the persona's difficulty level

Respond ONLY with valid JSON. No text before or after the JSON."""
    
    def _build_evaluation_prompt(self, transcript: str, persona: RoleplayPersona, org_id: Optional[int] = None) -> str:
        """Build evaluation prompt with per-category scoring, difficulty context, and optional product fact-checking."""
        
        difficulty_context = {
            "beginner": "This was an EASY persona. Be encouraging but still point out gaps. The trainee should score well if they followed basic sales flow.",
            "intermediate": "This was a MODERATE persona. Expect solid discovery, clear value presentation, and professional objection handling.",
            "advanced": "This was a CHALLENGING persona. Only give high marks for truly exceptional performance. The trainee had to earn every bit of trust."
        }
        
        difficulty_note = difficulty_context.get(persona.difficulty, difficulty_context["intermediate"])
        
        # Retrieve document context for product accuracy checking
        product_reference_section = ""
        product_accuracy_category = ""
        if org_id:
            from roleplay.prompts import retrieve_document_context
            # Use a broad query to get product info relevant to the conversation
            doc_context = retrieve_document_context(
                query="product features pricing implementation competitors objections",
                org_id=org_id,
                k=5
            )
            if doc_context:
                logger.info(f"📋 Retrieved {len(doc_context)} chars of document context for evaluation")
                product_reference_section = f"""\n\nPRODUCT REFERENCE MATERIAL (use this to fact-check the trainee's claims):
{doc_context}
\nIMPORTANT: Compare what the trainee said about the product against the reference material above. Flag any inaccurate claims, incorrect pricing, or misrepresented features."""
                
                product_accuracy_category = """,
    "product_accuracy": {{
      "score": <1-5>,
      "comment": "Did the trainee's product claims match the reference material? Flag any inaccuracies or misrepresentations."
    }}"""
        
        return f"""Evaluate this sales conversation:

CUSTOMER PERSONA: {persona.name} ({persona.difficulty} difficulty, {persona.tone} tone)
DIFFICULTY NOTE: {difficulty_note}

CONVERSATION:
{transcript}{product_reference_section}

Provide your evaluation as JSON with this EXACT structure:
{{
  "summary": "2-3 sentence overall assessment. Be specific about what the trainee did well and poorly.",
  "category_feedback": {{
    "rapport_building": {{
      "score": <1-5>,
      "comment": "Specific feedback about rapport efforts with an example from the conversation"
    }},
    "needs_discovery": {{
      "score": <1-5>,
      "comment": "Specific feedback about question quality and information gathering"
    }},
    "product_presentation": {{
      "score": <1-5>,
      "comment": "Specific feedback about value proposition clarity"
    }},
    "objection_handling": {{
      "score": <1-5>,
      "comment": "Specific feedback about how concerns were addressed"
    }},
    "closing": {{
      "score": <1-5>,
      "comment": "Specific feedback about next steps and commitment"
    }}{product_accuracy_category}
  }},
  "strengths": [
    "Specific strength with example from conversation",
    "Second strength with example",
    "Third strength with example"
  ],
  "improvements": [
    "Specific improvement area with actionable suggestion",
    "Second improvement with concrete next step",
    "Third improvement with practice recommendation"
  ],
  "coaching_tip": "One key technique the trainee should practice next time"
}}

Respond with JSON only:"""
    
    def _parse_evaluation(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured evaluation with hybrid scoring."""
        
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[start_idx:end_idx]
            evaluation = json.loads(json_str)
            
            # Validate required keys
            required_keys = ['summary', 'strengths', 'improvements']
            for key in required_keys:
                if key not in evaluation:
                    raise ValueError(f"Missing required key: {key}")
            
            # Extract per-category LLM scores (for hybrid scoring)
            category_feedback = evaluation.get('category_feedback', {})
            llm_category_scores = {}
            for cat_key, cat_data in category_feedback.items():
                if isinstance(cat_data, dict) and 'score' in cat_data:
                    # Convert 1-5 to 0-20 scale
                    llm_category_scores[cat_key] = min(20, max(0, int(cat_data['score']) * 4))
            
            evaluation['llm_category_scores'] = llm_category_scores
            
            return evaluation
            
        except json.JSONDecodeError as e:
            return self._create_fallback_evaluation(response)
    
    def _create_fallback_evaluation(self, raw_response: str = "") -> Dict[str, Any]:
        """Create a meaningful fallback if JSON parsing fails."""
        return {
            "summary": "The evaluation system was unable to generate a detailed analysis. "
                      "Based on the conversation, focus on asking more discovery questions, "
                      "building rapport early, and closing with clear next steps.",
            "category_feedback": {},
            "llm_category_scores": {},
            "strengths": [
                "Maintained professional communication throughout",
                "Showed willingness to engage with the customer",
                "Kept the conversation moving forward"
            ],
            "improvements": [
                "Ask more open-ended discovery questions to understand needs",
                "Provide specific examples and data to support value claims",
                "Close with a concrete next step and timeline"
            ],
            "coaching_tip": "Practice the SPIN selling technique: Situation, Problem, Implication, Need-payoff questions."
        }


def evaluate_session_conversation(
    messages: List[RoleplayMessage],
    persona: RoleplayPersona,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Convenience function to evaluate a conversation.
    Passes org_id for document-grounded product accuracy checking.
    """
    evaluator = ConversationEvaluator()
    return evaluator.evaluate_conversation(messages, persona, org_id=org_id)
