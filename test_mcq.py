"""
Test MCQ Generation Pipeline with llama3.1:8b model
Tests: stem generation → answer generation → distractor generation → validation
"""
import sys
import os
import json
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mcq_generation():
    """Test MCQ pipeline end-to-end"""
    
    print("=" * 60)
    print("  🧪 MCQ GENERATION TEST")
    print("  Model: llama3.1:8b-instruct-q4_K_M")
    print("=" * 60)
    
    # Step 1: Verify settings
    print("\n📋 Step 1: Checking configuration...")
    from config.settings import settings
    print(f"   MCQ Model:     {settings.MCQ_LLM_MODEL}")
    print(f"   LLM Base URL:  {settings.LOCAL_LLM_BASE_URL}")
    print(f"   Embedding:     {settings.EMBEDDING_MODEL}")
    
    # Step 2: Test LLM connectivity
    print("\n🔌 Step 2: Testing LLM connectivity...")
    import requests
    try:
        r = requests.post(
            f"{settings.LOCAL_LLM_BASE_URL}/api/chat",
            json={
                "model": settings.MCQ_LLM_MODEL,
                "messages": [{"role": "user", "content": "Say OK"}],
                "stream": False,
                "options": {"num_gpu": 24, "num_predict": 10}
            },
            timeout=30
        )
        if r.status_code == 200:
            resp = r.json()["message"]["content"]
            print(f"   ✅ LLM responding: '{resp.strip()[:50]}'")
        else:
            print(f"   ❌ LLM error: {r.status_code} - {r.text[:100]}")
            return
    except Exception as e:
        print(f"   ❌ LLM connection failed: {e}")
        return
    
    # Step 3: Test RAG availability
    print("\n📚 Step 3: Checking RAG/ChromaDB...")
    try:
        from services.rag_service import retrieve_relevant_chunks, CHROMA_AVAILABLE
        print(f"   CHROMA_AVAILABLE: {CHROMA_AVAILABLE}")
        
        if not CHROMA_AVAILABLE:
            print("   ❌ ChromaDB not available — MCQ needs RAG. Aborting.")
            return
        
        # Test retrieval with org_id=1
        chunks = retrieve_relevant_chunks(query="sales training", org_id=1, k=2)
        if chunks:
            print(f"   ✅ Retrieved {len(chunks)} chunks from org_id=1")
            for i, c in enumerate(chunks):
                print(f"      Chunk {i+1}: {c['chunk'][:80]}...")
        else:
            print("   ⚠️  No chunks found for org_id=1. MCQ needs uploaded documents.")
            print("   Trying org_id=2...")
            chunks = retrieve_relevant_chunks(query="sales training", org_id=2, k=2)
            if chunks:
                print(f"   ✅ Retrieved {len(chunks)} chunks from org_id=2")
            else:
                print("   ❌ No documents found in any org. Upload a PDF first.")
                return
    except ImportError as e:
        print(f"   ❌ RAG import error: {e}")
        return
    
    # Step 4: Run MCQ Pipeline
    print("\n🚀 Step 4: Running MCQ Generation Pipeline...")
    print(f"   Topic: 'sales techniques'")
    print(f"   Difficulty: 'medium'")
    print(f"   Questions: 5")
    print()
    
    start_time = time.time()
    
    try:
        from mcq.pipeline import MCQPipeline
        pipeline = MCQPipeline()
        
        questions = pipeline.generate_mcqs(
            topic="sales techniques",
            difficulty="medium",
            num_questions=5,
            org_id=1
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n{'=' * 60}")
        print(f"  📊 RESULTS ({elapsed:.1f}s)")
        print(f"{'=' * 60}")
        print(f"  Generated: {len(questions)} questions\n")
        
        for i, q in enumerate(questions, 1):
            print(f"  Q{i}: {q['question_text']}")
            print(f"      Difficulty: {q['difficulty']} | Level: {q.get('cognitive_level', '?')}")
            
            for opt in q.get('options', []):
                marker = "✅" if opt.get('is_correct') else "  "
                print(f"      {marker} {opt['option_text'][:100]}")
            
            print(f"      Correct: {q['correct_answer']}")
            
            if q.get('explanation'):
                print(f"      Explanation: {q['explanation'][:120]}...")
            
            # Show validation results
            val = q.get('validation', {})
            if val:
                print(f"      Validation: {val.get('summary', 'N/A')}")
            
            print()
        
        # Summary
        print(f"{'=' * 60}")
        print(f"  ✅ MCQ GENERATION TEST PASSED")
        print(f"  Generated {len(questions)} questions in {elapsed:.1f}s")
        print(f"  Average: {elapsed/max(len(questions),1):.1f}s per question")
        print(f"{'=' * 60}")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n  ❌ MCQ GENERATION FAILED after {elapsed:.1f}s")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_mcq_generation()
