# Evaluation

How the assistant is measured, what the numbers are, and what they do and don't show.

> All AI and retrieval results below come from **small, frozen development sets**. They show that the system behaves as designed on known cases. They are **not** estimates of production accuracy.

---

## 1. Principles

1. **Freeze before optimising.** Cases and labels are fixed before a method is tuned. A label is never changed because a method passed or failed.
2. **Measure each layer separately.** Routing, tool choice, arguments, retrieval and the final answer fail in different ways. Separate measurements show *where* a failure is.
3. **Evaluate the trajectory, not just the text.** A fluent answer can come from the wrong tool or weak evidence.
4. **Keep ranked retrieval apart from context construction.** Neighbour chunks help the answer but never get fake ranks.
5. **Check against an outside source when one exists.** Computed metrics are compared with published figures (see §6).
6. **Record failures.** Failures are classified and kept; the most useful lessons came from them (§8).
7. **Test software deterministically.** `pytest` checks code contracts with fake model clients; the evals check model behaviour. They answer different questions.

---

## 2. The evaluation suites

| Suite | Command | Cases | Measures | Cost |
|---|---|---:|---|---|
| Skill routing | `uv run abi-eval-routing` | 15 | Keyword router → expected skill | free |
| Interaction routing | `uv run abi-eval-interaction` | 15 | LLM intent classifier, including web conditions | paid |
| Tool selection | `uv run abi-eval-tools` | 15 | Agent calls the expected tool(s) | paid |
| Arguments | `uv run abi-eval-arguments` | 7 | Structured arguments (`min_flights`, `top_n`) | paid |
| End-to-end | `uv run abi-eval-e2e` | 8 | Skill, tool, arguments, stop reason, errors, required answer facts | paid |
| Flight analytics | `uv run abi-eval-analytics` | 8 | Skill, tool and key arguments for the analytics tools | paid |
| Retrieval (FAISS) | `uv run abi-eval-retrieval` | 10 | Hit@K and MRR against verified chunk labels | free |
| Retrieval (reranked) | `uv run abi-eval-reranked` | 10 | FAISS vs reranked on strict labels, plus context coverage | free |
| Software | `uv run pytest` | 192 tests | Deterministic contracts, fake clients | free |

The case files live in `evals/`:
- `agent_cases.json`
- `interaction_cases.json`
- `agent_end_to_end_cases.json`
- `analytics_cases.json`
- `retrieval_cases.json` and `retrieval_qrels.json`

**"Paid"** means the eval calls the OpenAI API: a few cents per run, and about $1–2 for all of them together.

---

## 3. Current results

| Evaluation | Result |
|---|---:|
| Skill routing | **15/15** |
| Interaction routing | **15/15** |
| Tool selection | **15/15** |
| Arguments | **7/7** |
| End-to-end | **8/8**, 0 classified failures |
| Flight analytics | **8/8** |
| pytest | **173 passed** |

Retrieval, with strict answer-bearing labels on the same 10 cases:

| Metric | FAISS baseline | + cross-encoder rerank |
|---|---:|---:|
| Hit@1 | 50% | **60%** |
| Hit@3 | 70% | **90%** |
| Hit@5 | 70% | **90%** |
| MRR@5 | 0.600 | **0.750** |
| Expanded-context evidence coverage | — | **10/10** |

`abi-eval-retrieval` reports a FAISS baseline of Hit@3 80% and MRR 0.650. The difference is one case:
- `abi-eval-retrieval` counts `retrieval_002`, whose answer is split across two chunks, as a hit when *either* chunk is retrieved.
- The reranked comparison treats it strictly: it has no single answer-bearing chunk, so it only counts toward context coverage, and only when *both* chunks are present.

Both numbers are reported, and each eval states its rule.

---

## 4. Agent behaviour: routing, tools, arguments

The 15 agent cases mix structured-data questions, document questions and boundary cases, such as a policy question that mentions cancellations.

