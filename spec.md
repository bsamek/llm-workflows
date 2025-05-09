**Technical Spec & Architecture
Python “workflows” wrapper for the `llm` CLI**

---

### 1 · Project goals

| Objective                                                                                                                                                                                                                                 | Details |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Provide a thin Python front‑end (“workflows”) that implements **five canonical agentic workflows**—*prompt chaining, routing, parallelization, orchestrator‑workers, evaluator‑optimizer*—on top of the existing `llm` command‑line tool. |         |
| Hide `llm` syntactic details behind single‑word sub‑commands (`chain`, `route`, `parallel`, `orchestrate`, `optimize`).                                                                                                                   |         |
| Offer a consistent, composable interface; unify logging, configuration, streaming, model selection and error handling.                                                                                                                    |         |
| Keep the wrapper 100 % stateless (aside from an optional YAML/INI config file) so it can be dropped into CI pipelines, notebooks or shell scripts.                                                                                        |         |

---

### 2 · High‑level architecture

```
workflows/
├── __main__.py          # Typer (or argparse) CLI entry‑point
├── engine/              # Workflow engines share a small runtime helper layer
│   ├── llm_runner.py    # Thin wrapper around subprocess / llm Python API
│   ├── models.py        # Model resolution / fallbacks
│   ├── streaming.py     # Unified stdout/err streaming & capture
│   └── logging.py       # Structured JSON + txt logs
└── workflows/           # One module per workflow
    ├── chain.py
    ├── route.py
    ├── parallel.py
    ├── orchestrate.py
    └── optimize.py
```

* **CLI Framework:** Typer (`pip install typer[all]`) for pleasant `--help` UX and automatic Bash completion.
* **Process execution:** Prefer `import llm` if present, else fallback to `subprocess.run(["llm", …])` so the tool works in either environment.
* **Concurrency:** `asyncio`, with a safe fallback to `concurrent.futures` when the event loop is unavailable.
* **Config discovery (optional):** `$XDG_CONFIG_HOME/workflows/config.{yaml|ini}` for defaults (model, temperature, max\_workers). CLI flags always take precedence.
* **Logging:** `--log file.jsonl` writes one JSON record per step; `--verbose` streams to stderr.
* **Exit codes:** `0` = success; `10` = validation error; `20` = llm execution error; `30` = evaluation threshold not met; `>=50` = uncaught.

---

### 3 · Shared CLI flags

| Flag                     | Purpose                                                   | Default                       |
| ------------------------ | --------------------------------------------------------- | ----------------------------- |
| `-m, --model TEXT`       | Override model for **all** inner `llm` calls              | `$LLM_MODEL` or `gpt‑4o-mini` |
| `--stream / --no-stream` | Mirror `llm --[no-]stream`                                | stream                        |
| `--max-workers INT`      | Parallel worker cap (parallel/orchestrate only)           | `min(32, os.cpu_count()*4)`   |
| `--config FILE`          | Load extra defaults                                       | auto‑detect                   |
| `--log FILE`             | Write JSONL execution log                                 | none                          |
| `--dry-run`              | Print planned `llm` invocations, execute nothing          | false                         |
| `--gate-schema FILE`     | JSON schema to validate intermediate outputs (chain only) | none                          |

---

### 4 · Workflow‑specific specifications

#### 4.1 · Prompt chaining → `chain`

| Aspect        | Specification                                                                                                                                  |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Purpose       | Sequential decomposition of a task into N deterministic steps.                                                                                 |
| Invocation    | `python workflows chain --prompt "<p1>" --prompt "<p2>" ...` (≥2 `--prompt` flags or `--prompts-file path.txt` one‑per‑line).                  |
| Semantics     | Step *1* executes `<p1>`; its **raw** output (optionally gated by `--gate-schema`) is appended to `<p2>` separated by two newlines, and so on. |
| Failure modes | a) Gate schema validation fails → exit 20; b) any `llm` call non‑zero → exit 20.                                                               |
| Output        | Stdout of final step **only** (unless `--verbose`, which streams intermediates).                                                               |

---

#### 4.2 · Routing → `route`

