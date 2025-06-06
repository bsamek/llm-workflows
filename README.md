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
workflows chain \
  --prompt "List 3 key points about Python" \
  --prompt "For each point, provide a code example" \
  --prompt "Summarize the examples in a single paragraph"
```

### Routing

Classify input and dispatch to specialized handlers:

```bash
workflows route \
  "How do I sort a list in Python?" \
  --routes-file routes.yaml
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

**Options:**
- `INPUT_TEXT` (required): The input text to classify and route.
- `--routes-file PATH` or `-f PATH` (required): YAML/JSON file with route configurations.
- `--classifier-system TEXT`: Custom system prompt for the classifier.
- `--classifier-prompt TEXT`: Custom prompt template for the classifier.
- `--print-label / --no-print-label`: Print the chosen label before the response (default: `no-print-label`).
- `--model TEXT`: Override the model for all LLM calls.
- `--stream / --no-stream`: Stream output as it is generated (default: `stream`).
- `--log-file PATH`: Write a JSONL execution log for all steps.
- `--verbose / --no-verbose`: Print intermediate steps and extra diagnostics.

### Parallelization

The parallel workflow supports two modes:
1. **Sectioning**: Split input into chunks and process each chunk in parallel
2. **Voting**: Run the same prompt multiple times and aggregate results

#### Sectioning Mode

Split a large document into sections and process each section in parallel:

```bash
# Split by size (characters)
cat document.txt | workflows parallel \
  --prompt "Summarize this section:" \
  --section 500 \
  --aggregate concat

# Split by regex pattern (e.g., markdown headers)
cat document.md | workflows parallel \
  --prompt "Extract key points from this section:" \
  --section-regex "^## " \
  --aggregate json \
  --model gpt-4o-mini \
  --verbose
```

#### Voting Mode

Run the same prompt multiple times and use majority voting or select the most detailed response:

```bash
# Majority voting
workflows parallel \
  --prompt "What is the capital of France?" \
  --vote 5 \
  --vote-mode majority

# Select response with most tokens
workflows parallel \
  --prompt "Explain quantum computing" \
  --vote 3 \
  --vote-mode max-tokens \
  --dedupe \
  --max-workers 3 \
  --log voting_results.jsonl
```

**Common Options:**
- `--prompt TEXT` (required): The prompt to execute for each section or vote.
- `--system TEXT`: System prompt to use for all LLM calls.
- `--input PATH`: Input file to process (defaults to stdin).
- `--model TEXT`: Override the model for all LLM calls.
- `--max-workers INT`: Maximum number of concurrent workers.
- `--timeout FLOAT`: Maximum time (seconds) to wait for each worker.
- `--log PATH`: Write a JSONL execution log.
- `--verbose`: Print progress and intermediate results.

**Sectioning Options:**
- `--section INT`: Split input into chunks of this size (characters).
- `--section-regex TEXT`: Split input based on regex pattern.
- `--aggregate [concat|json]`: How to aggregate section results.

**Voting Options:**
- `--vote INT`: Run the prompt this many times.
- `--vote-mode [majority|max-tokens]`: How to select the final result.
- `--dedupe`: Remove duplicate answers before voting.

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
workflows orchestrate \
  --prompt "Write a blog post about machine learning"
```

> **Note:** Redirecting output (e.g., `> blog.md`) will write only the final synthesized result to the file. Intermediate steps and diagnostics are printed to the terminal only if `--verbose` is used and are not included in redirected output.

**Advanced example:**
```bash
workflows orchestrate \
  --prompt "Summarize and compare the top 5 open-source LLMs" \
  --max-workers 8 \
  --iterations 2 \
  --max-input-tokens 1024 \
  --model gpt-4o-mini \
  --log orchestrate_log.jsonl \
  --verbose
```

### Evaluator-Optimizer

Generate and iteratively improve content using an evaluator-optimizer loop:

```bash
workflows optimize \
  --prompt "Write a product description for a new AI-powered coffee mug." \
  --target 0.8 \
  --max-iters 3
```

**Options:**
- `--prompt TEXT`: The initial prompt to generate content (required, or pipe via stdin).
- `--target FLOAT`: Target score (0-1) to stop optimizing (default: 0.9).
- `--max-iters INT`: Maximum optimization iterations (default: 5).
- `--evaluator-system PATH|TEXT`: Path to rubric file (markdown/text) or rubric string for evaluation (optional).
- `--model TEXT`: Override the model for all LLM calls.
- `--stream/--no-stream`: Stream output as it is generated (default: stream).
- `--log FILE`: Write a JSONL execution log for all steps.
- `--verbose, -v`: Print intermediate steps and extra diagnostics.

**How it works:**
1. Generates an initial output from the prompt.
2. Evaluates the output using a rubric (default or custom).
3. If the score is below the target and max-iters not reached, revises the output using evaluator feedback and repeats.
4. Prints the final answer (and logs the trace if `--log` is set).

**Test Example:**

You can run a quick test to verify the workflow:

```bash
workflows optimize --prompt "List two benefits of using solar energy." --target 0.5 --max-iters 2 --verbose
```

Expected: The tool will generate an answer, evaluate it, and (if needed) revise it once, printing intermediate steps and the final output.
