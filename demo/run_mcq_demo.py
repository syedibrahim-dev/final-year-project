"""
SalesForge AI — MCQ Generation Committee Demo
===============================================

A narrated, step-by-step demo showing how the MCQ pipeline generates
document-grounded quiz questions from uploaded training materials.

Uses the same CloudVault demo document as the roleplay demo, so the
committee can see the same product facts tested as quiz questions.

Pipeline steps demonstrated:
  1. RAG Retrieval  — fetches relevant chunks from ChromaDB
  2. Stem Generation — LLM creates question stems from context
  3. Answer Generation — LLM extracts correct answer from document
  4. Distractor Generation — LLM creates plausible wrong answers
  5. Distractor Filtering — removes duplicates and low-quality options
  6. Validation — checks relevance, correctness, and clarity

Usage:
    python demo/run_mcq_demo.py                     # Full demo (needs docs ingested)
    python demo/run_mcq_demo.py --ingest            # Ingest demo doc first
    python demo/run_mcq_demo.py --org-id 99         # Use specific org
    python demo/run_mcq_demo.py --questions 3       # Generate 3 questions
    python demo/run_mcq_demo.py --difficulty hard    # Set difficulty
"""

import sys
import os
import time
import argparse
from pathlib import Path

# Fix Windows console encoding
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Colours ──────────────────────────────────────────────────────
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
BLUE    = "\033[94m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"

def hr(char="-", length=80):
    print(f"{DIM}{char * length}{RESET}")

def banner(text, bg=BG_BLUE):
    padding = (78 - len(text)) // 2
    print(f"\n{bg}{BOLD}{' ' * padding}{text}{' ' * (78 - padding - len(text))}{RESET}\n")

def narrate(text):
    print(f"  {BLUE}{BOLD}[NARRATOR]{RESET} {BLUE}{text}{RESET}")


# ══════════════════════════════════════════════════════════════════
#  DOCUMENT INGESTION (reuse from roleplay demo)
# ══════════════════════════════════════════════════════════════════

def ingest_demo_document(org_id):
    """Ingest the demo product sheet into ChromaDB."""
    doc_path = Path(__file__).parent / "demo_product_sheet.txt"
    if not doc_path.exists():
        print(f"{RED}Demo document not found: {doc_path}{RESET}")
        return False

    try:
        from rag.pipeline import RAGPipeline
        pipeline = RAGPipeline()
        result = pipeline.ingest_document(
            file_path=str(doc_path),
            content_id=f"demo_{org_id}_cloudvault",
            org_id=org_id,
            metadata={"file_name": "demo_product_sheet.txt"},
        )
        print(f"{GREEN}Ingested demo document: {result['chunk_count']} chunks into org {org_id}{RESET}")
        return True
    except Exception as e:
        print(f"{RED}Failed to ingest demo document: {e}{RESET}")
        return False


# ══════════════════════════════════════════════════════════════════
#  MCQ DEMO RUNNER
# ══════════════════════════════════════════════════════════════════

