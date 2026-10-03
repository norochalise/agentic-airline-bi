# Refactor Journey: Agentic BI Assistant

A short log of how the Airline Intelligence Assistant went from "broken after a bad patch" to a cleaner, tested and measurable codebase. Each step lists the problem, what was done, the result and the lesson. It is written as raw material for an article.

**The project.** A bounded, agentic business-intelligence assistant over Delta airline data:
- **Routing:** an LLM interaction router.
- **Tools:**
  - a RAG pipeline (FAISS + cross-encoder reranking) over company documents
  - a deterministic pandas tool over flight data, also served over MCP
  - an official-web search restricted to delta.com and U.S. government sites
- **Controls:** pydantic validation, retries, guards, traces, a FastAPI backend with a chat frontend, and an evaluation suite.

**The rule for every step:** the tests stay green, and the evals don't regress against a recorded baseline.

---

## The numbers

| | Before | Now |
|---|---|---|
| Tests | 52 (agent tests broken) | **173**, all passing (also in CI) |
| Python lines | 8,590 | ~6,500 |
| `core/agent.py` | 1,021 lines, one ~840-line function | 789 lines in small functions |
| Places one tool is defined | 7 | **1** (`ToolSpec`) |
| `PROJECT_ROOT` definitions | 15, some wrong | 1 (`config.py`) |
| Data-tool call | ~2.3 s (new subprocess) | **0.02 s** (in-process) |
| Data question types | 1 (origin cancellation rate) | 6 metrics × 6 groupings + delay causes, with charts |
| Routing eval | 15/15 | 15/15 |
| Retrieval Hit@3 / MRR (FAISS → reranked, strict labels) | 70% / 0.600 → 90% / 0.750 | unchanged |

---

## Step 0: Safety net

**Problem**
- `core/agent.py`, the heart of the app, had been overwritten by a "patch script" that was meant to edit it. The API, the agent tests and the agent evals all failed on import.
- There was no version control in the working copy.

**What we did**
- Started using git.
- Restored the agent from the original project's history, then re-applied the intended changes: answer sources, a web-search counter, and source collection.
- Ran every test and eval and recorded the numbers as a **baseline** in `docs/EVALUATION.md`:

| Eval | Result |
|---|---|
| Routing | 15/15 |
| Tool selection | 15/15 |
| Arguments | 7/7 |
| End-to-end | 8/8 |
| Retrieval Hit@3 (FAISS → reranked) | 70% → 90% |

**Lesson:** before refactoring anything, make it work, put it in version control, and write the numbers down. Every later step is judged against them.

## Feature: official-web fallback with documents-first routing

**Problem**
- Web search only ran for explicitly "current" questions, and only on delta.com.
- A keyword router chose the skill, so questions without the right keywords lost their tools.

**What we did**
- Web search now covers delta.com, transportation.gov, faa.gov and bts.gov.
- The LLM router's intent picks the skill; keywords are only a fallback.
- Document questions get **one** web search, and only after a private document search.
- A controller guard enforces that ordering, and data questions are never offered web search.
- Added an interaction-routing eval (15/15).

**Lesson:** let the component that already understands the question (the LLM router) make the decision, and keep cheap heuristics as fallbacks. Enforce safety rules in code, not just in the prompt.

## Frontend redesign

**What we did**
- Rebuilt the UI as a chat thread with suggestion cards, a light/dark theme, labelled sources (document page, dataset, web URL) and collapsible run details.
- Added a "Demo" badge and a disclaimer: limited data, not affiliated with the airline, check official sources.

**Two real-world bugs**
- *Stale cache:* browsers paired an old `index.html` with a new stylesheet. Fixed with `Cache-Control: no-cache`; ETags keep it cheap.
- *Firefox-only:* Firefox restores form-control state on reload, including `disabled`. A reload during a request left the input locked forever. Fixed by resetting the busy state on load.

**Lesson:** "works in Chrome" is not done. Testing in a fresh headless Firefox profile separated real code bugs from a stale local cache.

## Step 1: Bug fixes