| Item          | Details                                                                                                                                                                                      |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Purpose       | Classify input then dispatch to specialised follow‑ups.                                                                                                                                      |
| Routing table | Supplied via `--routes yaml_or_json`. Keys are labels; values may specify<br>• `system:` (system prompt),<br>• `model:` override,<br>• `template:` prompt string with `{input}` placeholder. |
| Classifier    | By default a zeroshot `llm` call to `"Classify the following input into {labels}"`. Replaceable via `--classifier-system` / `--classifier-prompt`.                                           |
| Invocation    | `python workflows route --input "User text…" --routes routes.yaml`                                                                                                                           |
| Output        | The dispatched `llm` response. Add `--print-label` to prepend the chosen label.                                                                                                              |

---

#### 4.3 · Parallelization → `parallel`

| Mode           | CLI selector                                    | Behaviour                                                                                                                                                                      |
| -------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Sectioning** | `--section size=500` or `--section regex="^# "` | Split stdin or file into chunks; run the same prompt for every chunk concurrently; aggregate either by concatenation (`--aggregate concat`) or JSON list (`--aggregate json`). |
| **Voting**     | `--vote n=5`                                    | Run *n* identical `llm` calls; aggregate using majority vote (`--vote-mode majority`) or best‑of (`--vote-mode max‑tokens`, chooses answer with most tokens).                  |

Common flags: `--max-workers`, `--timeout`, `--dedupe` (drop duplicate answers before vote).

---

#### 4.4 · Orchestrator‑workers → `orchestrate`

| Component             | Description                                                                                                                                                                               |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Orchestrator loop** | 1) Call `llm` with `--system ORCHESTRATOR_SYSTEM_PROMPT` and original user request.<br>2) Expect JSON‑schema result `{"tasks": [{"id": 1, "prompt": "..."}], "aggregate_prompt": "..."}`. |
| **Workers**           | Execute each `tasks[i].prompt` concurrently (respect `--max-workers`).                                                                                                                    |
| **Aggregation**       | Feed *all* worker outputs into `aggregate_prompt` (system prompt fixed: `"Synthesize the following worker results"`).                                                                     |
| **Iteration**         | `--iterations k` (default 1). After synthesis, the orchestrator may decide more tasks; loop until `tasks == []` or `i == k`.                                                              |
| **Safety**            | `--max-input-tokens` drops any worker output > N tokens to avoid runaway costs.                                                                                                           |

---

#### 4.5 · Evaluator‑optimizer → `optimize`

| Phase              | Details                                                                                                                                 |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| 1️⃣ Generator      | `llm` called with user prompt (`--prompt` or stdin).                                                                                    |
| 2️⃣ Evaluator      | `llm` called with `--system EVALUATOR_SYSTEM_PROMPT` + generator output + rubric. Must return JSON `{"score": float, "feedback": str}`. |
| 3️⃣ Optimizer loop | If `score < --target (0‑1)` and `iter < --max-iters`, feed `feedback` back to generator using a *“revise”* template and repeat.         |
| CLI                | `python workflows optimize --prompt "...“ --target 0.9 --max-iters 5 --evaluator-system rubric.md`                                      |
| Termination codes  | `0` = met target;<br>`30` = reached max‑iters without target.                                                                           |
| Artifacts          | Final answer printed; evaluation trace stored in `--log`.                                                                               |

---

### 5 · Integration & extensibility guidelines

* **Dependency safety:** Pin `llm>=0.12.0` in `pyproject.toml`; expose `extra_requires["dev"]` for `ruff`, `pytest`, `pre‑commit`.
* **Unit tests:** Mock `llm_runner.run()`; assert JSON log structure and CLI exit codes.
* **Cost control hooks:** `--cost-limit USD` reads token counts via `llm logs -c --json` after each call; aborts when exceeded.
* **Plugin interface:** Other teams can add new workflows by subclassing `engine.base.Workflow` and registering through entry‑points `workflows.plugins`.

---

### 6 · Deliverables for the implementation LLM

1. **Codebase skeleton** exactly matching the directory tree above.
2. Fully typed Python (PEP 561) with docstrings referencing this spec section numbers.
3. 90 %+ test coverage using `pytest‑asyncio`.
4. README.md summarising usage examples (focus on a single concise example per workflow, avoid verbosity).
5. Continuous integration (GitHub Actions) running lint + tests on Python 3.10 ↔ 3.12.

---

### 7 · Future considerations (out‑of‑scope for v1)

* Inline tool‑calling support for upcoming `llm mcprotocol` helpers.
* Live progress UI (Rich or Textual) around streaming tokens.
* Persistent experiment tracking (e.g., SQLite) rather than file logs.