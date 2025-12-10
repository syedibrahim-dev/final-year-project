"""
Direct Ollama LLM client for roleplay conversations
No LangChain dependency - uses HTTP API directly
"""
import requests
from typing import Generator, Dict, Any, Optional
from config.settings import settings
import json


class OllamaClient:
    """Client for direct Ollama API calls"""
    
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        temperature: float = None
    ):
        self.base_url = base_url or settings.LOCAL_LLM_BASE_URL
        self.model = model or settings.LOCAL_LLM_MODEL
        self.temperature = temperature or settings.LOCAL_LLM_TEMPERATURE
        self.chat_endpoint = f"{self.base_url}/api/chat"
    
    def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 100,  # Allow natural 2-4 sentence responses
        timeout: int = None  # No timeout limit - allow LLM to take as long as needed
    ) -> str:
        """
        Generate a single response (non-streaming)
        
        Args:
            system_prompt: System instructions for the LLM
            user_message: User's message
            max_tokens: Maximum response length
        
        Returns:
            Generated response text
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=timeout  # Use parameter instead of hardcoded value
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["message"]["content"]
            # Remove leading/trailing quotation marks if present
            return content.strip().strip('"').strip("'")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama API call failed: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected response format: {str(e)}")
    
    def stream_response(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 100  # Allow natural 2-4 sentence responses
    ) -> Generator[str, None, None]:
        """
        Generate streaming response (for real-time UI)
        
        Args:
            system_prompt: System instructions for the LLM
            user_message: User's message
            max_tokens: Maximum response length
        
        Yields:
            Response chunks as they arrive
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                stream=True,
                timeout=None  # No timeout limit - allow LLM to take as long as needed
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
                        
                        # Check if done
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama streaming failed: {str(e)}")


# Convenience functions
def generate_customer_response(
    persona,
    history: list,
    trainee_message: str
) -> str:
    """
    Generate customer response using Ollama
    
    Args:
        persona: RoleplayPersona instance
        history: List of previous messages
        trainee_message: Latest trainee message
    
    Returns:
        Generated customer response
    """
    from roleplay.prompts import build_customer_prompt
    
    # Build prompts
    prompt_data = build_customer_prompt(persona, history, trainee_message)
    
    # Call Ollama
    client = OllamaClient()
    response = client.generate_response(
        system_prompt=prompt_data["system"],
        user_message=prompt_data["user_message"]
    )
    
    # Remove leading/trailing quotation marks and whitespace
    return response.strip().strip('"').strip("'")


def stream_customer_response(
    persona,
    history: list,
    trainee_message: str
) -> Generator[str, None, None]:
    """
    Stream customer response using Ollama
    
    Args:
        persona: RoleplayPersona instance
        history: List of previous messages
        trainee_message: Latest trainee message
    
    Yields:
        Response chunks
    """
    from roleplay.prompts import build_customer_prompt
    
    # Build prompts
    prompt_data = build_customer_prompt(persona, history, trainee_message)
    
    # Stream from Ollama
    client = OllamaClient()
    for chunk in client.stream_response(
        system_prompt=prompt_data["system"],
        user_message=prompt_data["user_message"]
    ):
        yield chunk
