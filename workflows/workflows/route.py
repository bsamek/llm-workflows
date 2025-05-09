"""Route input to specialized handlers based on classification."""

import json
import typer
from pathlib import Path
from typing import Optional, Dict, Any

app = typer.Typer()

def load_routes(routes_file: Path) -> Dict[str, Dict[str, str]]:
    """Load routing configuration from YAML or JSON file.
    
    Args:
        routes_file: Path to routes configuration file
        
    Returns:
        Dictionary mapping labels to route configurations
    """
    if routes_file.suffix == ".json":
        return json.loads(routes_file.read_text())
    else:
        import yaml
        return yaml.safe_load(routes_file.read_text())

@app.command()
def main(
    input_text: str = typer.Argument(..., help="Input text to classify and route"),
    routes_file: Path = typer.Option(..., "--routes-file", "-f", help="YAML/JSON file with route configurations"),
    classifier_system: Optional[str] = typer.Option(None, help="Custom system prompt for classifier"),
    classifier_prompt: Optional[str] = typer.Option(None, help="Custom prompt template for classifier"),
    print_label: bool = typer.Option(False, help="Print the chosen label before response"),
    model: Optional[str] = typer.Option(None, help="Model to use for all LLM calls"),
    stream: bool = typer.Option(True, help="Stream output"),
    log_file: Optional[Path] = typer.Option(None, help="Write execution log to file"),
    verbose: bool = typer.Option(False, help="Enable verbose logging"),
) -> None:
    """Classify input and dispatch to specialized handlers.
    
    The routes file should contain a mapping of labels to route configurations.
    Each route can specify:
    - system: System prompt for the handler
    - model: Model override for this route
    - template: Prompt template with {input} placeholder
    """
    from ..engine.llm_runner import run_llm
    from ..engine.models import resolve_model
    from ..engine.logging import setup_logging, log_step
    
    # Setup logging
    setup_logging(log_file, verbose)
    
    # Load routes
    routes = load_routes(routes_file)
    labels = list(routes.keys())
    
    # Build classifier prompt
    if classifier_prompt:
        classifier_prompt = classifier_prompt.format(labels=labels)
    else:
        classifier_prompt = f"Classify the following input into one of these categories: {', '.join(labels)}\n\nInput: {input_text}"
    
    # Run classifier
    log_step("classify", {"input": input_text, "labels": labels})
    classification = run_llm(
        prompt=classifier_prompt,
        system=classifier_system or "You are a classifier. Respond with exactly one of the provided labels, nothing else.",
        model=resolve_model(model),
        stream=stream
    ).strip()
    
    # Validate classification
    if classification not in routes:
        raise typer.Exit(f"Classifier returned invalid label: {classification}")
    
    # Get route config
    route_config = routes[classification]
    
    # Build handler prompt
    handler_prompt = route_config["template"].format(input=input_text)
    
    # Run handler
    log_step("handle", {"label": classification, "prompt": handler_prompt})
    response = run_llm(
        prompt=handler_prompt,
        system=route_config.get("system"),
        model=resolve_model(route_config.get("model", model)),
        stream=stream
    )
    
    # Print response
    if print_label:
        print(f"[{classification}] ", end="")
    print(response) 