**Bugs found in review**
- **Substring matching.** Keyword routing used `"rate" in question`, so "corporate" counted as a data question. "rag" matched "average" and "data" matched "update". Fixed with whole-word matching in one shared helper.
- **Wrong project root.** The index-building scripts used `Path(__file__).parents[2]`, which pointed at the Desktop, not the repo. Fixed, and given a `main()`.
- **Every error retried.** The MCP client turned *every* error into a "transient, please retry" error, so permanent failures were retried for nothing. Now only connection and timeout errors are retried.
- **Small cleanups:** a duplicate import, and an empty `.env.example`.

**Verification:** the RAG index was rebuilt with the fixed scripts and gave identical embeddings (700 × 384).

**Lesson:** a substring match is not a word match. And when you fix a data pipeline, rebuild the data and prove it's byte-identical.

## Step 2: Formatting baseline

**Problem:** the code was formatted one argument per line, even for one-argument calls. That roughly doubled its length and hid the logic.

**What we did**
- Adopted **ruff** for formatting and linting.
- The key setting was `skip-magic-trailing-comma`. Without it, ruff keeps every trailing comma and changes nothing.
- 8,590 → 6,536 lines (−24%).
- The reformat went in its own commit and is listed in `.git-blame-ignore-revs`, so `git blame` still points at real changes.

**Lesson:** reformat in a separate commit with no logic changes, so every later diff stays readable.

## Step 3: Central configuration

**Problem**
- 15 modules computed the project root, with different `parents[n]` values; that was the source of the Step 1 path bug.
- `.env` was loaded as an import side effect in 4 places.
- A missing setting crashed mid-request with a bare `KeyError`.
- Indexed files stored absolute paths that included the developer's username.

**What we did**
- One `config.py` holds:
  - every path, derived from one root
  - `.env`, loaded once
  - settings read through functions that raise a clear error naming the missing variable
  - the model and retrieval constants
- The API refuses to start without its required keys.
- Indexed paths are now project-relative.

**Lesson:** read settings when they're used, not at import time. Tests and deployments can then change them, and a missing value fails at startup with a message, not mid-request.

## Step 4: Core architecture

**Problems**
- **Tool sprawl.** Adding one tool meant editing 7 places (schema JSON, function map, input and output models, retry policy, access policy, prompt text).
- **One giant function.** `run_agent` was a single ~840-line function.
- **Wired-in dependencies.** Tests had to monkeypatch module globals to swap the OpenAI client and file writes.
- **Slow data questions.** Every data question started a new MCP subprocess, taking about 2.3 s.
- **Unused safety guard.** The write-action approval guard existed, but the agent loop never called it.

**What we did**
- **One `ToolSpec` per tool.** The OpenAI tool JSON and the prompt's capability list are now *generated*. We proved the generated output byte-identical to the old hand-written text against a saved snapshot, so the model sees exactly the same thing.
- **Agent split into a pipeline:** `interaction_gate` → `choose_skill` → `run_tool_loop` → `finish_run`.
- **One path per tool call:** `handle_tool_call` applies the guards, then `execute_tool` runs access policy → retry → output validation. The approval guard now actually runs.
- **Dependency injection:** `run_agent(question, client=…, store=…, tools=…)`. Tests pass fakes from a shared `conftest.py`.
- **Data tool in-process by default:** 0.02 s instead of 2.3 s. MCP stays available with `TOOL_TRANSPORT=mcp`.
- **Richer search results:** knowledge results now say how each chunk was retrieved (`reranked` vs `neighbor_*`) and carry real scores. Before, neighbour chunks got a fake `0.0`.
- **Persistence:** shared JSON helpers, a run store that keeps the newest 500 runs (`MAX_SAVED_RUNS`) and can be switched off (`PERSIST_RUNS=false`), and logging instead of `print`.

**A bug the new tests caught:** pruning sorted runs by timestamp. Two runs saved in the same timestamp tick could delete the run being saved. Pruning now always protects the current run.

**Lesson:** one definition per concept, everything else generated from it. And when you generate what the LLM sees, diff it against the old version before you trust it.

## Step 5: Hardening and cleanup

