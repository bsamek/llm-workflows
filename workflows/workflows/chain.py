"""Sequential decomposition of a task into N deterministic steps."""

import typer
import sys
from typing import List, Optional
from pathlib import Path
import json

from ..engine.llm_runner import run_llm
from ..engine.models import resolve_model
from ..engine.streaming import StreamHandler
from ..engine.logging import log_step

app = typer.Typer()

@app.callback(invoke_without_command=True)
def chain(
    prompt: List[str] = typer.Option(
        ...,
        "--prompt",
        "-p",
        help="Prompt to execute (can be specified multiple times)",
    ),
    prompts_file: Optional[Path] = typer.Option(
        None,
        "--prompts-file",
        help="File containing prompts (one per line)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream output",
    ),
    gate_schema: Optional[Path] = typer.Option(
        None,
        "--gate-schema",
        help="JSON schema to validate intermediate outputs",
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log",
        help="Write JSONL execution log",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Execute a chain of prompts sequentially."""
    # Load prompts from file if specified
    if prompts_file:
        with open(prompts_file) as f:
            prompt = [line.strip() for line in f if line.strip()]
    
    if len(prompt) < 2:
        raise typer.BadParameter("At least 2 prompts are required")
        
    # Load gate schema if specified
    schema = None
    if gate_schema:
        with open(gate_schema) as f:
            schema = json.load(f)
            
    # Execute chain
    result = ""
    for i, p in enumerate(prompt, 1):
        # Append previous result to prompt
        if result:
            p = f"{p}\n\n{result}"
            
        # Run LLM
        result = run_llm(
            prompt=p,
            model=resolve_model(model),
            stream=stream,
        )
        
        # Log step
        log_step(
            f"chain_step_{i}",
            {
                "prompt": p,
                "result": result,
            },
            log_file,
        )
        
        # Show intermediate results to stderr
        if i < len(prompt):
            print(f"\n--- Step {i} Result ---", file=sys.stderr)
            print(result, file=sys.stderr)
            print(f"--- End Step {i} Result ---\n", file=sys.stderr)
        
        # Validate against schema if specified
        if schema:
            try:
                json_result = json.loads(result)
                # TODO: Add schema validation
            except json.JSONDecodeError:
                raise typer.Exit(20)
                
    # Print final result
    print(result) 
