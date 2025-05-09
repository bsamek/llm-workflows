"""Orchestrator-workers pattern implementation (see spec §4.4)."""

import typer
from typing import Optional
from pathlib import Path
import json
import asyncio
import sys

from ..engine.llm_runner import run_llm
from ..engine.models import resolve_model
from ..engine.logging import setup_logging, log_step

try:
    import tiktoken
    def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
except ImportError:
    def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
        # Fallback: rough estimate (4 chars/token)
        return max(1, len(text) // 4)

app = typer.Typer()

ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are an expert orchestrator. Given a user request, break it down into a list of JSON tasks "
    "(each with a unique id and a prompt) and an aggregate_prompt for synthesizing the results. "
    "Return a JSON object: {\"tasks\": [{\"id\": 1, \"prompt\": \"...\"}], \"aggregate_prompt\": \"...\"}. "
    "If no further tasks are needed, return an empty list for 'tasks'."
)
AGGREGATE_SYSTEM_PROMPT = "Synthesize the following worker results."

@app.callback(invoke_without_command=True)
def orchestrate(
    prompt: str = typer.Option(..., "--prompt", help="User request to orchestrate"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use for all LLM calls"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream output"),
    max_workers: int = typer.Option(None, "--max-workers", help="Max parallel workers (default: 5)"),
    iterations: int = typer.Option(1, "--iterations", help="Max orchestrator iterations"),
    max_input_tokens: Optional[int] = typer.Option(None, "--max-input-tokens", help="Drop any worker output > N tokens"),
    log_file: Optional[Path] = typer.Option(None, "--log", help="Write JSONL execution log"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Break down a complex task into subtasks, run them in parallel, and synthesize the results (spec §4.4)."""
    import os
    setup_logging(log_file, verbose)
    resolved_model = resolve_model(model)
    if max_workers is None:
        max_workers = 5

    user_request = prompt
    final_result = None
    for iteration in range(1, iterations + 1):
        # 1. Orchestrator step: get tasks and aggregate_prompt
        log_step("orchestrator", {"iteration": iteration, "prompt": user_request}, log_file)
        try:
            orchestrator_response = run_llm(
                prompt=user_request,
                system=ORCHESTRATOR_SYSTEM_PROMPT,
                model=resolved_model,
                stream=stream,
            )
        except Exception as e:
            typer.echo(f"[orchestrate] LLM error: {e}", err=True)
            raise typer.Exit(20)
        try:
            parsed = json.loads(orchestrator_response)
            tasks = parsed.get("tasks", [])
            aggregate_prompt = parsed.get("aggregate_prompt", None)
        except Exception as e:
            typer.echo(f"[orchestrate] Invalid orchestrator output: {e}", err=True)
            raise typer.Exit(10)
        log_step("orchestrator_result", {"tasks": tasks, "aggregate_prompt": aggregate_prompt}, log_file)
        if not tasks:
            typer.echo("[orchestrate] No tasks returned, finishing.", err=verbose)
            break
        # 2. Run worker prompts concurrently
        def run_worker(task):
            try:
                result = run_llm(
                    prompt=task["prompt"],
                    model=resolved_model,
                    stream=stream,
                )
                if max_input_tokens is not None and count_tokens(result, resolved_model) > max_input_tokens:
                    return {"id": task["id"], "result": None, "dropped": True}
                return {"id": task["id"], "result": result, "dropped": False}
            except Exception as e:
                return {"id": task["id"], "result": str(e), "dropped": True}
        async def run_all_workers():
            sem = asyncio.Semaphore(max_workers)
            async def sem_worker(task):
                async with sem:
                    return await asyncio.to_thread(run_worker, task)
            return await asyncio.gather(*(sem_worker(task) for task in tasks))
        try:
            worker_results = asyncio.run(run_all_workers())
        except Exception as e:
            typer.echo(f"[orchestrate] Worker execution error: {e}", err=True)
            raise typer.Exit(20)
        log_step("worker_results", {"results": worker_results}, log_file)
        # 3. Aggregate results
        valid_results = [w["result"] for w in worker_results if not w["dropped"] and w["result"] is not None]
        if not valid_results:
            typer.echo("[orchestrate] All worker outputs dropped or failed.", err=True)
            raise typer.Exit(20)
        aggregate_input = "\n\n".join(valid_results)
        try:
            final_result = run_llm(
                prompt=aggregate_prompt or aggregate_input,
                system=AGGREGATE_SYSTEM_PROMPT,
                model=resolved_model,
                stream=stream,
            )
        except Exception as e:
            typer.echo(f"[orchestrate] Aggregation LLM error: {e}", err=True)
            raise typer.Exit(20)
        log_step("aggregate", {"aggregate_prompt": aggregate_prompt, "input": aggregate_input, "result": final_result}, log_file)
        # 4. Prepare for next iteration
        user_request = final_result
        if iteration == iterations or not tasks:
            break
    print(final_result or "[orchestrate] No result.") 