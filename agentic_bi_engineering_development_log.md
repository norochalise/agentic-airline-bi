# Agentic Business Intelligence --- Engineering Development Log

**Project:** Delta Air Lines Agentic Business Intelligence\
**Status:** In progress --- M0 through M13 completed; M14 retrieval
evaluation and retrieval improvement in progress\
**Environment:** Windows, PowerShell, Antigravity IDE, Python 3.13,
`uv`\
**Primary goal:** Learn agentic AI by building a portfolio-ready
business intelligence system that combines structured-data analysis,
private-document RAG, tool use, orchestration, reliability controls,
MCP, and evaluation.

> This is a living engineering document. It records what was built, why
> it was built, how it works, what failed, and what was learned. After
> the project is finished, it can be edited into a polished GitHub
> README, architecture document, portfolio case study, and interview
> reference.

------------------------------------------------------------------------

## 1. Project Vision

The project began as a practical learning system rather than a large
production platform. Delta Air Lines was chosen as the business domain
because it provides a useful mixture of:

-   structured operational flight data;
-   corporate reports;
-   customer-service policies;
-   a Contract of Carriage;
-   DOT aviation reports;
-   questions that require deterministic calculation;
-   questions that require evidence retrieval from documents.

The intended system is not merely a chatbot. It combines:

1.  an LLM/controller;
2.  deterministic Python tools;
3.  skill routing;
4.  structured state;
5.  private-document retrieval;
6.  local embeddings;
7.  FAISS vector search;
8.  reliability and safety guards;
9.  MCP interoperability;
10. systematic evaluation.

A simplified architecture is:

``` text
User Question
     |
     v
Skill Router
     |
     +----------------------+
     |                      |
     v                      v
Data Analysis          Knowledge Analysis
     |                      |
     v                      v
Python / CSV Tool      Local RAG Retrieval
     |                      |
     +----------+-----------+
                |
                v
          Agent Controller
                |
                v
       Evidence-grounded Answer
```

------------------------------------------------------------------------

## 2. Design Constraints

Several constraints shaped the project from the beginning.

### Small and testable data

The project deliberately avoids downloading many years of large aviation
datasets. The goal is to learn architecture and engineering, not to
maximize storage.

### Authoritative sources

Where possible, the corpus uses Delta, SEC/Delta investor materials,
DOT, and BTS data.

### Low API cost

Local computation is preferred whenever practical:

-   local Sentence Transformers embeddings;
-   local FAISS;
-   pandas for structured analysis;
-   local CrossEncoder reranking.

The LLM API is used where language reasoning or tool selection is
valuable rather than for work that deterministic/local code can perform.

### Learning-first implementation

Each milestone introduces one concept at a time. The system is
intentionally built incrementally so the reason for each component
remains understandable.

------------------------------------------------------------------------

## 3. Repository Structure

The repository has evolved during the project. Important areas currently
include:

``` text
agentic-business-intelligence/
|
|-- pyproject.toml
|-- evals/
|   |-- agent_cases.json
|   |-- retrieval_cases.json
|
|-- data/
|   |-- raw/
|   |   `-- delta_small_pack/
|   |       |-- documents/
|   |       `-- flights/
|   |
|   `-- processed/
|       `-- rag/
|
`-- src/
    `-- agentic_bi/
        |-- bi_agent_demo.py
        |-- mcp_server.py
        |-- mcp_client_demo.py
        |-- mcp_tools.py
        |
        |-- core/
        |   |-- agent.py
        |   |-- prompts.py
        |   |-- reliability.py
        |   `-- schemas.py
        |
        |-- skills/
        |   |-- router.py
        |   `-- registry.py
        |
        |-- tools/
        |   |-- registry.py
        |   |-- flight_analysis.py
        |   |-- knowledge_search.py
        |   |-- improved_knowledge_search.py
        |   `-- mock_actions.py
        |
        |-- rag/
        |   |-- loader.py
        |   |-- chunker.py
        |   |-- ingestion.py
        |   |-- embeddings.py
        |   |-- faiss_store.py
        |   |-- storage.py
        |   `-- reranker.py
        |
        `-- evaluation/
            |-- routing_eval.py
            |-- tool_selection_eval.py
            |-- argument_eval.py
            |-- retrieval_eval.py
            |-- build_retrieval_qrels.py
            `-- retrieval_failure_analysis.py
```

This is a development snapshot rather than a final frozen structure.

------------------------------------------------------------------------

# PART I --- FOUNDATION

