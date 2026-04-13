"""Debug script to understand the pydantic.v1 / Python 3.14 / chromadb issue."""
import sys
print(f"Python {sys.version}")

from typing import Optional

# Simulate exactly what pydantic.v1 ModelMetaclass.__new__ does
class TestMeta(type):
    def __new__(mcs, name, bases, namespace):
        ann = namespace.get('__annotations__', {})
        ann_dict = dict(ann) if hasattr(ann, 'items') else {}
        print(f"Annotations keys: {list(ann_dict.keys())}")
        ns_keys = [k for k in namespace.keys() if not k.startswith('_')]
        print(f"Namespace non-private keys: {ns_keys}")
        for k in ns_keys:
            in_ann = k in ann_dict
            val = namespace[k]
            print(f"  {k}: in_annotations={in_ann}, type={type(val).__name__}, value={val!r}")
        return super().__new__(mcs, name, bases, namespace)


print("\n--- Test 1: Validator BEFORE field (like chromadb) ---")
class TestSettings1(metaclass=TestMeta):
    environment: str = ""
    
    @classmethod
    def empty_str_to_none(cls, v):
        return None if v == "" else v
    
    chroma_server_nofile: Optional[int] = None
    chroma_server_thread_pool_size: int = 40


print("\n--- Test 2: No validator, just fields ---")
class TestSettings2(metaclass=TestMeta):
    environment: str = ""
    chroma_server_nofile: Optional[int] = None
    chroma_server_thread_pool_size: int = 40


print("\n--- Test 3: Actual pydantic.v1 BaseSettings test ---")
try:
    from pydantic.v1 import BaseSettings, validator

    class WorkingSettings(BaseSettings):
        environment: str = ""
        chroma_server_thread_pool_size: int = 40
    
    print(f"WorkingSettings created OK, fields: {list(WorkingSettings.__fields__.keys())}")
except Exception as e:
    print(f"WorkingSettings ERROR: {e}")


print("\n--- Test 4: With validator + field (like chromadb) ---")
try:
    from pydantic.v1 import BaseSettings, validator

    class BrokenSettings(BaseSettings):
        environment: str = ""
        
        @validator("chroma_server_nofile", pre=True, always=True, allow_reuse=True)
        def empty_str_to_none(cls, v):
            if type(v) is str and v.strip() == "":
                return None
            return v
        
        chroma_server_nofile: Optional[int] = None
        chroma_server_thread_pool_size: int = 40
    
    print(f"BrokenSettings created OK, fields: {list(BrokenSettings.__fields__.keys())}")
except Exception as e:
    print(f"BrokenSettings ERROR: {e}")


print("\n--- Test 5: With validator AFTER field ---")
try:
    from pydantic.v1 import BaseSettings, validator

    class ReorderedSettings(BaseSettings):
        environment: str = ""
        chroma_server_nofile: Optional[int] = None
        
        @validator("chroma_server_nofile", pre=True, always=True, allow_reuse=True)
        def empty_str_to_none(cls, v):
            if type(v) is str and v.strip() == "":
                return None
            return v
        
        chroma_server_thread_pool_size: int = 40
    
    print(f"ReorderedSettings created OK, fields: {list(ReorderedSettings.__fields__.keys())}")
except Exception as e:
    print(f"ReorderedSettings ERROR: {e}")
