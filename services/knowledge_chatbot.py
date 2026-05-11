import requests
from typing import List, Dict, Optional
from datetime import datetime
import json
from services.rag_service import retrieve_relevant_chunks
from config.settings import settings

class KnowledgeChatbot:
    """
    Interactive chatbot for training content Q&A
    Uses RAG + Phi-3 Mini for conversational responses
    """
    
    def __init__(self, org_id: int, llm_url: str = "http://localhost:11434"):
        self.org_id = org_id
        self.llm_url = llm_url
        self.model_name = settings.LOCAL_LLM_MODEL
        self.conversation_history = []
    
    def chat(
        self,
        question: str,
        top_k: int = 1,  # ✅ REDUCED FROM 5
        use_history: bool = True
    ) -> Dict:
        """
        Have a conversation about training content
        """
        
        print(f"\n💬 User Question: {question}")
        
        try:
            # Step 1: Retrieve relevant content chunks
            print("🔍 Retrieving relevant training content...")
            
            relevant_chunks_raw = retrieve_relevant_chunks(
                query=question,
                org_id=self.org_id,
                k=top_k
            )
            
            # Convert to expected format
            relevant_chunks = []
            for item in relevant_chunks_raw:
                relevant_chunks.append({
                    'content': item['chunk'],
                    'metadata': item['metadata'],
                    'score': item['score']
                })
            
            if not relevant_chunks:
                return {
                    "answer": "I couldn't find any relevant information in the training materials. Could you rephrase your question?",
                    "sources": [],
                    "conversation_id": None,
                    "timestamp": datetime.now().isoformat()
                }
            
            print(f"✅ Found {len(relevant_chunks)} relevant chunks")
            
            # Step 2: Build context from chunks
            context = self._build_context(relevant_chunks)
            
            # Step 3: Build conversation history
            history_context = ""
            if use_history and self.conversation_history:
                history_context = self._build_history_context()
            
            # Step 4: Generate response using Phi-3 Mini
            print("🤖 Generating response with Phi-3 Mini...")
            
            answer = self._generate_response(
                question=question,
                context=context,
                history=history_context
            )
            
            # Step 5: Store in conversation history
            conversation_entry = {
                "question": question,
                "answer": answer,
                "timestamp": datetime.now().isoformat(),
                "sources_used": len(relevant_chunks)
            }
            self.conversation_history.append(conversation_entry)
            
            # Step 6: Format sources
            sources = self._format_sources(relevant_chunks)
            
            print("✅ Response generated successfully")
            
            return {
                "answer": answer,
                "sources": sources,
                "conversation_id": len(self.conversation_history),
                "timestamp": conversation_entry["timestamp"]
            }
            
        except Exception as e:
            print(f"❌ Chat error: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "answer": "I encountered an error while processing your question. Please try again.",
                "sources": [],
                "conversation_id": None,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def _build_context(self, chunks: List[Dict]) -> str:
        """Build context string from retrieved chunks"""
        
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            
            # ✅ LIMIT CHUNK SIZE TO 500 CHARS
            content_preview = content[:500] if len(content) > 500 else content
            
            source = metadata.get('source', 'Unknown')
            page = metadata.get('page', 'N/A')
            
            context_parts.append(
                f"[Source {i}: {source}, Page {page}]\n{content_preview}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    def _build_history_context(self) -> str:
        """Build conversation history context"""
        
        if not self.conversation_history:
            return ""
        
        # ✅ ONLY LAST 2 EXCHANGES (REDUCED FROM 3)
        recent_history = self.conversation_history[-2:]
        
        history_parts = []
        for entry in recent_history:
            history_parts.append(
                f"User: {entry['question'][:100]}\nAssistant: {entry['answer'][:200]}"
            )
        
        return "\n\n".join(history_parts)
    
    def _generate_response(
        self,
        question: str,
        context: str,
        history: str = ""
    ) -> str:
        """
        Generate conversational response using Phi-3 Mini with STREAMING
        """
        
        system_prompt = """You are a helpful training assistant. Answer based on the provided context.
Be concise and helpful. Keep responses under 200 words."""

        conversation_context = ""
        if history:
            conversation_context = f"\nPrevious:\n{history}\n"
        
        user_prompt = f"""{conversation_context}
Context:
{context}

Question: {question}

Answer briefly:"""

        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # ✅ STREAMING RESPONSE
        try:
            response = requests.post(
                f"{self.llm_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": full_prompt,
                    "stream": True,  # ✅ ENABLE STREAMING
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 250,  # ✅ LIMIT LENGTH
                        "num_ctx": 2048,     # ✅ SMALLER CONTEXT
                        "top_p": 0.9,
                        "num_gpu": 0  # CPU-only; GPU MODE (revert): set to 24
                    }
                },
                stream=True,
                timeout=180  # ✅ INCREASED TIMEOUT
            )
            
            if response.status_code == 200:
                answer = ""
                
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        
                        if "response" in chunk:
                            answer += chunk["response"]
                            print(".", end="", flush=True)
                        
                        if chunk.get("done", False):
                            break
                
                print()  # New line
                
                if not answer.strip():
                    return "I couldn't generate a proper response. Please try rephrasing your question."
                
                return answer.strip()
            else:
                print(f"❌ LLM API error: {response.status_code}")
                return "I'm having trouble connecting to the AI model. Please try again."
                
        except requests.exceptions.Timeout:
            print("❌ LLM request timeout")
            return "The request took too long. Please try a simpler question."
        
        except Exception as e:
            print(f"❌ LLM generation error: {e}")
            import traceback
            traceback.print_exc()
            return "I encountered an error generating the response."
    
    def _format_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Format source information for response"""
        
        sources = []
        
        for chunk in chunks:
            metadata = chunk.get('metadata', {})
            
            sources.append({
                "content_preview": chunk.get('content', '')[:150] + "...",
                "filename": metadata.get('source', 'Unknown'),
                "page": metadata.get('page', 'N/A'),
                "content_id": metadata.get('content_id', 'N/A')
            })
        
        return sources
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("🗑️  Conversation history cleared")
    
    def get_history(self) -> List[Dict]:
        """Get conversation history"""
        return self.conversation_history
    
    def export_conversation(self) -> Dict:
        """Export conversation for saving/analysis"""
        return {
            "org_id": self.org_id,
            "total_messages": len(self.conversation_history),
            "conversation": self.conversation_history,
            "exported_at": datetime.now().isoformat()
        }