## 4. M0 --- Plain LLM API Call

### Goal

Verify the environment and understand the most basic LLM
request/response flow before introducing tools or agents.

### What was learned

A model call by itself is not an agent. It receives input and returns
generated output. The later agent architecture adds tools, state, loops,
routing, budgets, and evidence.

### Outcome

A simple Python entry point successfully sent a question to the
configured OpenAI model and inspected the response, model information,
and usage.

------------------------------------------------------------------------

## 5. M1 --- Function Calling

### Goal

Understand the complete tool-call lifecycle:

``` text
User question
    |
    v
Model sees tool schema
    |
    v
Model chooses tool + JSON arguments
    |
    v
Python executes real function
    |
    v
Tool result returned using call ID
    |
    v
Model produces final answer
```

### First deterministic tools

Examples included:

-   `calculate_delay_rate`
-   `calculate_cancellation_rate`
-   `calculate_on_time_rate`

These functions validate their inputs and perform deterministic
calculations.

Example:

``` text
cancelled = 6
total = 120

cancellation rate = 5%
```

### Key lesson

The **Python function** performs the real computation.

The **tool definition/schema** explains to the LLM:

-   the tool name;
-   what it does;
-   what arguments it requires;
-   the type of each argument.

This separation became fundamental to the rest of the project.

------------------------------------------------------------------------

## 6. M2 --- Multiple Tools and Tool Registry

The project moved from one function to several tools.

The model could decide whether a question required:

-   delay rate;
-   cancellation rate;
-   on-time rate.

A registry/dispatcher pattern was introduced so execution did not depend
on large `if/elif` blocks.

Example tested results included:

``` text
18 delayed / 120 flights  -> 15%
6 cancelled / 120 flights -> 5%
170 on time / 200 flights -> 85%
```

### Lesson

Tool selection and tool execution are separate responsibilities.

------------------------------------------------------------------------

## 7. Packaging the Project

The repository was converted into an installable Python package using
`pyproject.toml`, a `src/` layout, Hatchling, and `uv`.

The working execution pattern became:

``` powershell
uv run python -m agentic_bi.<module>
```

from the project root.

This eliminated the need to repeatedly `cd src`.

------------------------------------------------------------------------

# PART II --- AGENT ORCHESTRATION

## 8. M3 --- Bounded Agent Loop

A real multi-step agent loop was introduced.

The agent can:

1.  receive a goal;
2.  select tools;
3.  execute one or more tool calls;
4.  return observations;
5.  continue reasoning;
6.  stop with a final answer.

Important limits were added:

``` text
MAX_STEPS = 5
MAX_TOOL_CALLS = 8
```

Example:

``` text
Goal: analyze 200 flights

30 delayed
10 cancelled
160 on time

Tool results:
delay       = 15%
cancellation = 5%
on-time      = 80%

Steps      = 2
Tool calls = 3
Stop reason = final_answer
```

### Lesson

An agent is not an infinite loop. Production-minded orchestration
requires explicit stopping conditions and budgets.

------------------------------------------------------------------------

## 9. M4 --- Guards and Failure Handling

Several protections were introduced.

### Repeat guard

An identical repeated tool call can be blocked.

### Budget guard

The agent stops when its configured step/tool budget is exhausted.

### Invalid-input propagation

Impossible business inputs such as:

``` text
120 delayed flights out of 100 total flights
```

produce a Python validation error instead of silently generating a
percentage.

The error can be returned to the model so it can explain the problem.

### Lesson

Reliability is part of agent design, not something to add only after
deployment.

------------------------------------------------------------------------

## 10. M5 --- Skill Routing

Two major skills were created:

``` text
data-analysis
knowledge-analysis
```

The router is deterministic and uses keywords and weighted phrases.

Examples:

``` text
"Which airports have the highest cancellation rate?"
    -> data-analysis

"What does the customer service plan say about cancellations?"
    -> knowledge-analysis
```

This separates **what type of work is required** from **which specific
tool should execute it**.

------------------------------------------------------------------------

# PART III --- PRIVATE KNOWLEDGE / RAG

## 11. Delta Small Data Pack

The project intentionally uses a compact corpus.

### Documents

``` text
delta_2025_form_10k.pdf
delta_domestic_contract_plain_language_2026-08-18.pdf
delta_customer_service_plan_2026-09-25.txt
dot_september_2026_atcr_july_data.pdf
```

### Structured data

``` text
delta_marketing_flights_2026_07.csv
```