def run_mcq_demo(org_id=99, num_questions=3, difficulty="medium", pause=False):

    banner("SALESFORGE AI -- MCQ GENERATION DEMO")

    print(f"  {BOLD}What you are about to see:{RESET}")
    print(f"  The MCQ pipeline generates quiz questions from uploaded training documents.")
    print(f"  Every question and answer is grounded in the company's actual product data")
    print(f"  via RAG retrieval -- no hallucinated or generic questions.\n")
    print(f"  {BOLD}Source Document:{RESET}  CloudVault Certificate Manager product sheet")
    print(f"  {BOLD}Organization:{RESET}     org_id={org_id}")
    print(f"  {BOLD}Questions:{RESET}        {num_questions}")
    print(f"  {BOLD}Difficulty:{RESET}       {difficulty}")
    print(f"  {BOLD}LLM Model:{RESET}        llama3.1:8b-instruct-q8_0 (22 GPU layers + RAM)\n")

    hr("=", 80)

    # ── Step 1: RAG Retrieval ──
    banner("STEP 1: RAG RETRIEVAL", BG_GREEN)
    narrate("First, the pipeline retrieves relevant chunks from ChromaDB.")
    narrate("These chunks become the ONLY source of truth for question generation.")
    narrate("The LLM cannot use its general knowledge -- only what's in the document.")
    print()

    from services.rag_service import retrieve_relevant_chunks

    topic = "certificate management security compliance"
    print(f"  {BOLD}Query:{RESET} \"{topic}\"")
    print(f"  {BOLD}Retrieving top 3 chunks with cross-encoder re-ranking...{RESET}\n")

    t0 = time.perf_counter()
    chunks = retrieve_relevant_chunks(query=topic, org_id=org_id, k=3)
    elapsed = (time.perf_counter() - t0) * 1000

    if not chunks:
        print(f"  {RED}No chunks found! Did you run --ingest first?{RESET}")
        print(f"  Run: python demo/run_mcq_demo.py --ingest --org-id {org_id}")
        return

    print(f"  {GREEN}Retrieved {len(chunks)} chunks in {elapsed:.0f}ms{RESET}\n")

    for i, chunk in enumerate(chunks, 1):
        score = chunk.get("score", 0)
        text_preview = chunk["chunk"][:150].replace("\n", " ")
        color = GREEN if score > 0.5 else YELLOW if score > 0.1 else RED
        print(f"  {BOLD}Chunk {i}{RESET} (score: {color}{score:.3f}{RESET}):")
        print(f"    {DIM}\"{text_preview}...\"{RESET}\n")

    context = "\n\n".join([c["chunk"] for c in chunks])[:3000]
    narrate(f"Combined context: {len(context)} characters from {len(chunks)} chunks.")
    narrate("This context is the ONLY input the LLM sees for question generation.")

    if pause:
        input(f"\n  {DIM}Press Enter to continue to question generation...{RESET}")

    hr("=", 80)

    # ── Step 2: Full Pipeline ──
    banner("STEP 2: MCQ GENERATION PIPELINE", BG_GREEN)
    narrate("Now running the full 4-stage pipeline:")
    narrate("  Stage 1: Stem Generation -- LLM creates question text from context")
    narrate("  Stage 2: Answer Extraction -- LLM finds correct answer IN the document")
    narrate("  Stage 3: Distractor Generation -- LLM creates plausible wrong answers")
    narrate("  Stage 4: Validation -- checks relevance, correctness, clarity")
    print()
    narrate("Key design principle: every correct answer must be traceable back")
    narrate("to a specific fact in the uploaded document. The LLM is prompted")
    narrate("to return 'SKIP_QUESTION' if the answer isn't in the text.")
    print()

    from mcq.pipeline import MCQPipeline

    pipeline = MCQPipeline()
    t0 = time.perf_counter()

    try:
        questions = pipeline.generate_mcqs(
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions,
            org_id=org_id,
            include_explanations=True,
        )
    except Exception as e:
        print(f"\n  {RED}Pipeline error: {e}{RESET}")
        return

    elapsed = (time.perf_counter() - t0)

    hr("=", 80)

    # ── Step 3: Display Results ──
    banner("GENERATED QUESTIONS", BG_BLUE)
    narrate(f"Generated {len(questions)} questions in {elapsed:.1f}s")
    narrate(f"Each question is grounded in the CloudVault product sheet.")
    print()

    for i, q in enumerate(questions, 1):
        print(f"  {BOLD}{CYAN}Question {i} of {len(questions)}{RESET}")
        print(f"  {BOLD}Difficulty:{RESET} {q.get('difficulty', '?')} | "
              f"{BOLD}Concept:{RESET} {q.get('key_concept', '?')} | "
              f"{BOLD}Cognitive Level:{RESET} {q.get('cognitive_level', '?')}")
        print()
        print(f"  {BOLD}Q: {q['question_text']}{RESET}")
        print()

        options = q.get("options", [])
        letters = ["A", "B", "C", "D"]
        for j, opt in enumerate(options):
            letter = letters[j] if j < len(letters) else "?"
            is_correct = opt.get("is_correct", False)
            marker = f"{GREEN}>> " if is_correct else "   "
            end_marker = f" <<{RESET}" if is_correct else ""
            text = opt.get("option_text", "")
            print(f"  {marker}{letter}. {text}{end_marker}")

        correct_letter = q.get("correct_answer", "?")
        print(f"\n  {GREEN}{BOLD}Correct Answer: {correct_letter}{RESET}")

        explanation = q.get("explanation", "")
        if explanation:
            print(f"  {DIM}Explanation: {explanation[:200]}{RESET}")

        # Validation results
        validation = q.get("validation", {})
        if validation and not validation.get("error"):
            passed = validation.get("overall_passed", False)
            status = f"{GREEN}PASS" if passed else f"{YELLOW}WARN"
            print(f"\n  {BOLD}Validation:{RESET} {status}{RESET}")

            checks = validation.get("checks", {})
            for check_name, check_data in checks.items():
                if isinstance(check_data, dict):
                    check_passed = check_data.get("passed", False)
                    check_score = check_data.get("score", check_data.get("similarity", "N/A"))
                    icon = f"{GREEN}PASS" if check_passed else f"{RED}FAIL"
                    label = check_name.replace("_", " ").title()
                    print(f"    {icon}{RESET} {label}: {check_score}")

        if q.get("quality_warning"):
            print(f"  {YELLOW}Quality Warning: Some validation checks did not pass{RESET}")

        print()
        hr("-", 80)

        if pause and i < len(questions):
            input(f"\n  {DIM}Press Enter for next question...{RESET}")
        print()

    # ── Summary ──
    banner("DEMO COMPLETE")
    print(f"  {BOLD}Pipeline Summary:{RESET}")
    print(f"    Questions generated:  {len(questions)}")
    print(f"    Total time:           {elapsed:.1f}s")
    print(f"    Source document:       CloudVault product sheet ({len(context)} chars context)")
    print(f"    RAG chunks used:      {len(chunks)}")
    print(f"    Difficulty level:     {difficulty}")
    print()
    print(f"  {BOLD}How it works:{RESET}")
    print(f"    1. Company uploads PDF/URL/video  -->  RAG ingests into ChromaDB")
    print(f"    2. Trainer requests MCQs on a topic  -->  RAG retrieves relevant chunks")
    print(f"    3. LLM generates questions ONLY from retrieved context (no hallucination)")
    print(f"    4. Distractor filter removes duplicates and low-quality options")
    print(f"    5. Validator checks relevance (embeddings), correctness (LLM), clarity (rules)")
    print()
    print(f"  {BOLD}Key differentiator:{RESET}")
    print(f"    Every question is traceable to a specific section of the uploaded document.")
    print(f"    The LLM is constrained to SKIP any question it can't answer from the text.")
    print(f"    This ensures quiz content matches what the company actually teaches.")
    print()


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="SalesForge AI -- MCQ Generation Demo")
    parser.add_argument("--org-id", type=int, default=99, help="Org ID for RAG retrieval")
    parser.add_argument("--ingest", action="store_true", help="Ingest demo document first")
    parser.add_argument("--questions", "-n", type=int, default=3, help="Number of questions")
    parser.add_argument("--difficulty", "-d", choices=["easy", "medium", "hard"], default="medium")
    parser.add_argument("--pause", action="store_true", help="Pause between questions")
    args = parser.parse_args()

    if args.ingest:
        ingest_demo_document(args.org_id)
        print()

    run_mcq_demo(
        org_id=args.org_id,
        num_questions=args.questions,
        difficulty=args.difficulty,
        pause=args.pause,
    )


if __name__ == "__main__":
    main()
