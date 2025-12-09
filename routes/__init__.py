"""
API Routes Package
"""

from . import auth
from . import user
from . import organization
from . import content
from . import mcq

__all__ = ["auth", "user", "organization", "content", "mcq"]