The flight data represents July 2026 Delta-marketed domestic flights.

------------------------------------------------------------------------

## 12. M6 --- Document Loading, Chunking, and Ingestion

PDF loading was implemented with PyMuPDF, together with text loading and
chunking.

Page metadata was preserved for PDF evidence.

The corpus produced approximately 700 chunks:

``` text
Delta 2025 10-K          411
Customer Service Plan     20
Contract of Carriage     241
DOT ATCR                   28
-----------------------------
Total                     700
```

### Why chunk?

An LLM does not need the entire document corpus for every question.

Instead:

``` text
Documents
   |
   v
Chunks
   |
   v
Embeddings
   |
   v
Vector index
```

At question time, only relevant chunks are retrieved.

------------------------------------------------------------------------

## 13. M7 --- Local Embeddings and FAISS

Embedding model:

``` text
sentence-transformers/all-MiniLM-L6-v2
```

Embedding dimension:

``` text
384
```

Vector store:

``` text
FAISS
```

Both embedding generation and vector retrieval are local.

### RAG insight

Instead of feeding hundreds of pages to an LLM:

``` text
Question
   |
   v
Query embedding
   |
   v
FAISS similarity search
   |
   v
Small set of relevant chunks
   |
   v
LLM
```

This reduces context size and cost while grounding the answer in private
material.

------------------------------------------------------------------------

## 14. M8--M10 --- Knowledge Agent

A tool called:

``` text
search_private_knowledge
```

was connected to the agent.

It returns fields including:

``` text
source
page_number
chunk_id
score
text
```

The knowledge agent can therefore answer questions from Delta documents
and provide evidence-aware citations.

A refund-policy test successfully retrieved relevant Contract of
Carriage evidence.

------------------------------------------------------------------------

# PART IV --- STRUCTURED BUSINESS DATA

## 15. Structured Flight Analytics

The July 2026 CSV contains approximately 149,051 rows and 17 retained
columns, including:

``` text
FlightDate
Origin
Dest
DepDelayMinutes
ArrDelayMinutes
Cancelled
CancellationCode
Diverted
CarrierDelay
WeatherDelay
NASDelay
SecurityDelay
LateAircraftDelay
Distance
```

A deterministic tool was built:

``` python
analyze_top_origin_cancellation_rates(min_flights, top_n)
```

This uses pandas rather than asking the LLM to calculate statistics.

### Why?

The LLM should decide **what analysis is required**.

Python should perform the deterministic numerical computation.

------------------------------------------------------------------------

# PART V --- RELIABILITY AND SAFETY

## 16. M11 --- Pydantic Validation

Pydantic models validate tool arguments and structured output.

Examples include:

``` text
OriginCancellationAnalysisArgs
OriginCancellationResult
OriginCancellationAnalysisOutput
```

This catches invalid inputs before business logic executes and validates
outputs before the agent relies on them.

------------------------------------------------------------------------

## 17. Retry and Error Classification

`core/reliability.py` introduced categories such as:

``` text
TransientToolError
ToolTimeoutError
BusinessRuleError
PermanentToolError
```

`execute_with_retry()` implements bounded retries and exponential
backoff.

The project demonstrated:

-   transient failure -\> retry -\> success;
-   simulated timeout -\> retry -\> success;
-   `ValueError` -\> no retry.

### Important distinction

The implemented timeout behavior classifies timeout-style failures. It
is not yet a universal hard wall-clock process timeout.

------------------------------------------------------------------------

## 18. Read/Write Safety

A mock write tool demonstrated a critical agentic distinction:

``` text
READ TOOL
    -> normally safe to execute

WRITE TOOL
    -> may require approval
    -> requires stronger controls
```

A simulated customer-credit action demonstrated:

-   approval;
-   idempotency;
-   duplicate-action prevention.

The real Delta BI demonstration remains read-only.

------------------------------------------------------------------------

# PART VI --- MCP

## 19. M12 --- Model Context Protocol

MCP was added using:

``` powershell
uv add "mcp[cli]"
```

Components include:

``` text
mcp_server.py
mcp_client_demo.py
mcp_tools.py
```

### Architecture

``` text
BI Agent
   |
   v
MCP Adapter
   |
   v
MCP Client
   |
   v
MCP Server
   |
   v
Business Analysis Function
```

The MCP server exposes the cancellation-analysis capability with typed
input/output.

The client successfully:

1.  launched the server;
2.  discovered tools;
3.  called the tool;
4.  received structured content.

