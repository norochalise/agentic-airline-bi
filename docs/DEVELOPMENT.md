# Development Story

## 1. Purpose

This document records how Agentic Business Intelligence evolved from a single model call into a bounded, evaluated, observable application.

It serves a different purpose from the other project documentation:

- `README.md` presents the finished portfolio project.
- `ARCHITECTURE.md` explains the current system design.
- `EVALUATION.md` explains how behavior is measured.
- `DEVELOPMENT.md` explains **why the architecture became what it is**.

The project was built incrementally so that each new layer solved a concrete problem exposed by the previous stage.

---

# 2. Project Goal

The project began as a practical attempt to move from understanding individual AI concepts to being able to:

```text
design
implement
debug
evaluate
refactor
test
expose
and explain
```

a complete agentic AI system.

Delta Air Lines was selected as the working domain because it provided two useful information types within one coherent business setting:

1. structured flight-performance data;
2. policy, service, regulatory, and financial documents.

This allowed the project to explore an important architectural question:

> **How should one agent handle questions that require fundamentally different kinds of work?**

The answer became the core architecture:

```text
structured question
→ deterministic computation

knowledge question
→ grounded retrieval
```

with the LLM coordinating rather than replacing those capabilities.

---

# 3. Development Timeline

```mermaid
flowchart LR
    M0["M0<br/>Plain API"]
    --> M1["M1–M2<br/>Tool Calling"]

    M1 --> M3["M3–M4<br/>Agent Loop + Guards"]

    M3 --> M5["M5<br/>Skill Routing"]

    M5 --> M6["M6–M10<br/>RAG + Data"]

    M6 --> M11["M11<br/>Reliability"]

    M11 --> M12["M12<br/>MCP"]

    M12 --> M13["M13–M16<br/>Evaluation"]

    M13 --> M17["M17<br/>Observability"]

    M17 --> M18["M18<br/>FastAPI"]

    M18 --> M19["M19<br/>pytest"]

    M19 --> M20["M20<br/>Documentation"]

    M20 --> M21["M21<br/>Web Interface"]
```

The milestone numbers describe the learning/build sequence, not separate products.

---

# 4. M0 — Start With One Model Call

The first milestone intentionally did almost nothing.

One question was sent to the model.

The response object, model information, output text, and usage were inspected.

There was:

```text
no tool calling
no agent loop
no RAG
no MCP
no API service
no frontend
```

### Why start this small?

Before building an agent, it was useful to understand the smallest observable model interaction.

### Lesson

> **Complex systems are easier to understand when each layer is added deliberately.**

---

# 5. M1–M2 — Function Calling

The next step introduced ordinary Python business functions.

Early examples included:

```text
calculate_delay_rate
calculate_cancellation_rate
calculate_on_time_rate
```

The interaction became:

```text
User Question
      ↓
Model
      ↓
Tool Selection + JSON Arguments
      ↓
Python Function
      ↓
Tool Result
      ↓
Model
      ↓
Final Explanation
```

This established one of the project's foundational concepts.

A tool has two related but different sides:

```text
Model-facing schema
→ tells the model what capability exists

Python function
→ performs the actual work
```

### Lesson

> **The model requests a capability. Python executes it.**

Tool calling is not the same thing as giving the model the implementation.

---

# 6. M3 — From Tool Calling to an Agent Loop

A single function call demonstrated tool use, but not robust agent behavior.

A reusable bounded loop was introduced so the model could:

1. inspect the goal;
2. request a tool;
3. receive an observation;
4. decide whether more work was required;
5. eventually terminate with an answer.

The loop introduced explicit limits such as:

```text
MAX_STEPS
MAX_TOOL_CALLS
```

### Lesson

> **An LLM that can call a function is not automatically a reliable agent.**

Agent behavior requires orchestration, state, observations, and termination rules.

---

# 7. M4 — Guards and Bounded Autonomy

Once a loop existed, failure modes became possible.

For example:

```text
call same tool repeatedly
exceed useful tool budget
continue after invalid input
fail to terminate
```

The project added:

- repeated-call protection;
- tool-budget enforcement;
- invalid-input handling;
- explicit stop reasons.

### Lesson

> **Autonomy should be bounded in code, not only requested in a prompt.**

This principle remained throughout the rest of the project.

---

# 8. M5 — Skill Routing

The project now needed to distinguish two different workloads:

```text
data-analysis
knowledge-analysis
```

A deterministic skill router was introduced.

