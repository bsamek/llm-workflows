"""Structured JSON + txt logs."""

import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

def setup_logging(
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    """Set up logging configuration.
    
    Args:
        log_file: Optional path to write JSONL logs
        verbose: Whether to enable verbose logging
    """
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
    )
    
    # Add JSONL file handler if specified
    if log_file:
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(handler)

def log_step(
    step: str,
    data: Dict[str, Any],
    log_file: Optional[Path] = None,
) -> None:
    """Log a workflow step.
    
    Args:
        step: Step name/identifier
        data: Step data to log
        log_file: Optional path to write JSONL logs
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "step": step,
        **data,
    }
    
    if log_file:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    else:
        logging.info(json.dumps(entry)) 