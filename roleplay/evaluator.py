"""
Conversation evaluation module for roleplay sessions
Uses LLM to analyze sales conversations and provide structured feedback
"""
from typing import Dict, Any, List
from models.roleplay import RoleplayPersona, RoleplayMessage
from roleplay.llm_client import OllamaClient
from config.settings import settings
import json


class ConversationEvaluator:
    """Evaluates roleplay conversations and generates structured feedback"""
    
    def __init__(self):
        self.llm_client = OllamaClient()
    
    def evaluate_conversation(
        self,
        messages: List[RoleplayMessage],
        persona: RoleplayPersona
    ) -> Dict[str, Any]:
        """
        Evaluate a completed conversation
        
        Args:
            messages: List of conversation messages
            persona: The customer persona used
        
        Returns:
            Dict with evaluation results
        """
        
        # Build conversation transcript
        transcript = self._build_transcript(messages, persona.name)
        
        # Create evaluation prompt
        evaluation_prompt = self._build_evaluation_prompt(transcript, persona)
        
        # Get LLM evaluation
        try:
            response = self.llm_client.generate_response(
                system_prompt=self._get_system_prompt(),
                user_message=evaluation_prompt,
                max_tokens=400,  # Reduced from 800 - force concise evaluation
                timeout=None  # No timeout limit - allow LLM to take as long as needed
            )
            
            # Parse JSON response
            evaluation = self._parse_evaluation(response)
            
            return evaluation
            
        except Exception as e:
            raise Exception(f"Evaluation failed: {str(e)}")
    
    def _build_transcript(self, messages: List[RoleplayMessage], persona_name: str) -> str:
        """Format messages into readable transcript"""
        
        transcript_lines = []
        for msg in messages:
            speaker = "Trainee" if msg.sender == "trainee" else persona_name
            transcript_lines.append(f"{speaker}: {msg.message_text}")
        
        return "\n".join(transcript_lines)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for evaluation"""
        
        return """You are a sales coach. Evaluate this conversation and respond ONLY with valid JSON.

Provide qualitative feedback in this EXACT format:
{
  "summary": "2-3 sentence overall assessment of the sales conversation",
  "strengths": [
    "Specific strength with example",
    "Another strength with example",
    "Third strength with example"
  ],
  "improvements": [
    "Specific area to improve with suggestion",
    "Another improvement with actionable advice",
    "Third improvement with concrete next step"
  ]
}

Be specific and actionable. Reference actual things said in the conversation."""
    
    def _build_evaluation_prompt(self, transcript: str, persona: RoleplayPersona) -> str:
        """Build the evaluation request prompt"""
        
        return f"""Evaluate this sales conversation:

CUSTOMER: {persona.name} ({persona.difficulty} difficulty)

CONVERSATION:
{transcript}

Provide:
1. SUMMARY: 2-3 sentence overall assessment of performance
2. STRENGTHS: 3 specific things done well (with examples from conversation)
3. IMPROVEMENTS: 3 specific areas to improve (with actionable suggestions)

Focus on:
- Rapport building and active listening
- Needs discovery through questions
- Clear value presentation
- Handling objections professionally  
- Attempting to close or next steps

Provide JSON with summary, strengths array, and improvements array."""
    
    def _parse_evaluation(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured evaluation"""
        
        try:
            # Find JSON in response (might have extra text)
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[start_idx:end_idx]
            evaluation = json.loads(json_str)
            
            # Validate structure (new format)
            required_keys = ['summary', 'strengths', 'improvements']
            for key in required_keys:
                if key not in evaluation:
                    raise ValueError(f"Missing required key: {key}")
            
            return evaluation
            
        except json.JSONDecodeError as e:
            # Fallback: return default structure
            return {
                "summary": "Unable to generate detailed evaluation. The conversation showed basic sales interaction with room for improvement in discovery and closing.",
                "strengths": [
                    "Maintained professional communication throughout the conversation",
                    "Showed interest in understanding customer needs"
                ],
                "improvements": [
                    "Ask more discovery questions to uncover pain points",
                    "Provide more specific product details aligned to needs",
                    "Include stronger closing with clear next steps"
                ]
            }


def evaluate_session_conversation(
    messages: List[RoleplayMessage],
    persona: RoleplayPersona
) -> Dict[str, Any]:
    """
    Convenience function to evaluate a conversation
    
    Args:
        messages: Conversation messages
        persona: Customer persona
    
    Returns:
        Evaluation results
    """
    evaluator = ConversationEvaluator()
    return evaluator.evaluate_conversation(messages, persona)