Instead of using another LLM call, it uses keyword and phrase scoring.

Conceptually:

```text
Question
   ↓
Deterministic Router
   ├── data-analysis
   ├── knowledge-analysis
   └── None
```

### Why deterministic?

At the current scale there are only two skills.

The deterministic approach is:

```text
cheap
inspectable
testable
reproducible
```

### Lesson

> **Not every decision in an AI system needs another model call.**

---

# 9. M6–M10 — Building the Private Knowledge Path

The knowledge-analysis path required a complete RAG pipeline.

Development progressed through:

```text
document loading
      ↓
chunking
      ↓
metadata preservation
      ↓
embedding
      ↓
vector indexing
      ↓
semantic retrieval
      ↓
agent tool integration
      ↓
grounded answer generation
```

The corpus contained:

- Delta 2025 Form 10-K;
- Delta Domestic Contract of Carriage;
- Delta Customer Service Plan;
- one 2026 U.S. DOT Air Travel Consumer Report.

Approximately:

```text
700 chunks
```

were produced with source/page metadata.

---

# 10. Local Embeddings

The embedding model selected was:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Embeddings were generated locally.

### Why?

For a corpus of approximately 700 chunks:

- local inference was practical;
- recurring embedding API cost was unnecessary;
- experimentation was fast;
- the architecture still demonstrated real vector retrieval.

### Lesson

> **Infrastructure should match the actual scale of the problem.**

---

# 11. FAISS

FAISS was used as the local vector index.

At this project scale, a hosted vector database would have introduced additional infrastructure without solving a current problem.

### Lesson

> **A production-minded design does not mean selecting the largest possible infrastructure stack.**

It means selecting infrastructure appropriate to the requirement and understanding when that choice would need to change.

---

# 12. Structured Business Data Path

Alongside RAG, the project added a real structured-data capability over a July 2026 Delta-marketed domestic flight CSV.

The main analysis tool calculates top origin-airport cancellation rates.

Instead of sending raw rows to the model:

```text
CSV
 ↓
pandas
 ↓
deterministic calculation
 ↓
structured result
 ↓
LLM explanation
```

### Lesson

> **Use deterministic computation for deterministic business questions.**

The LLM should not approximate a metric that Python can calculate exactly.

---

# 13. RAG Became a Pipeline, Not a Feature

The project initially made embedding and vector search concrete.

But retrieval evaluation later showed that RAG quality depends on much more than embeddings.

The full pipeline became:

```text
load
 ↓
chunk
 ↓
preserve metadata
 ↓
embed
 ↓
index
 ↓
retrieve
 ↓
rerank
 ↓
construct context
 ↓
answer
 ↓
cite
 ↓
evaluate
```

### Lesson

> **RAG is a system pipeline, not an embedding call.**

---

# 14. M11 — Reliability

Once tools were doing real work, the next question became:

> What happens when a capability fails?

Pydantic models were introduced for structured inputs and outputs.

The reliability layer added:

- error classification;
- bounded retry;
- exponential backoff;
- tool-specific retry policies.

Representative categories include:

```text
TransientToolError
ToolTimeoutError
BusinessRuleError
PermanentToolError
```

The architecture distinguishes:

```text
failure may succeed on another attempt
→ potentially retry

failure cannot be fixed by trying again
→ do not blindly retry
```

### Lesson

> **Retry is a policy decision, not a generic exception handler.**

---

# 15. Read / Write Safety

The main BI workflow remained read-only.

A separate mock consequential action was introduced to explore how an agent should interact with write capabilities.

The experiment demonstrated:

```text
read/write classification
approval requirement
duplicate/idempotency protection
```

Later, approval-policy enforcement was promoted into reusable production code:

```text
core/action_guard.py
```

The guard checks the access policy before executing the protected function.

### Lesson

> **Consequential capabilities require a stronger execution boundary than read-only analysis.**

No real Delta write capability is connected.

---

# 16. M12 — MCP

The structured flight-analysis capability was then exposed through Model Context Protocol.

The architecture became:

```text
Business Function
      ↓
MCP Server
      ↓
MCP Client / Adapter
      ↓
Tool Registry
      ↓
Agent
```

The important insight was what MCP **did not** replace.

It did not replace:

```text
business logic
validation
agent orchestration
reliability policy
```

It standardized capability exposure.

### Lesson

> **MCP is a protocol boundary, not business logic.**

---

# 17. Architecture Refactor

