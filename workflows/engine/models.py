"""Model resolution and fallbacks."""

import os
from typing import Optional

DEFAULT_MODEL = "gpt-4.1-mini"

def resolve_model(model: Optional[str] = None) -> str:
    """Resolve the model to use, with fallbacks.
    
    Args:
        model: Optional model override
        
    Returns:
        The resolved model name
    """
    if model:
        return model
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL) 