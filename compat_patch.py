"""
Compatibility patch for pydantic.v1 on Python 3.14+.

Python 3.14 implements PEP 649 (deferred evaluation of annotations),
which stores class annotations via an __annotate__ function instead of
populating __annotations__ eagerly. Pydantic v1's ModelMetaclass reads
namespace.get('__annotations__', {}) which returns empty on Python 3.14,
causing fields with None defaults (like Optional[int] = None) to fail
type inference with: "unable to infer type for attribute ..."

This module patches pydantic.v1's ModelMetaclass.__new__ to correctly
extract annotations using Python 3.14's annotationlib before field
processing occurs.

MUST be imported before any module that uses pydantic.v1 (e.g., chromadb).
"""
import sys
import warnings

# Suppress the pydantic.v1 Python 3.14 warning since we're patching the issue
warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality")

if sys.version_info >= (3, 14):
    import pydantic.v1.main as _pydantic_main
    import annotationlib

    _OriginalMetaclass = _pydantic_main.ModelMetaclass
    _original_new = _OriginalMetaclass.__new__

    def _patched_new(mcs, name, bases, namespace, **kwargs):
        """Patched ModelMetaclass.__new__ that handles PEP 649 deferred annotations."""
        # On Python 3.14+, annotations are deferred via PEP 649.
        # Extract them from the __annotate__ function and inject into namespace
        # so pydantic v1's field processing loop can find them.
        if '__annotations__' not in namespace or not namespace.get('__annotations__'):
            annotate_fn = annotationlib.get_annotate_from_class_namespace(namespace)
            if annotate_fn is not None:
                try:
                    annotations = annotationlib.call_annotate_function(
                        annotate_fn, annotationlib.Format.FORWARDREF
                    )
                    namespace['__annotations__'] = dict(annotations)
                except Exception:
                    pass

        return _original_new(mcs, name, bases, namespace, **kwargs)

    _OriginalMetaclass.__new__ = _patched_new