As the original learning scripts accumulated responsibilities, the architecture was refactored.

Responsibilities moved into modules such as:

```text
core/agent.py
core/prompts.py
core/state.py
core/reliability.py
tools/registry.py
skills/router.py
rag/
evaluation/
```

The reusable entry point became:

```python
run_agent(
    question: str,
    verbose: bool = False,
) -> AgentResult
```

### Lesson

> **A prototype can work correctly and still need refactoring.**

The right time to refactor was after the behavior had become understood.

---

# 18. M13 — Evaluation Begins

Until this point, much of the system had been verified through manual examples.

M13 introduced frozen evaluation cases.

Three agent behaviors were measured separately:

```text
skill routing
tool selection
argument extraction
```

Results on the frozen M13 development set:

```text
Skill routing:               15/15
Tool selection:              15/15
Structured arguments:         7/7
```

A routing failure produced a targeted router adjustment rather than a broad rewrite.

### Lesson

> **Evaluation converts confidence into inspectable evidence.**

---

# 19. M14 — Retrieval Evaluation

Retrieval was then evaluated independently from generation.

This revealed a subtle problem.

A retriever could find:

```text
the correct document
```

or even:

```text
the correct semantic neighborhood
```

without ranking:

```text
the exact answer-bearing evidence
```

highly enough.

Baseline results on the frozen 10-case development set:

```text
Hit@1: 50%
Hit@3: 70%
Hit@5: 70%
MRR@5: 0.600
```

This established a measurable baseline.

---

# 20. CrossEncoder Reranking

The retrieval pipeline was upgraded:

```text
FAISS top 15 candidates
        ↓
CrossEncoder reranking
        ↓
top 5 ranked evidence
```

Model:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

Results became:

```text
Hit@1: 60%
Hit@3: 90%
Hit@5: 90%
MRR@5: 0.750
```

On the frozen set, reranking improved the placement of answer-bearing evidence.

### Lesson

> **Dense retrieval can be strong candidate generation without being the best final ranking mechanism.**

---

# 21. Neighbor Expansion

One remaining issue involved evidence split across chunk boundaries.

Neighbor expansion was added after reranking.

This produced:

```text
Expanded-context evidence coverage:
10/10
```

One case was explicitly identified as fragmented evidence.

Crucially, expanded neighbors were **not** assigned artificial retrieval ranks.

### Lesson

> **Ranking and context construction are different stages and should be measured differently.**

---

# 22. M15 — End-to-End Evaluation

Component-level evaluation was useful, but users interact with the complete system.

An 8-case frozen end-to-end set was created:

```text
3 structured-data cases
5 private-knowledge cases
```

The evaluator checks:

```text
skill
tool
arguments
stop reason
runtime errors
answer requirements
full-case pass
```

The final regression reached:

```text
8/8
```

on the current frozen set.

### Lesson

> **Component metrics and end-to-end behavior are complementary.**

Neither replaces the other.

---

# 23. M16 — Failure Analysis

A simple pass/fail result does not explain what broke.

M16 introduced structured failure categories:

```text
routing_failure
tool_selection_failure
argument_failure
tool_execution_failure
guard_triggered
termination_failure
answer_failure
```

This became especially valuable for one 10-K question.

---

# 24. The Most Important Failure

The question asked:

> According to Delta's 2025 10-K, what percentage of operating expense was fuel in 2025, 2024, and 2023?

The agent failed.

At first glance, the trajectory looked healthy:

```text
correct skill
      ↓
knowledge tool called
      ↓
tool completed
```

But the final answer still failed.

That became one of the most valuable engineering moments in the project.

---

# 25. Failure Analysis Found an Integration Gap

Investigation revealed:

```text
M14
→ improved retriever developed

but

production registry
→ still using baseline retriever
```

The experiment and the production path had diverged.

The registry was updated to use the improved retrieval implementation.

### Lesson

> **An experimental improvement has no production value until the real execution path uses it.**

---

# 26. The Fix Exposed Another Failure

After integrating the improved retriever, a new validation problem appeared.

The CrossEncoder produced raw ranking scores.

The existing external schema expected a bounded score.

Conceptually:

```text
CrossEncoder ranking logit
        ≠
normalized similarity score
```

The adapter was corrected so:

```text
CrossEncoder score
→ remains internal for ranking

bounded FAISS score
→ exposed through external contract
```

After the fix:

```text
M15 regression: 8/8
classified failures: 0
```

