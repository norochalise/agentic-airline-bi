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
| Tests | 52 (agent tests broken) | **115**, all passing |
| Python lines | 8,590 | ~6,500 |
| `core/agent.py` | 1,021 lines, one ~840-line function | 789 lines in small functions |
| Places one tool is defined | 7 | **1** (`ToolSpec`) |
| `PROJECT_ROOT` definitions | 15, some wrong | 1 (`config.py`) |
| Data-tool call | ~2.3 s (new subprocess) | **0.02 s** (in-process) |
| Routing eval | 15/15 | 15/15 |
| Retrieval Hit@3 / MRR (baseline → reranked) | 80% / 0.650 → 90% / 0.750 | unchanged |

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
| Retrieval Hit@3 (baseline → reranked) | 80% → 90% |

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

---

## How we verified without burning API money

- **Free:**
  - `pytest` uses fake OpenAI and Exa clients
  - routing and retrieval evals run on local models
  - the data tool runs on a local CSV
- **Paid, at milestones only:** live `/ask` questions and the LLM evals (tool selection, arguments, end-to-end).
- **Snapshot diffs:** the generated tool JSON and prompts were compared with the originals before any paid run was needed.

## What's next

5. **Hardening:** API error handler, input length limit, model warm-up, SRI on CDN scripts, shared eval code, shorter README.
6. **Richer analytics:** more data questions (delays, routes, on-time performance) and charts in the chat.
7. **Conversation UX:** streamed answers and follow-up questions.
8. **Ship it:** Docker, CI and a live demo.
