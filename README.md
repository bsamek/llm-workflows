# LLM Workflows

A Python wrapper for the `llm` CLI that implements five canonical agentic workflows:
- Prompt chaining
- Routing
- Parallelization
- Orchestrator-workers
- Evaluator-optimizer

## Installation

```bash
pip install llm-workflows
```

## Usage Examples

### Prompt Chaining

Chain multiple prompts together, with each step's output feeding into the next:

```bash
python -m workflows chain \
  --prompt "List 3 key points about Python" \
  --prompt "For each point, provide a code example" \
  --prompt "Summarize the examples in a single paragraph"
```

### Routing

Classify input and dispatch to specialized handlers:

```bash
python -m workflows route \
  --input "How do I sort a list in Python?" \
  --routes routes.yaml
```

Where `routes.yaml` contains:
```yaml
code:
  system: "You are a Python coding assistant"
  template: "Explain this code concept: {input}"
  
general:
  system: "You are a helpful assistant"
  template: "Answer this question: {input}"
```

### Parallelization

Process multiple inputs in parallel:

```bash
python -m workflows parallel \
  --section size=500 \
  --prompt "Summarize this text" \
  --aggregate concat
```

### Orchestrator-Workers

Break down complex tasks into subtasks:

```bash
python -m workflows orchestrate \
  --prompt "Write a blog post about machine learning" \
  --max-workers 4
```

### Evaluator-Optimizer

Generate and iteratively improve content:

```bash
python -m workflows optimize \
  --prompt "Write a product description" \
  --target 0.9 \
  --max-iters 5
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .
```

## License

MIT 