The recovered fuel-expense answer contained approximately:

```text
2025: 17.1%
2024: 19.0%
2023: 21.1%
```

### Lesson

> **Integration fixes can expose new interface-contract problems. Regression must follow every meaningful fix.**

---

# 27. M17 — Observability

Console output was useful during early development, but it was not enough for inspecting complete runs.

Structured tracing was introduced.

Events include:

```text
agent_started
skill_selected
tool_started
tool_completed
checkpoint_saved
agent_finished
```

Trace metadata includes:

```text
run ID
timestamps
tool duration
event payloads
stop reason
total duration
```

Traces are persisted as JSON.

### Lesson

> **If agent behavior matters, execution should be inspectable after the terminal output disappears.**

---

# 28. M17 — Checkpointing

The project also introduced application-state checkpoints.

Snapshots are stored:

```text
after successful tool observations
and
at final termination
```

A checkpoint can be loaded and converted back into `AgentState`.

The scope was deliberately limited.

The system provides:

```text
application-state restoration
```

not:

```text
full durable recovery of an interrupted
external model conversation
```

### Lesson

> **A system should describe its recovery guarantees precisely.**

Calling application-state persistence "full crash recovery" would overstate the implementation.

---

# 29. M18 — FastAPI

Once `run_agent()` was reusable, it was exposed through a thin FastAPI layer.

Endpoints:

```text
GET  /health
POST /ask
```

Pydantic validates incoming requests.

The API translates:

```text
AskRequest
   ↓
run_agent()
   ↓
AgentResult
   ↓
AskResponse
```

Swagger/OpenAPI documentation is automatically available.

### Lesson

> **FastAPI did not make the agent more intelligent. It made the capability accessible as a service.**

Keeping the API thin preserved the reusable core architecture.

---

# 30. M19 — Deterministic Software Testing

The project now had AI evaluations, but it also needed fast regression tests for ordinary software contracts.

pytest was added.

Initial coverage included:

```text
router
API schemas
API endpoints
reliability
checkpointing
observability
```

The first mature suite reached:

```text
16 passed
```

API tests mocked the real agent so routine regression did not consume model credits.

A Windows temporary-directory permission problem was solved by configuring a repository-local pytest base temp directory.

### Lesson

> **AI evaluation and software regression testing solve different problems.**

```text
Evaluation
→ Is AI/retrieval behavior as expected?

pytest
→ Did deterministic software behavior break?
```

---

# 31. Productionizing the Action Guard

During the final architecture review, the earlier write-safety demonstration was promoted into reusable code:

```text
core/action_guard.py
```

Tests were added for:

```text
read action without approval
write action requiring approval
approved write execution
blocked unapproved execution
unknown tool rejection
```

All five passed.

This moved an important safety concept from a learning demo into a tested architectural component.

---

# 32. M20 — Documentation

The next milestone was not another AI feature.

It was documentation.

The goal was to turn the implementation history into a coherent engineering story.

The public documentation was separated into:

```text
README.md
→ portfolio landing page

ARCHITECTURE.md
→ technical design

EVALUATION.md
→ measurement and evidence

DEVELOPMENT.md
→ engineering progression
```

The documentation deliberately emphasizes:

```text
why decisions were made
what was measured
what failed
what changed
what remains limited
```

rather than presenting the repository as a collection of technologies.

### Lesson

> **A portfolio project is stronger when another engineer can understand the decisions, not merely see the dependencies.**

---

# 33. Final Repository Cleanup

Before adding the user interface, the repository was reviewed as a finished engineering package.

Development-only demo scripts were removed from the production package.

Obsolete early files were also removed.

Offline index-building utilities were moved into:

```text
scripts/
```

MCP functionality was reorganized into:

```text
src/agentic_bi/mcp/
├── server.py
└── tools.py
```

The real MCP subprocess path was smoke-tested after the move.

The production package now reflects responsibilities rather than the chronological order in which experiments were created.

### Lesson

> **Learning artifacts and publication artifacts do not need to have the same structure.**

Experiments were useful while learning. They did not all need to remain in the final runtime package.

---

# 34. M21 — Web Interface

The final application milestone added a browser interface.

A deliberately lightweight stack was chosen:

```text
HTML
CSS
JavaScript
```

served by the existing FastAPI application.

No separate frontend framework or second development server was required.

The architecture became:

```text
Browser
   ↓
JavaScript
   ↓
POST /ask
   ↓
FastAPI
   ↓
run_agent()
   ↓
Skill Router
   ↓
Tools / MCP / RAG
   ↓
AgentResult
   ↓
AskResponse
   ↓
Browser
```

### Why this approach?

The frontend had one primary job:

> Make the existing engineering system easy to demonstrate.

Introducing a large frontend framework would not have improved the core AI engineering story.

---

# 35. Frontend Observability

The interface does more than display the answer.

It also exposes:

```text
selected skill
stop reason
step count
tool-call count
knowledge-search count
data-analysis count
error count
run ID
```

This aligns the presentation layer with the project's broader observability philosophy.

The user can see not only:

```text
what did the agent answer?
```

but also part of:

```text
how did the agent execute?
```

---

# 36. Frontend Integration Failure

The first frontend integration exposed a useful interface mismatch.

The API initially attempted to access:

```text
result.answer
result.state.*
```

but the real `AgentResult` contract contained:

```text
result.final_answer
result.step_count
result.tool_call_count
result.errors
...
```

The browser loaded successfully, but:

```text
POST /ask
→ HTTP 500
```

Inspection of the actual `AgentResult` dataclass identified the mismatch.

`api/app.py` was corrected to map the real contract.

The next real browser request completed successfully.

### Lesson

> **Integration code should follow the actual interface contract, not an assumed representation.**

This was a small failure, but it reinforced the same principle discovered earlier during retrieval integration.

---

# 37. Frontend Testing

The existing API regression tests were extended.

New tests verify:

```text
GET /
→ HTML loads

GET /static/styles.css
→ stylesheet loads

GET /static/app.js
→ JavaScript loads and references /ask
```

The existing mocked `/ask` test remains isolated from the real model.

The complete deterministic suite now reports:

```text
24 passed
```

This includes the earlier action-guard tests and the new frontend coverage.

### Lesson

> **A presentation layer becomes part of the application contract once users depend on it.**

It should therefore participate in regression testing.

---

# 38. Final System

The project that began as:

```text
question
   ↓
model
   ↓
text
```

became:

```text
Browser / API Client
        ↓
FastAPI
        ↓
Pydantic Validation
        ↓
Bounded Agent Controller
        ↓
Deterministic Skill Router
        ↓
Tool Registry
   ┌────┴─────┐
   ↓          ↓
MCP/Data     RAG
   ↓          ↓
pandas      MiniLM
             ↓
            FAISS
             ↓
         CrossEncoder
             ↓
      Context Expansion
   └────┬─────┘
        ↓
Validated Observation
        ↓
Final Answer
        ↓
Structured Response
        ↓
Browser

Cross-cutting:
validation
reliability
guards
state
tracing
checkpointing
evaluation
pytest
```

The most important change was not the number of components.

It was that each component eventually acquired a clear responsibility.

---

# 39. Major Engineering Decisions

## Local embeddings instead of an embedding API

Reason:

- approximately 700 chunks;
- lower recurring cost;
- fast experimentation;
- sufficient local performance;
- preserves real vector-retrieval architecture.

---

## FAISS instead of hosted vector infrastructure

Reason:

- small corpus;
- easy local reproducibility;
- minimal infrastructure overhead.

A hosted service becomes useful when scale, collaboration, persistence, filtering, or operational requirements justify it.

---

## Deterministic skill router

Reason:

- two current skills;
- inspectable rules;
- no additional model cost;
- straightforward evaluation.

---

## pandas for structured calculations

Reason:

- cancellation-rate analysis is deterministic;
- calculations should be reproducible;
- model reasoning is unnecessary for arithmetic over known rows.

---

## CrossEncoder reranking

Reason:

FAISS semantic similarity provided useful candidates but did not always rank exact answer-bearing evidence highly enough.

---

## Neighbor expansion

Reason:

Evidence can cross chunk boundaries.

Expansion improves final context while remaining separate from ranked retrieval metrics.

---

## MCP as a thin capability boundary

Reason:

The protocol should expose the business capability, not become the business implementation.

---

## FastAPI as a thin service boundary

Reason:

The interface should expose `run_agent()` without duplicating orchestration logic.

---

## Plain frontend instead of a large frontend framework

Reason:

The portfolio needed a clean interactive demonstration, not a second complex application architecture.

---

## Frozen development evaluation sets

Reason:

Before/after comparisons require stable cases.

The small sets are intentionally described as development/regression evidence rather than production benchmarks.

---

# 40. What the Project Demonstrates