**Why three separate measurements:**

```text
correct skill? → correct tool? → correct arguments? → execution → answer
```

A correct route doesn't guarantee the right tool, and the right tool doesn't guarantee valid arguments. Measuring each stage tells you which one broke.

**A targeted fix, not a rewrite.** One case, about Delta's customer commitments during disruption, was first routed to data analysis. The fix was narrow:
- add "commitment" as a knowledge term;
- drop the overly generic keyword "flight", while keeping the stronger phrase "flight data".

The same 15 cases were then re-run: 15/15. Later the matching moved to whole words. Before that, "rate" matched "corporate" and "rag" matched "average". The routing score was unchanged, and the false matches are now covered by tests.

---

## 5. Retrieval

**Labels.** `evals/retrieval_qrels.json` lists, for each case, the chunk IDs that actually contain the answer. They were verified by reading and visually inspecting the source pages, not by looking at retrieval output. Retrieving the right *document* is not enough; the eval asks whether the *answer-bearing chunk* was found.

**Metrics:**
- **Hit@K:** a verified answer-bearing chunk appears in the top K.
- **MRR@5:** the mean of 1/rank of the first such chunk (0 if it isn't in the top 5).
- **Context coverage:** the final expanded context (top 5 plus neighbours) contains enough evidence. For a fragmented case, that means *all* of its required chunks.

**What improved retrieval:**
1. **Cross-encoder reranking** (`ms-marco-MiniLM-L6-v2`) over the 15 FAISS candidates moved answer-bearing chunks up: Hit@3 70% → 90%, MRR 0.600 → 0.750.
2. **Neighbour expansion** (the previous and next chunk from the same document) recovered evidence split across chunk boundaries, bringing context coverage to 10/10.

**What the results support:** on these cases, two-stage retrieval puts answer-bearing evidence in front of the model much more reliably than FAISS alone. They do not show general retrieval quality on unseen questions.

---

## 6. Data analytics

**Analytics eval.** Eight cases cover the analytics tools:
- the lowest on-time rate among routes from ATL (with a route-volume threshold)
- the highest average arrival delay by destination
- a direct JFK vs LGA comparison (`only=["JFK","LGA"]`)
- the best operating carrier
- weekdays in calendar order
- overall delay causes and ORD-only delay causes
- the highest diversion rate

The eval checks the skill, the tool and only the arguments the question pins down. Result: **8/8**.

**Regression.** Adding the new tools changed the data-analysis prompt, so the original suites were re-run. Tool selection stayed 15/15, arguments 7/7 and end-to-end 8/8, so the original cancellation questions still choose the original tool.

**Validation against the DOT report.** The DOT Air Travel Consumer Report is in the document set, and it publishes July 2026 on-time rates. The first implementation computed on-time rates over completed flights only; the DOT counts cancelled and diverted flights as *not on time*.

| | Completed flights only | DOT definition | DOT report |
|---|---:|---:|---:|
| Delta network | 74.52% | **71.67%** | **71.7%** |
| DL mainline | 74.10% | **71.86%** | **71.9%** |

The implementation now uses the DOT definition, and `tests/test_flight_metrics.py` pins both figures. Without the outside check, on-time performance would have been overstated by about 3 points.

The new ranking tool also reproduces the original cancellation tool exactly (LGA 11.43%, JFK 10.78%, DCA 7.35% at ≥1,000 flights).

---

## 7. End-to-end evaluation

There are 8 frozen cases: 3 structured-data and 5 private-knowledge questions. A case passes only if all of these pass:
- the skill
- the tool
- the arguments
- the stop reason
- no runtime errors
- the required facts appearing in the answer

Failures are classified by `evaluation/failure_analysis.py` into routing, tool selection, arguments, tool execution, guard, termination or answer failures.

---

## 8. Case study: the fuel-expense failure

The most useful result in the project was a **failure**:

> *According to Delta's 2025 10-K, what percentage of operating expense was fuel in 2025, 2024 and 2023?*

The trajectory looked healthy (the right skill, the knowledge tool called and completed), but the answer failed.

```text
end-to-end failure
  → the tool call succeeded, so look deeper
  → failure analysis: production registry still used the BASELINE retriever
    (the improved retriever existed only in the experiment)
  → integrate the improved retriever
  → new failure: schema rejected the cross-encoder's unbounded logit as "score"
  → keep the rerank score internal, expose the bounded FAISS score
  → full regression: 8/8, 0 classified failures
```

The recovered answer gave fuel as about 17.1%, 19.0% and 21.1% of operating expense for 2025, 2024 and 2023.

**Lessons:**
- An experimental improvement has no value until the production path uses it.
- A successful tool call does not mean a correct outcome.
- Every fix needs a full regression run, because fixes expose new contract problems.

Later, the refactor made the scores explicit: each result now carries `retrieval_type`, a FAISS `score` (`None` for neighbours) and a separate `rerank_score`.

---

## 9. Baselines across the refactor

The October 2026 refactor (see [`REFACTOR_JOURNEY.md`](REFACTOR_JOURNEY.md)) was judged against a baseline recorded before any change. A routing or retrieval regression blocked a step.

| Evaluation | Before refactor | After Steps 1–5 | After Steps 6–7 |
|---|---:|---:|---:|
| pytest | 52 | 141 | 173 |
| Skill routing | 15/15 | 15/15 | 15/15 |
| Interaction routing | 15/15 | 15/15 | (router unchanged) |
| Tool selection | 15/15 | 15/15 | 15/15 |
| Arguments | 7/7 | 7/7 | 7/7 |
| End-to-end | 8/8 | 8/8 | 8/8 |
| Retrieval, reranked (Hit@3 / MRR) | 90% / 0.750 | 90% / 0.750 | 90% / 0.750 |
| Flight analytics | — | — | 8/8 |

**How the paid runs were kept to one per step.** Whenever generated prompts or tool schemas changed, they were first compared byte-for-byte with a saved snapshot of the originals. The single paid run at the end of a step was then a confirmation, not a debugging session.

---

## 10. Software tests

`uv run pytest` runs 192 tests in about 3 seconds, with no API keys. CI runs the same suite on every push.

| Area | Examples |
|---|---|
| Agent loop | Token, cost and stage-timing totals per run, forced final answer at budget, repeated-call stop, invalid arguments returned to the model, web-before-private guard, follow-up rewriting, a failing progress listener not stopping the run |
| Tools and registry | Generated strict JSON, per-skill tool offers, write tool never offered, MCP error classification, in-process vs MCP transport |
| Data | Ranking, filters and calendar order on hand-built data; the DOT on-time figures on the real data |
| RAG | Chunk overlap, page-aware PDF ingestion (with a blank page), whole-word routing |
| API | Clean 500/503 errors without internals, question and history limits, SSE event order, feedback storage, startup warm-up switch, cache headers, 429 rate limits with `Retry-After`, `usage` in the response |
| Packaging | Dockerfile model names match `config.py`; `.dockerignore` excludes secrets |

---

## 11. Limitations

- **Small eval sets:** 8–15 cases per suite. A perfect score shows the designed behaviour holds on those cases, not that it generalises.
- **Model drift:** results depend on the model in `OPENAI_MODEL` and can drift with model versions. Re-run the paid suites after changing it.
- **Strict labels:** retrieval labels are strict. Answers built from other valid evidence may score as misses.
- **Narrow answer checks:** the end-to-end answer checks look for required facts; they don't judge the whole answer's quality or faithfulness.
- **Untested at scale:** there is no load, latency-under-concurrency or cost-regression testing.

**Next measurements:** a larger held-out question set, citation correctness and faithfulness scoring, latency and token budgets per question type (each run now records its tokens, cost and stage timings, so this is a matter of aggregating traces), and using the 👍/👎 feedback to find new failure cases.