The main BI agent was then switched to the MCP-backed structured
analysis path.

### Lesson

MCP does not replace business logic. It standardizes how
capabilities/resources can be exposed and consumed.

------------------------------------------------------------------------

# PART VII --- ARCHITECTURE REFACTOR

## 20. Modularizing the Agent

The original BI agent became too large, so responsibilities were
separated.

### `core/agent.py`

Contains reusable orchestration:

``` python
run_agent(question: str, verbose: bool = False) -> AgentResult
```

`AgentResult` records:

``` text
goal
selected_skill
final_answer
stop_reason
step_count
tool_call_count
knowledge_search_count
data_analysis_count
tool_history
observations
errors
```

### `tools/registry.py`

Contains tool-related configuration such as:

``` text
TOOLS
FUNCTIONS
INPUT_SCHEMAS
OUTPUT_SCHEMAS
TOOL_POLICIES
```

### `core/prompts.py`

Contains prompt/instruction builders.

### `bi_agent_demo.py`

Became a small entry point instead of containing the whole system.

### Lesson

A working prototype is not necessarily maintainable architecture.
Refactoring after behavior becomes understood is valuable.

------------------------------------------------------------------------

# PART VIII --- M13 AGENT EVALUATION

## 21. Why Evaluation Was Added

Manual demonstrations answer:

> "Can the agent work?"

Evaluation answers:

> "How often does the expected behavior occur across a fixed set of
> cases?"

A frozen dataset was created:

``` text
evals/agent_cases.json
```

It eventually contained 15 cases spanning:

-   structured-data questions;
-   knowledge questions;
-   boundary/ambiguous questions.

------------------------------------------------------------------------

## 22. Routing Evaluation

The first expanded evaluation produced one failure.

Question:

``` text
What commitments does Delta make to customers when flights are disrupted?
```

It incorrectly routed to `data-analysis`.

The router registry was inspected. A targeted change added:

``` text
commitment
```

to knowledge keywords and removed the overly generic:

``` text
flight
```

from data keywords, while retaining the stronger phrase:

``` text
flight data
```

After the change:

``` text
Routing evaluation: 15/15 = 100%
```

This means 100% **on the current frozen evaluation set**, not universal
accuracy.

------------------------------------------------------------------------

## 23. Tool-Selection Evaluation

A second evaluator runs the actual agent and inspects `tool_history`.

Result:

``` text
15/15 = 100%
```

on the current evaluation set.

------------------------------------------------------------------------

## 24. Argument Evaluation

For cases with expected structured arguments, the evaluator compares the
model-generated tool arguments with the expected values.

Result:

``` text
7/7 = 100%
```

on the current evaluation set.

### M13 conclusion

M13 established three different behavioral layers:

``` text
Question
   |
   v
Correct skill?
   |
   v
Correct tool?
   |
   v
Correct arguments?
```

All three passed the current test set after the router correction.

------------------------------------------------------------------------

# PART IX --- M14 RETRIEVAL EVALUATION

## 25. Why Retrieval Needed Its Own Evaluation

A RAG answer can look plausible even when retrieval is weak.

Therefore M14 evaluates the retriever independently of final LLM answer
generation.

A manually verified 10-case dataset was created:

``` text
evals/retrieval_cases.json
```

Distribution:

``` text
Contract of Carriage       4
Customer Service Plan      3
Delta 2025 Form 10-K       2
DOT ATCR                    1
-----------------------------
Total                      10
```

The evaluation uses source-verified evidence.

------------------------------------------------------------------------

## 26. Locator Evaluation

The first evaluation checked whether retrieval reached the correct:

``` text
document + page/section
```

Results:

``` text
Hit@1 : 7/10  = 70%
Hit@3 : 10/10 = 100%
Hit@5 : 10/10 = 100%
MRR@5 : 0.850
```

At first glance this looked very strong.

However, this was intentionally labeled:

``` text
LOCATOR RETRIEVAL RESULTS
```

because being on the correct page does not guarantee that the returned
chunk actually contains the answer.

------------------------------------------------------------------------

## 27. Strict Answer-Bearing Qrels

Candidate chunks were inspected manually and answer-bearing chunk IDs
were frozen.

This created a stronger definition of relevance:

> A retrieved chunk must contain the evidence needed to answer the
> question, not merely originate from the correct page.

Strict results:

``` text
Hit@1 : 5/10 = 50%
Hit@3 : 8/10 = 80%
Hit@5 : 8/10 = 80%
MRR@5 : 0.650
```

