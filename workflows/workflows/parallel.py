"""Parallelization of inputs for the LLM CLI.

This module implements the 'parallel' workflow, which supports two modes:
- Sectioning: Split input into chunks and process each chunk in parallel
- Voting: Run the same prompt multiple times and aggregate results
"""

import asyncio
import concurrent.futures
import re
import sys
import typer
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import json

from ..engine.llm_runner import run_llm
from ..engine.models import resolve_model
from ..engine.streaming import StreamHandler
from ..engine.logging import log_step

app = typer.Typer()

class AggregateMode(str, Enum):
    """Aggregation modes for sectioning."""
    CONCAT = "concat"
    JSON = "json"

class VoteMode(str, Enum):
    """Voting modes for parallel execution."""
    MAJORITY = "majority"
    MAX_TOKENS = "max-tokens"

async def run_parallel_tasks(
    prompts: List[str],
    model: Optional[str] = None,
    system: Optional[str] = None,
    max_workers: int = None,
    timeout: Optional[float] = None,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> List[str]:
    """Run multiple prompts in parallel and return their results.
    
    Args:
        prompts: List of prompts to run in parallel
        model: Model to use for all prompts
        system: System prompt to use for all prompts
        max_workers: Maximum number of concurrent workers
        timeout: Maximum time to wait for each worker
        log_file: Path to log file
        verbose: Whether to print verbose output
        
    Returns:
        List of results from each prompt
    """
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, prompt in enumerate(prompts):
            future = loop.run_in_executor(
                executor,
                lambda p=prompt, idx=i: _run_task(p, idx, model, system, log_file, verbose)
            )
            futures.append(future)
        
        results = []
        for i, future in enumerate(asyncio.as_completed(futures, timeout=timeout)):
            result = await future
            results.append(result)
            if verbose:
                print(f"Task {i+1}/{len(prompts)} completed", file=sys.stderr)
        
        # Sort results by their original order
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

def _run_task(
    prompt: str,
    task_id: int,
    model: Optional[str] = None,
    system: Optional[str] = None,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> tuple[int, str]:
    """Run a single task and return its result with original index."""
    if verbose:
        print(f"Running task {task_id+1}", file=sys.stderr)
    
    result = run_llm(
        prompt=prompt,
        model=resolve_model(model),
        system=system,
        stream=False,  # No streaming for parallel tasks
    )
    
    # Log step
    log_step(
        f"parallel_task_{task_id+1}",
        {
            "prompt": prompt,
            "result": result,
        },
        log_file,
    )
    
    return task_id, result

def section_by_size(text: str, size: int) -> List[str]:
    """Split text into chunks of approximately equal size."""
    chunks = []
    for i in range(0, len(text), size):
        chunks.append(text[i:i+size])
    return chunks

def section_by_regex(text: str, pattern: str) -> List[str]:
    """Split text based on regex pattern."""
    matches = re.split(f"({pattern})", text)
    chunks = []
    
    # Combine headers with their content
    i = 0
    while i < len(matches):
        if i + 1 < len(matches) and re.match(pattern, matches[i]):
            chunks.append(matches[i] + matches[i+1])
            i += 2
        else:
            if matches[i]:  # Skip empty matches
                chunks.append(matches[i])
            i += 1
    
    return chunks

def aggregate_concat(results: List[str]) -> str:
    """Concatenate results with newlines."""
    return "\n\n".join(results)

def aggregate_json(results: List[str]) -> str:
    """Aggregate results as a JSON list."""
    return json.dumps(results, indent=2)

def count_majority(results: List[str]) -> str:
    """Return the most common result."""
    counts = {}
    for result in results:
        counts[result] = counts.get(result, 0) + 1
    
    # Find the most common result
    max_count = 0
    max_result = ""
    for result, count in counts.items():
        if count > max_count:
            max_count = count
            max_result = result
    
    return max_result

def max_tokens_result(results: List[str]) -> str:
    """Return the result with the most tokens."""
    return max(results, key=lambda x: len(x.split()))

@app.callback(invoke_without_command=True)
def parallel(
    # Common options
    prompt: str = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Prompt to execute for each section/vote",
    ),
    system: Optional[str] = typer.Option(
        None,
        "--system",
        "-s",
        help="System prompt to use",
    ),
    input_file: Optional[Path] = typer.Option(
        None,
        "--input",
        "-i",
        help="Input file to process (defaults to stdin)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use",
    ),
    max_workers: Optional[int] = typer.Option(
        None,
        "--max-workers",
        help="Maximum number of concurrent workers",
    ),
    timeout: Optional[float] = typer.Option(
        None,
        "--timeout",
        help="Maximum time to wait for each worker (in seconds)",
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
    
    # Sectioning options
    section_size: Optional[int] = typer.Option(
        None,
        "--section",
        help="Split input into chunks of this size",
    ),
    section_regex: Optional[str] = typer.Option(
        None,
        "--section-regex",
        help="Split input based on regex pattern",
    ),
    aggregate: Optional[AggregateMode] = typer.Option(
        None,
        "--aggregate",
        help="How to aggregate sectioned results",
    ),
    
    # Voting options
    vote_count: Optional[int] = typer.Option(
        None,
        "--vote",
        help="Run the prompt this many times and aggregate results",
    ),
    vote_mode: Optional[VoteMode] = typer.Option(
        VoteMode.MAJORITY,
        "--vote-mode",
        help="How to aggregate voting results",
    ),
    dedupe: bool = typer.Option(
        False,
        "--dedupe",
        help="Remove duplicate answers before voting",
    ),
) -> None:
    """Execute prompts in parallel using sectioning or voting."""
    # Validate inputs
    if not prompt:
        raise typer.BadParameter("Prompt is required")
    
    # Determine mode
    is_sectioning = section_size is not None or section_regex is not None
    is_voting = vote_count is not None
    
    if is_sectioning and is_voting:
        raise typer.BadParameter("Cannot use both sectioning and voting at the same time")
    if not is_sectioning and not is_voting:
        raise typer.BadParameter("Either sectioning or voting mode must be specified")
    
    # Read input
    input_text = ""
    if input_file:
        with open(input_file, "r") as f:
            input_text = f.read()
    else:
        # Read from stdin if no input file provided
        if not sys.stdin.isatty():
            input_text = sys.stdin.read()
    
    # Process based on mode
    if is_sectioning:
        # Validate sectioning options
        if aggregate is None:
            raise typer.BadParameter("--aggregate is required for sectioning mode")
        
        # Split input into sections
        sections = []
        if section_size:
            sections = section_by_size(input_text, section_size)
        elif section_regex:
            sections = section_by_regex(input_text, section_regex)
        
        if not sections:
            raise typer.Exit("No sections found in input")
        
        # Prepare prompts for each section
        prompts = [f"{prompt}\n\n{section}" for section in sections]
        
        # Run in parallel
        results = asyncio.run(run_parallel_tasks(
            prompts=prompts,
            model=model,
            system=system,
            max_workers=max_workers,
            timeout=timeout,
            log_file=log_file,
            verbose=verbose,
        ))
        
        # Aggregate results
        if aggregate == AggregateMode.CONCAT:
            final_result = aggregate_concat(results)
        elif aggregate == AggregateMode.JSON:
            final_result = aggregate_json(results)
        
        print(final_result)
        
    elif is_voting:
        # Validate voting options
        if vote_count < 2:
            raise typer.BadParameter("Vote count must be at least 2")
        
        # Prepare prompts (same prompt multiple times)
        prompts = [prompt] * vote_count
        
        # Run in parallel
        results = asyncio.run(run_parallel_tasks(
            prompts=prompts,
            model=model,
            system=system,
            max_workers=max_workers,
            timeout=timeout,
            log_file=log_file,
            verbose=verbose,
        ))
        
        # Deduplicate if requested
        if dedupe:
            results = list(dict.fromkeys(results))
        
        # Aggregate results based on vote mode
        if vote_mode == VoteMode.MAJORITY:
            final_result = count_majority(results)
        elif vote_mode == VoteMode.MAX_TOKENS:
            final_result = max_tokens_result(results)
        
        print(final_result) 