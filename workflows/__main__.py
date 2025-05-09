"""CLI entry point for the workflows package."""

import typer
from typing import Optional

app = typer.Typer(
    name="workflows",
    help="Python workflows wrapper for the llm CLI",
    add_completion=False,
)

# Import workflow commands
from workflows.workflows.chain import app as chain_app
from workflows.workflows.route import main as route_command
from workflows.workflows.parallel import app as parallel_app
from workflows.workflows.orchestrate import app as orchestrate_app
from workflows.workflows.optimize import app as optimize_app

# Register workflow subcommands
app.add_typer(chain_app, name="chain")
app.command(name="route")(route_command)
app.add_typer(parallel_app, name="parallel")
app.add_typer(orchestrate_app, name="orchestrate")
app.add_typer(optimize_app, name="optimize")

def main():
    """Entry point for the workflows CLI."""
    app()

if __name__ == "__main__":
    main() 