This difference was one of the most important findings in the project.

### Lesson

``` text
Correct document
      !=
Correct page
      !=
Answer-bearing chunk
```

A retrieval system can look excellent under coarse metrics while still
fail to provide the LLM with the evidence it needs.

------------------------------------------------------------------------

## 28. Fragmented Evidence Case

One baggage-liability case exposed another issue.

The question requires both:

-   the general `$4,700` liability cap;
-   the assistive-device/wheelchair exception.

Those facts were split across adjacent chunks.

This means a single-chunk relevance metric cannot perfectly represent
the case.

The evaluation therefore needs to distinguish:

``` text
single answer-bearing evidence
```

from:

``` text
combined evidence across multiple chunks
```

This is an important future evaluation refinement.

------------------------------------------------------------------------

# PART X --- RETRIEVAL FAILURE ANALYSIS

## 29. Failure `retrieval_007`

Question concerned Complaint Resolution Officials (CROs) for customers
with disabilities and how to request one.

### Baseline behavior

FAISS retrieved:

``` text
rank 1 -> customer_service_plan:c11
```

Chunk `c11` begins the relevant passage and ends around:

``` text
"...Complaint Resolution Officials (CROs) in all airports who are
responsible for ensuring services are properly..."
```

The complete continuation is in:

``` text
customer_service_plan:c12
```

which states that CROs ensure services are properly implemented and that
a passenger may request one by contacting a Delta agent.

But `c12` ranked:

``` text
13
```

### Diagnosis

This is primarily a:

``` text
CHUNK-BOUNDARY + RANKING PROBLEM
```

FAISS found the correct semantic location, but the answer crossed from
one chunk into the next.

------------------------------------------------------------------------

## 30. Failure `retrieval_009`

Question asked for fuel costs as percentages of operating expense in:

``` text
2025
2024
2023
```

The correct chunk:

``` text
delta_2025_form_10k:p20:c4
```

contains:

``` text
17%
19%
21%
```

respectively.

But baseline FAISS ranked it:

``` text
7
```

A nearby fuel-related chunk `p20:c5` ranked higher even though it did
not contain the requested percentages.

### Diagnosis

This is primarily a:

``` text
RANKING PROBLEM
```

The evidence existed and was retrievable, but semantic similarity alone
did not rank the exact answer high enough for top-5 retrieval.

------------------------------------------------------------------------

# PART XI --- RETRIEVAL IMPROVEMENT EXPERIMENTS

## 31. Neighbor Expansion

A new experimental retriever was created:

``` text
src/agentic_bi/tools/improved_knowledge_search.py
```

The baseline retriever was deliberately preserved for comparison.

### Idea

When FAISS retrieves a chunk, also include adjacent chunks from the same
document:

``` text
FAISS finds c11
      |
      +--> c10
      +--> c11
      `--> c12
```

### Test result

For `retrieval_007`, baseline semantic search found:

``` text
semantic -> c11
```

Neighbor expansion then automatically added:

``` text
neighbor_previous -> c10
neighbor_next     -> c12
```

Therefore the answer-bearing `c12`, previously semantic rank 13, becomes
available in the final context because the system recognized that `c11`
may be part of a passage spanning a chunk boundary.

### Important evaluation caution

A neighbor chunk should not automatically be described as having a
normal FAISS rank.

We must distinguish:

``` text
ranked semantic retrieval
```

from:

``` text
expanded final context
```

Otherwise evaluation metrics can be accidentally inflated.

------------------------------------------------------------------------

## 32. Local CrossEncoder Reranker

A reranker was added:

``` text
src/agentic_bi/rag/reranker.py
```

Model:

``` text
cross-encoder/ms-marco-MiniLM-L6-v2
```

It runs locally.

### Why a CrossEncoder?

The embedding retriever independently embeds the query and documents and
uses vector similarity.

A CrossEncoder instead considers:

``` text
[question, candidate chunk]
```

together and assigns a relevance score.

This is slower than vector retrieval across the whole corpus, so it is
used only on a small candidate set.

The intended two-stage pattern is:

``` text
FAISS
  |
  | retrieve broad candidate set
  v
Top 15 candidates
  |
  v
CrossEncoder
  |
  | judge question/chunk relevance
  v
