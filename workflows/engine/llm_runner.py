"""Thin wrapper around subprocess / llm Python API."""

import subprocess
from typing import Optional, List, Dict, Any
import json

def run_llm(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    stream: bool = True,
    **kwargs: Any,
) -> str:
    """Run an LLM command and return its output.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Optional model override
        system: Optional system prompt
        stream: Whether to stream the output
        **kwargs: Additional arguments to pass to llm
        
    Returns:
        The LLM's response as a string
    """
    try:
        # Try to use llm Python API first
        import llm
        model_instance = llm.get_model(model) if model else llm.get_model()
        response = model_instance.prompt(
            prompt,
            system=system,
            **kwargs
        )
        return response.text()
    except ImportError:
        # Fallback to subprocess
        cmd = ["llm"]
        if model:
            cmd.extend(["--model", model])
        if system:
            cmd.extend(["--system", system])
        if not stream:
            cmd.append("--no-stream")
        cmd.extend(["--prompt", prompt])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip() 