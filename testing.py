"""Test all imports are working"""
import sys

def test_imports():
    try:
        print("Testing imports...")
        
        print("✓ models.concept_map...", end=" ")
        from models.concept_map import ConceptMap, ConceptNode, ConceptRelationship
        print("OK")
        
        print("✓ schemas.concept_map...", end=" ")
        from schemas.concept_map import ConceptMapOut, ConceptNodeOut
        print("OK")
        
        print("✓ services.concept_map_service...", end=" ")
        from services.concept_map_service import build_concept_map
        print("OK")
        
        print("✓ services.ontology_loader...", end=" ")
        from services.ontology_loader import load_universal_ontology
        print("OK")
        
        print("✓ routes.concept_map...", end=" ")
        from routes.concept_map import router
        print("OK")
        
        print("\n✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)