Top evidence
```

------------------------------------------------------------------------

## 33. Reranker Test Result

The known `retrieval_009` failure was used as a controlled test.

Before reranking:

``` text
Correct chunk p20:c4
FAISS rank = 7
```

After local CrossEncoder reranking:

``` text
Rank 1 -> delta_2025_form_10k:p20:c4
Rerank score = 3.7995
```

Observed reranked top results included:

``` text
1  p20:c4   RERANK 3.7995
2  p39:c1   RERANK 3.4368
3  p22:c6   RERANK 1.1938
4  p94:c2   RERANK 0.2734
5  p20:c5   RERANK -0.333
```

### Result

The exact answer-bearing chunk moved:

``` text
FAISS rank 7
     |
     v
Reranked rank 1
```

This validates the ranking diagnosis for this test case.

------------------------------------------------------------------------

# PART XII --- CURRENT RETRIEVAL ARCHITECTURE

## 34. Baseline

``` text
Question
   |
   v
MiniLM query embedding
   |
   v
FAISS
   |
   v
Top 5 chunks
```

Advantages:

-   fast;
-   local;
-   simple;
-   inexpensive.

Weaknesses observed:

-   chunk-boundary answers;
-   semantic near-matches may outrank exact answer evidence.

------------------------------------------------------------------------

## 35. Experimental Improved Architecture

The architecture currently being developed is:

``` text
Question
   |
   v
MiniLM embedding
   |
   v
FAISS top 15 candidates
   |
   v
CrossEncoder reranking
   |
   v
Best evidence candidates
   |
   v
Neighbor expansion
   |
   v
Final context
   |
   v
Knowledge agent
```

The two improvement components have been tested independently.

### Verified so far

**Neighbor expansion**

Solved the known context-fragmentation pattern for `retrieval_007` by
bringing `c12` alongside retrieved `c11`.

**Reranking**

Moved the known answer-bearing chunk for `retrieval_009` from FAISS rank
7 to reranked rank 1.

### NOT YET CLAIMED

We have **not yet completed the frozen 10-case evaluation of the
combined improved pipeline**.

Therefore we should not yet claim that the overall M14 metrics improved.

That comparison is the immediate next task.

------------------------------------------------------------------------

# PART XIII --- EVALUATION PHILOSOPHY LEARNED SO FAR

## 36. Freeze the Test Set Before Optimization

Once retrieval cases and qrels are manually verified, they should remain
stable while comparing retrieval methods.

Otherwise the benchmark can be unconsciously changed to fit the system.

------------------------------------------------------------------------

## 37. Measure Multiple Layers

The project now demonstrates why a single metric is insufficient.

### Agent behavior

``` text
Routing accuracy
Tool-selection accuracy
Argument accuracy
```

### Retrieval behavior

``` text
Locator Hit@K
Strict evidence Hit@K
MRR
Evidence/context coverage
```

### Future final-answer behavior

Possible later evaluation:

``` text
Groundedness
Citation correctness
Answer completeness
Business-rule correctness
```

------------------------------------------------------------------------

## 38. Failure Analysis Before Optimization

The project deliberately did not immediately replace MiniLM after seeing
an 80% strict Hit@5.

Instead:

``` text
Measure
   |
   v
Identify failed cases
   |
   v
Retrieve deeper
   |
   v
Inspect exact chunks
   |
   v
Classify failure
   |
   v
