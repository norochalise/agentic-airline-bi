# Contributing

How to set up, change and verify this project. For what the system does and why, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). For how quality is measured, read [`docs/EVALUATION.md`](docs/EVALUATION.md).

## Setup

The project uses [`uv`](https://docs.astral.sh/uv/) and Python 3.13. Run everything through `uv run`.

```powershell
uv sync                                   # app + dev tools (pytest, pytest-cov, ruff)
copy .env.example .env                    # then fill in your keys
uv run abi-serve [--reload] [--port N]    # API + chat UI at http://127.0.0.1:8000 (/docs for OpenAPI)
```

The settings are listed in the [README](README.md#configuration). `OPENAI_API_KEY` and `OPENAI_MODEL` are required; the server refuses to start without them.

**Windows:** stop any running dev server before `uv sync --reinstall`. A running process locks faiss's `.pyd` file and leaves the install half-done.

## Checks before every change

```powershell
uv run pytest                             # full suite: fake model clients, no API cost
uv run pytest tests/test_agent_tools.py::test_repeated_identical_call_stops_the_run   # one test
uv run pytest --cov=agentic_bi            # coverage
uv run ruff check --fix ; uv run ruff format
```

CI (`.github/workflows/ci.yml`) runs `uv sync --frozen`, `ruff check`, `ruff format --check` and `pytest`, then builds the Docker image. After changing dependencies, run `uv lock` and commit `uv.lock`, or `--frozen` fails.

## Evaluations

Each evaluation is a console script in `pyproject.toml`. Compare results with the baseline in [`docs/EVALUATION.md`](docs/EVALUATION.md). A regression in routing or retrieval blocks a change.

| Free (local) | Paid (calls OpenAI) |
|---|---|
| `abi-eval-routing` | `abi-eval-interaction` |
| `abi-eval-retrieval` | `abi-eval-tools` |
| `abi-eval-reranked` | `abi-eval-arguments` |
| | `abi-eval-e2e` |
| | `abi-eval-analytics` |

Run the paid suites only when model-facing behaviour changes: prompts, tool descriptions, schemas or routing.

**Evaluation data is frozen.**
- Never change the cases or labels in `evals/` to make a method pass.
- `evals/retrieval_qrels.json` is the single source of retrieval labels. `retrieval_002` is a fragmented case: it needs both chunks for context coverage and has no strict ranked hit.
- Chunk IDs look like `<file-stem>:p<page>:c<n>` (PDF) or `<file-stem>:c<n>` (text).

## Changing things safely

**Tools.** Every tool is one `ToolSpec` in `tools/registry.py`. Its OpenAI schema, the capability list in the prompt and the access policies are generated from it, so change a tool in one place only.
- The pydantic `Field(description=...)` text in `core/schemas.py` is what the model sees. Editing it changes model behaviour, so run the paid tool and argument evals afterwards.
- Write tools are registered with `offered_to_model=False` and need `approved=True`.

**Stable names.** Stop reasons, trace event names and `error_type` strings are asserted by the tests and the evaluations. Don't rename them.

**Configuration.** `config.py` is the only place that resolves paths, loads `.env` and holds constants.
- Settings are read at call time through functions such as `openai_model()`. Don't cache environment values at import time; the tests rely on `monkeypatch.setenv`.
- Don't compute paths with `Path(__file__).parents[n]` anywhere else.

**Documents and the RAG index.** After changing `data/raw/delta_small_pack/documents/`, rebuild with `uv run python scripts/build_embedding_cache.py`, then `uv run python scripts/build_faiss_index.py`. Unchanged documents must reproduce identical embeddings (700 × 384).

**Frontend.** `src/agentic_bi/frontend/` is plain HTML, CSS and JavaScript with no agent logic. The CDN scripts are pinned with SRI hashes; if you bump a version, recompute its hash.

## Tests

- `tests/conftest.py` provides `FakeClient` (a scripted Responses API), `function_call`, `model_response`, `token_usage`, `tools_with(**funcs)`, `routed_to(intent)` and a `run_store` fixture.
- Agent tests inject fakes: `run_agent(q, client=FakeClient([...]), store=run_store, tools=tools_with(...))`, monkeypatching only `classify_interaction` or `select_skill` on `agentic_bi.core.agent`.
- Fake tool outputs must satisfy the tools' output models; for example, knowledge results need `retrieval_type`.
- No test may call a paid API.

## Docker

- `docker compose up --build` reads `.env`. The image bakes in the models and data, and sets `HF_HUB_OFFLINE=1` at runtime.
- If `EMBEDDING_MODEL` or `RERANKER_MODEL` change, update the model names in the `Dockerfile`; `tests/test_packaging.py` enforces this.
- On Linux, torch comes from PyTorch's CPU-only index (`[tool.uv.sources]`). Keep it that way, or the image gains several GB of CUDA libraries.

## Notebook

`notebooks/agentic_airline_bi_concepts.ipynb` is standalone: it implements each concept itself and does not import `agentic_bi`. It is committed with outputs and must stay free to run, with its live cell off by default.

```powershell
uv sync --group notebook
uv run jupyter lab notebooks/agentic_airline_bi_concepts.ipynb
```

Ruff lints notebooks too, so run `ruff check` and `ruff format` after editing one.

## Conventions

- **Formatting:** ruff with `skip-magic-trailing-comma` and line length 88. Don't reintroduce one-argument-per-line formatting. The reformat commit is listed in `.git-blame-ignore-revs`.
- **Media:** README images, the demo GIF and the MP4 live in `docs/images/`.
- **Commits:** one logical change per commit, with a conventional prefix (`feat:`, `fix:`, `docs:`, `build:`, `test:`, `chore:`).