**API**
- `/ask` used to turn any failure into a bare 500. It now returns `{detail, error_id}` and logs the traceback under the same ID; nothing internal reaches the browser. A missing setting returns 503.
- Questions are capped at 2,000 characters, which bounds the cost of a single request.
- **Startup warm-up:** about 13.5 s of model loading (FAISS + embeddings 7.5 s, reranker 5.1 s, flight data 0.9 s) now happens at server start instead of on the first user's question.
- The CDN scripts are pinned with **Subresource Integrity** hashes, so the browser refuses a tampered file.

**Evaluation**
- The same loaders and metrics were copied in 8 eval scripts; they now live in `evaluation/common.py`.
- **Two copies of the labels disagreed.** The retrieval labels were hard-coded in one eval and stored in a JSON file for another, and they differed on one chunk. Both chunks contained the answer and the metrics came out identical, so the frozen JSON file became the only source, unchanged.
- Every eval got a short command (`uv run abi-eval-routing`, …), and the server one (`uv run abi-serve`).

**Tests and cleanup**
- New unit tests for the pandas analysis, chunking and ingestion (using a generated PDF with a blank page), and the eval metrics: **141 tests**.
- Removed an unused brute-force retriever.

**Environment and docs**
- **A broken environment.** The `.venv` had been copied from another folder, so `uv run pytest` silently ran the *other* project's code. Rebuilding it failed halfway because a running dev server locked a faiss DLL. Lesson: stop processes before reinstalling on Windows.
- The README went from 680 to 144 lines, all current.

**Paid check (once, at the end of the step):** interaction 15/15, tool selection 15/15, arguments 7/7, end-to-end 8/8 with 0 failures, and five live questions each routed correctly. Every result matches the baseline recorded before the refactor.

**Lesson:** keep running the free checks while working, and save the paid evals for one run at the end of a step. Because the generated prompts were proven identical first, that one paid run was a confirmation rather than a debugging session.

## Step 6: Richer analytics and charts

**Problem:** the data path could answer one question shape, "origin airports by cancellation rate". The dataset holds much more: 149k flights, 211 airports, routes, operating carriers, delay minutes, five delay causes, cancellation codes and diversions.

**What we did**
- **Two flexible tools, not ten narrow ones:**
  - `rank_flight_performance` groups by origin, destination, route, carrier, date or weekday; ranks by cancellation rate, on-time rate, average delay, diversion rate or flight count; filters by airport; and compares named groups.
  - `analyze_delay_causes` breaks down delay minutes and cancellations by cause.
- The original tool stayed, so the frozen evals still apply. The new ranking reproduces its numbers exactly.
- **Charts:** data answers now come with a ranked bar chart, a hover/focus tooltip and a table toggle. The chart colour was validated for contrast and colour-blindness in light and dark mode, and every view was checked in a real browser.

**A metric bug caught by checking against an outside source.** My first on-time rate left cancelled and diverted flights out. The DOT report in our own document set counts them as *not on time*. With the DOT rule, the data reproduces the report exactly: **71.7%** for the Delta network and **71.9%** for mainline. The first version would have overstated on-time performance by about 3 points. A test now pins those figures.

**Keeping the model's view stable:** the new tools are offered only to data questions, so the document-question prompt stayed byte-identical.

**Evaluation:** a *new* 8-case analytics eval, kept separate from the frozen sets, passed 8/8, including "compare JFK and LGA". The regression evals stayed at tool selection 15/15, arguments 7/7 and end-to-end 8/8, so the original questions still choose the original tool.

**Lesson:** when a metric has a published definition, reproduce a published number before trusting your own.

## Step 7: Conversation UX

**What we did**
- **Live progress.** The agent got a small hook that reports every trace event as it happens. A streaming endpoint (`/ask/stream`, Server-Sent Events) turns those events into plain-language steps, and the chat shows them in place of a blind spinner: "Planning a flight-data analysis…" at 2.3 s, "Analyzing flight data…" at 4.3 s, the answer at 6.1 s.
- **Follow-up questions.** The browser sends the last three exchanges. A single model call rewrites "and what about JFK's on-time rate?" into a standalone question, and routing, tools and evals work unchanged on that question. The answer shows how the question was understood.
- **Feedback.** 👍/👎 is stored with the run ID, so a bad rating can be joined with its full trace.