Choose targeted improvement
```

This produced two concrete diagnoses:

``` text
retrieval_007 -> chunk boundary / neighbor problem
retrieval_009 -> ranking problem
```

Only then were neighbor expansion and reranking introduced.

This is a stronger engineering process than blindly adding more
sophisticated components.

------------------------------------------------------------------------

# PART XIV --- IMPORTANT ENGINEERING DECISIONS

## 39. Why Local Embeddings?

-   zero embedding API cost after local model download;
-   fast enough for this small corpus;
-   private documents remain local;
-   easy to reproduce.

------------------------------------------------------------------------

## 40. Why FAISS?

The corpus is small, local, and experimental.

A hosted vector database would add infrastructure without currently
solving an important project problem.

FAISS is sufficient for learning and evaluation.

------------------------------------------------------------------------

## 41. Why Deterministic Data Tools?

Questions such as cancellation rate should not depend on an LLM
performing arithmetic over raw rows.

The architecture is:

``` text
LLM -> decide analysis/tool
Python/pandas -> compute
LLM -> explain result
```

------------------------------------------------------------------------

## 42. Why Keep Baseline Retrieval?

`search_private_knowledge()` remains useful even after improved
retrieval exists.

It provides a reproducible baseline.

Without the baseline we could say:

> "The new retriever works."

With a frozen baseline and evaluation we can eventually say:

> "This specific retrieval change changed these measured metrics on the
> same verified cases."

The second statement is much stronger.

------------------------------------------------------------------------

# PART XV --- IMPORTANT COMMANDS

## 43. Run the Main BI Agent

``` powershell
uv run python -m agentic_bi.bi_agent_demo
```

------------------------------------------------------------------------

## 44. Run Routing Evaluation

``` powershell
uv run python -m agentic_bi.evaluation.routing_eval
```

------------------------------------------------------------------------

## 45. Run Tool-Selection Evaluation

``` powershell
uv run python -m agentic_bi.evaluation.tool_selection_eval
```

------------------------------------------------------------------------

## 46. Run Argument Evaluation

``` powershell
uv run python -m agentic_bi.evaluation.argument_eval
```

------------------------------------------------------------------------

## 47. Run Retrieval Evaluation

``` powershell
uv run python -m agentic_bi.evaluation.retrieval_eval
```

------------------------------------------------------------------------

## 48. Generate Qrel Candidates

``` powershell
uv run python -m agentic_bi.evaluation.build_retrieval_qrels > qrel_candidates.txt
```

------------------------------------------------------------------------

## 49. Retrieval Failure Analysis

``` powershell
uv run python -m agentic_bi.evaluation.retrieval_failure_analysis > retrieval_failure_analysis.txt
```

------------------------------------------------------------------------

# PART XVI --- CURRENT MEASURED RESULTS

## 50. Agent Evaluation --- M13

On the current frozen development evaluation set:

  Evaluation                      Result
  --------------------- ----------------
  Skill routing           15/15 --- 100%
  Tool selection          15/15 --- 100%
  Argument extraction       7/7 --- 100%

These results apply only to the current evaluation set.

------------------------------------------------------------------------

## 51. Retrieval Baseline --- M14

### Locator metrics

  Metric             Result
  -------- ----------------
  Hit@1        7/10 --- 70%
  Hit@3      10/10 --- 100%
  Hit@5      10/10 --- 100%
  MRR@5               0.850

### Strict answer-bearing metrics

  Metric           Result
  -------- --------------
  Hit@1      5/10 --- 50%
  Hit@3      8/10 --- 80%
  Hit@5      8/10 --- 80%
  MRR@5             0.650

The difference between these tables is a core project finding.

------------------------------------------------------------------------

# PART XVII --- WHAT REMAINS

## 52. Immediate M14 Next Step

Combine the tested improvements:

``` text
FAISS top 15
   |
   v
CrossEncoder reranking
   |
   v
Top candidates
   |
   v
Neighbor expansion
```

Then evaluate all 10 frozen retrieval questions.

The comparison should clearly separate:

1.  baseline semantic retrieval;
2.  reranked retrieval;
3.  final context coverage after neighbor expansion.

Do not mix neighbor-expanded chunks with ordinary ranked retrieval
metrics unless the metric definition explicitly supports that.

------------------------------------------------------------------------

## 53. M15 --- Agent Evaluation

Extend evaluation beyond routing/tool/argument checks into broader
end-to-end agent behavior.

Potential dimensions include:

-   correct skill;
-   correct tool;
-   valid arguments;
-   grounded final answer;
-   appropriate citation/evidence use;
-   stop behavior;
-   tool-budget behavior.

------------------------------------------------------------------------

## 54. M16 --- Failure Analysis

Create a structured failure taxonomy rather than merely recording
pass/fail.

Examples:

``` text
routing failure
tool-selection failure
argument failure
retrieval failure
chunk-boundary failure
ranking failure
tool execution failure
grounding failure
citation failure
```

------------------------------------------------------------------------

## 55. M17 --- Observability and Checkpoint/Resume

Improve traceability of:

``` text
goal
selected skill
steps
tool calls
arguments
observations
errors
latency
stop reason
```

Checkpoint/resume can later demonstrate durable agent state.

------------------------------------------------------------------------

## 56. M18 --- FastAPI

Expose the BI agent through an API layer after the internal architecture
and evaluation are stable.

The API should be a thin interface over the reusable `run_agent()`
architecture rather than duplicating agent logic.

------------------------------------------------------------------------

## 57. M19 --- pytest

Convert important behavior into automated tests.

Likely test targets:

-   deterministic calculation functions;
-   Pydantic validation;
-   routing;
-   guards;
-   retry policy;
-   duplicate prevention;
-   retrieval helpers;
-   API behavior.

------------------------------------------------------------------------

## 58. M20 --- Final GitHub and Portfolio Documentation

Only after the implementation is stable should this engineering log be
converted into polished public documentation.

Possible final artifacts:

``` text
README.md
ARCHITECTURE.md
EVALUATION.md
portfolio case study
architecture diagram
demo screenshots
interview talking points
```

The final documentation should emphasize measured engineering decisions
rather than simply listing technologies.

------------------------------------------------------------------------

# PART XVIII --- PROJECT STORY SO FAR

The project has progressed through a meaningful sequence:

``` text
Plain LLM call
      |
      v
