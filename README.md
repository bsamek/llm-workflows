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

Break down complex tasks into subtasks and synthesize the results. The orchestrate workflow automatically decomposes your prompt into parallelizable subtasks, runs them concurrently, and aggregates the results into a final answer.

**Options:**
- `--prompt TEXT` (required): The main user request to orchestrate.
- `--max-workers INT`: Maximum number of parallel worker tasks (default: 5).
- `--iterations INT`: Maximum orchestrator/aggregation rounds (default: 1).
- `--max-input-tokens INT`: Drop any worker output exceeding this token count.
- `--model TEXT`: Override the model for all LLM calls.
- `--stream/--no-stream`: Stream output as it is generated (default: stream).
- `--log FILE`: Write a JSONL execution log for all steps.
- `--verbose, -v`: Print intermediate steps and extra diagnostics.

**Basic usage:**
```bash
python -m workflows orchestrate \
  --prompt "Write a blog post about machine learning"
```

> **Note:** Redirecting output (e.g., `> blog.md`) will write only the final synthesized result to the file. Intermediate steps and diagnostics are printed to the terminal only if `--verbose` is used and are not included in redirected output.

**Advanced example:**
```bash
python -m workflows orchestrate \
  --prompt "Summarize and compare the top 5 open-source LLMs" \
  --max-workers 8 \
  --iterations 2 \
  --max-input-tokens 1024 \
  --model gpt-4o-mini \
  --log orchestrate_log.jsonl \
  --verbose
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