**Design choice:** rewriting the question was chosen over passing the chat history to every component. All the earlier work (evals, guards, tool selection) still applies to one self-contained question, and the extra cost is only paid when there *is* history.

## Step 8 (part 1): Docker and CI

**Docker**
- One `docker compose up --build` runs the whole app. The image bakes in the models and data, so the container starts with **no downloads** (models load in 0.3 s).
- It runs as a non-root user, has a health check, and keeps run logs and feedback in volumes.

**A hidden 4+ GB problem.** sentence-transformers pulls in PyTorch, and on Linux the default PyTorch wheel bundles CUDA plus several GB of NVIDIA libraries. A CPU-only app never uses them. Pointing uv at PyTorch's CPU index *for Linux only* removed every `nvidia-*` package from the lock. The image is now 2.8 GB, Windows and macOS are untouched, and CI installs are much faster.

**CI.** A GitHub Actions workflow runs ruff, the 173 tests and a Docker build on every push and pull request.
- The tests use fake model clients, so CI needs **no API keys and costs nothing**.
- A small test keeps the Dockerfile's baked-in model names in sync with `config.py`.
- `.gitattributes` pins LF line endings, because CRLF from a Windows checkout breaks multi-line Dockerfile commands.

**Verified locally:** the image built, the container started healthy, and it answered a real document question with 6 sources and no errors. The workflow runs once the repository is pushed to GitHub.

**Lesson:** check what your dependencies pull in. The largest part of the image came from GPU libraries for hardware the app never uses.

**Rate limiting.** On a public demo, every question spends real money on OpenAI and Exa calls.
- `/ask` and `/ask/stream` allow 10 questions per minute per client (`ASK_RATE_LIMIT`). `ASK_DAILY_LIMIT` adds an optional cap across all visitors, so a burst of traffic cannot run up the bill.
- Over a limit, the endpoints return 429 with `Retry-After` before any model call. The UI already shows the message.
- The limiter is a small in-memory sliding window instead of a new dependency, which fits a single-instance demo.
- Invalid questions are rejected first and do not use up the budget.

**Cost and latency per answer.** Each answer now shows its tokens, an estimated cost and where the time went.
- One wrapper around the OpenAI client (`MeteredClient`) times every model call and reads its token usage. The follow-up rewriter, the router, the web answerer and the tool loop all already used the run's client, so none of them changed.
- Calls are grouped by stage. Tool time comes from the trace's existing `tool_completed` durations.
- Prices are settings, not a table in the code: model prices change, and the model is configurable. Without prices, the UI shows tokens only.
- The run details panel shows a "where the time went" bar. It usually shows that model calls, not pandas or retrieval, dominate the wait.

**Presentation.** A recorded demo, screenshots, a rewritten README with highlights, a tech-stack table and a roadmap, and an MIT license.
- The 14.8 MB, 3½-minute screen recording became a 7.9 MB GIF for the README: 960 px wide, 2× speed, with a custom palette so the text stays sharp. The full recording is kept as a 5 MB MP4.
- **Screenshots find bugs.** One screenshot showed "Tool time 0.0s" on a web answer. The official-web path runs its Exa search outside the tool loop, so the search time was counted as "other". The search is now timed and counted as tool time, with a test.

**A CI trap found on the way.** Ruff 0.16 also formats Python code blocks inside markdown. It would have rewrapped the hand-aligned `ToolSpec` example in `ARCHITECTURE.md` and failed `ruff format --check` on the first push. Markdown is now excluded from the formatter.

---

## How we verified without burning API money

- **Free:**
  - `pytest` uses fake OpenAI and Exa clients
  - routing and retrieval evals run on local models
  - the data tool runs on a local CSV
- **Paid, at milestones only:** live `/ask` questions and the LLM evals (tool selection, arguments, end-to-end).
- **Snapshot diffs:** the generated tool JSON and prompts were compared with the originals before any paid run was needed.

## What's next

8. **Ship it (part 2):** push to GitHub so CI runs, then deploy the live demo.