Function calling
      |
      v
Multiple tools
      |
      v
Bounded agent loop
      |
      v
Guards and validation
      |
      v
Skill routing
      |
      +-----------------------+
      |                       |
      v                       v
Structured Data          Private Documents
pandas tools             loaders/chunks
      |                       |
      |                   MiniLM + FAISS
      |                       |
      +-----------+-----------+
                  |
                  v
             Unified BI Agent
                  |
                  v
        Reliability / Safety
                  |
                  v
                 MCP
                  |
                  v
        Modular Architecture
                  |
                  v
          Behavioral Evaluation
                  |
                  v
        Retrieval Evaluation
                  |
                  v
          Failure Analysis
                  |
            +-----+-----+
            |           |
            v           v
       Neighbor      Reranking
       Expansion
            |           |
            +-----+-----+
                  |
                  v
          CURRENT POSITION
```

------------------------------------------------------------------------

# PART XIX --- CORE LESSONS

1.  **An LLM with a prompt is not an agent.** Agent behavior comes from
    orchestration, tools, state, limits, and feedback loops.

2.  **Tool schemas and Python functions have different jobs.** The
    schema communicates capability to the model; Python executes the
    real business logic.

3.  **Use deterministic computation for deterministic business
    questions.**

4.  **RAG is not just embeddings.** Loading, chunking, metadata,
    retrieval, ranking, context construction, citations, and evaluation
    all matter.

5.  **Correct-document retrieval can hide incorrect evidence
    retrieval.**

6.  **Chunk boundaries are an engineering decision with measurable
    consequences.**

7.  **Dense retrieval is excellent for candidate generation but does not
    always provide the best final ranking.**

8.  **A reranker can improve precision without replacing the fast
    vector-search stage.**

9.  **Evaluation should be frozen before optimization.**

10. **Failure analysis should guide architectural changes.**

11. **Reliability controls belong inside the agent architecture.**

12. **Local models can meaningfully reduce API cost while preserving a
    strong learning architecture.**

13. **MCP exposes capabilities; it does not replace the underlying
    business functions.**

14. **Modularization becomes important once a prototype grows beyond a
    demonstration script.**

15. **Measured failures are valuable.** The M14 drop from coarse locator
    metrics to strict evidence metrics produced some of the most useful
    engineering insights in the project.

------------------------------------------------------------------------

# PART XX --- LIVING STATUS

## Completed / substantially completed

``` text
M0  Plain API
M1  Function calling
M2  Multi-tool selection/registry
M3  Bounded agent loop
M4  Guards
M5  Skill routing
M6  Document ingestion
M7  Local embeddings + FAISS
M8–M10 Knowledge/RAG integration
M11 Reliability, validation, data path, safety
M12 MCP
M13 Agent evaluation
```

## In progress

``` text
M14 Retrieval evaluation and improvement
```

Current M14 work has completed:

``` text
verified retrieval cases
locator evaluation
strict evidence evaluation
manual/frozen evidence labels
failure analysis
neighbor-expansion experiment
CrossEncoder reranking experiment
```

Still required before M14 is considered finished:

``` text
combine improved retrieval pipeline
run frozen 10-case comparison
analyze regressions/improvements
finalize M14 results
```

## Remaining later milestones

``` text
M15 Agent evaluation expansion
M16 Failure analysis framework
M17 Observability + checkpoint/resume
M18 FastAPI
M19 pytest
M20 Final GitHub documentation
```

------------------------------------------------------------------------

## Final Note

This document intentionally records the development process, including
failures and intermediate results. It should **not** be treated as the
final public README.

After the project is complete, we should revisit it and:

-   verify file names and final repository structure;
-   update final evaluation numbers;
-   remove obsolete experiments;
-   add final architecture diagrams;
-   select the strongest technical story;
-   convert implementation history into concise public documentation;
-   add reproducible setup/run instructions;
-   document limitations honestly.

Until then, this file should remain the project's **engineering
memory**.