The completed system demonstrates practical implementation of:

```text
LLM API interaction
tool / function calling
bounded agent loops
explicit agent state
skill routing
tool registries
structured validation
deterministic pandas analysis
private-document RAG
local embeddings
FAISS retrieval
CrossEncoder reranking
context expansion
MCP
selective retry
error classification
read/write safety
approval guards
failure analysis
observability
checkpointing
FastAPI
browser integration
pytest
evaluation-driven iteration
repository refactoring
technical documentation
```

But the value of the project is **not** the number of technologies.

The value is that each component exists for a reason and participates in an understandable system.

---

# 41. Known Boundaries

The finished project remains a focused portfolio system rather than a production airline platform.

It does not currently provide:

- enterprise authentication/RBAC;
- distributed workers;
- hosted scalable vector infrastructure;
- production monitoring-platform integration;
- complete durable model-conversation recovery;
- broad arbitrary BI analysis over every possible CSV question;
- real consequential airline write actions;
- large held-out evaluation sets;
- sophisticated multi-agent orchestration;
- production traffic/load validation.

These are potential future requirements, not capabilities the current project claims to implement.

---

# 42. What I Would Build Next

The next useful improvements should address measurable limitations rather than simply add more frameworks.

Potential directions include:

```text
more deterministic BI tools
larger held-out evaluation sets
citation correctness/completeness evaluation
groundedness evaluation
latency/token/cost regression
retrieval metadata filters
hybrid retrieval experiments
more durable workflow execution
```

A longer-term architectural direction would be extracting the domain-independent pieces into a reusable package so the same system pattern could support other private corpora and BI domains.

---

# 43. Final Lessons

The development journey produced several recurring lessons.

### 1. An LLM call is not an agent

Agent behavior requires orchestration, state, tools, observations, and termination.

### 2. Tool schemas and tool implementations are different

The schema communicates a capability to the model. Python performs the capability.

### 3. Deterministic work should remain deterministic

Do not ask a language model to approximate calculations that code can perform exactly.

### 4. RAG is an end-to-end pipeline

Loading, chunking, metadata, retrieval, ranking, context construction, grounding, and evaluation all affect quality.

### 5. Correct-document retrieval is not enough

The answer-bearing evidence must be available in useful context.

### 6. Ranking and context construction are different

Reranking improves ordering. Neighbor expansion repairs context boundaries.

### 7. Reliability belongs inside the architecture

Retry policy, validation, budgets, and guards should not be afterthoughts.

### 8. A successful tool call does not prove a successful system

The fuel-expense failure demonstrated this directly.

### 9. Integration boundaries deserve contracts

The retrieval-score issue and frontend `AgentResult` mismatch both reinforced this.

### 10. Evaluation should drive engineering changes

The strongest architecture improvements came from measured failures.

### 11. AI evaluation and pytest serve different purposes

One measures behavior that depends on models/retrieval; the other protects deterministic software contracts.

### 12. Observability changes debugging

Structured traces provide evidence that console output cannot preserve reliably.

### 13. State persistence should not be oversold

Application-state restoration is useful, but it is not automatically durable workflow recovery.

### 14. Protocols should remain thin

MCP and FastAPI expose capabilities. They should not absorb the core logic.

### 15. Simpler infrastructure can be the better engineering decision

Local embeddings, FAISS, deterministic routing, and a plain frontend are appropriate when they satisfy the actual requirement.

### 16. Refactoring is part of finishing

The final repository should communicate the current architecture, not every experiment used to discover it.

### 17. Measured failures are valuable portfolio evidence

A project becomes more credible when it can explain not only what worked, but **what failed, why it failed, and what changed because of it**.

---

# 44. Closing Perspective

This project did not begin by trying to assemble a large AI stack.

It began with one API call.

Each subsequent layer was introduced because a new engineering question appeared:

```text
How does the model use a function?
How does an agent continue after a tool result?
How do we prevent loops?
How do we route different workloads?
How do we ground private knowledge?
How do we calculate business metrics reliably?
How do we handle failures?
How do we expose capabilities?
How do we measure retrieval?
How do we evaluate the full trajectory?
How do we diagnose failures?
How do we inspect completed runs?
How do we preserve state?
How do we expose the agent as a service?
How do we prevent regressions?
How do we present the system to a user?
```

The resulting architecture is therefore best understood not as a collection of AI technologies, but as the accumulated answer to those engineering questions.

That is the central development story of **Agentic Business Intelligence**.