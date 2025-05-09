"""Evaluator-optimizer pattern implementation."""

import json
from pathlib import Path
from typing import Optional
from ..engine.llm_runner import run_llm
from ..engine.models import resolve_model
from ..engine.logging import setup_logging, log_step
import typer

app = typer.Typer()

EVALUATOR_SYSTEM_PROMPT = (
    "You are an evaluator. Given the following output and rubric, return a JSON object: {\"score\": float, \"feedback\": str}. "
    "Score must be between 0 and 1."
)
REVISE_TEMPLATE = (
    "Revise the following output based on this feedback.\n\nOutput:\n{output}\n\nFeedback:\n{feedback}\n\nReturn the improved output only."
)

@app.callback(invoke_without_command=True)
def optimize(
    prompt: Optional[str] = typer.Option(
        None, "--prompt", help="Prompt to generate initial output (or read from stdin)"
    ),
    target: float = typer.Option(
        0.9, "--target", help="Target score (0-1) to stop optimizing"
    ),
    max_iters: int = typer.Option(
        5, "--max-iters", help="Maximum optimization iterations"
    ),
    evaluator_system: Optional[Path] = typer.Option(
        None, "--evaluator-system", help="Path to rubric file (markdown or text) or rubric string"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model to use for all LLM calls"
    ),
    stream: bool = typer.Option(
        True, "--stream/--no-stream", help="Stream output as it is generated"
    ),
    log_file: Optional[Path] = typer.Option(
        None, "--log", help="Write JSONL execution log"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
) -> None:
    """Generate and iteratively improve content using evaluator-optimizer pattern (spec §4.5)."""
    setup_logging(log_file, verbose)
    resolved_model = resolve_model(model)

    # Read prompt from stdin if not provided
    if not prompt:
        if not typer.get_app().stdin_isatty():
            prompt = typer.get_text_stream("stdin").read()
        else:
            raise typer.BadParameter("Prompt is required (use --prompt or pipe to stdin)")

    # Load rubric (evaluator system prompt)
    rubric = None
    if evaluator_system:
        if isinstance(evaluator_system, Path) and evaluator_system.exists():
            rubric = evaluator_system.read_text()
        else:
            rubric = str(evaluator_system)
    else:
        rubric = "Evaluate the quality, clarity, and completeness of the output."

    # Initial generation
    current_output = run_llm(
        prompt=prompt,
        model=resolved_model,
        stream=stream,
    )
    log_step("generate", {"prompt": prompt, "output": current_output}, log_file)
    if verbose:
        typer.echo(f"[generate] Output:\n{current_output}\n", err=True)

    for iteration in range(1, max_iters + 1):
        # Evaluate
        eval_prompt = f"Output to evaluate:\n{current_output}\n\nRubric:\n{rubric}"
        eval_response = run_llm(
            prompt=eval_prompt,
            system=EVALUATOR_SYSTEM_PROMPT,
            model=resolved_model,
            stream=False,  # Evaluator output is JSON, don't stream
        )
        try:
            eval_json = json.loads(eval_response)
            score = float(eval_json.get("score", 0.0))
            feedback = eval_json.get("feedback", "")
        except Exception as e:
            typer.echo(f"[optimize] Invalid evaluator output: {eval_response}", err=True)
            raise typer.Exit(20)
        log_step("evaluate", {"iteration": iteration, "score": score, "feedback": feedback, "raw": eval_response}, log_file)
        if verbose:
            typer.echo(f"[evaluate] Iter {iteration}: score={score}, feedback={feedback}", err=True)
        # Check if target met
        if score >= target:
            log_step("success", {"iteration": iteration, "score": score, "output": current_output}, log_file)
            print(current_output)
            raise typer.Exit(0)
        if iteration == max_iters:
            log_step("max_iters", {"iteration": iteration, "score": score, "output": current_output}, log_file)
            print(current_output)
            raise typer.Exit(30)
        # Revise
        revise_prompt = REVISE_TEMPLATE.format(output=current_output, feedback=feedback)
        revised_output = run_llm(
            prompt=revise_prompt,
            model=resolved_model,
            stream=stream,
        )
        log_step("revise", {"iteration": iteration, "revise_prompt": revise_prompt, "output": revised_output}, log_file)
        if verbose:
            typer.echo(f"[revise] Iter {iteration}: revised output:\n{revised_output}\n", err=True)
        current_output = revised_output 