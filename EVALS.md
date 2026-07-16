# 🧪 Agent evaluation (evals)

End-to-end evaluation suite for the HR agent: each case runs against the
real agent (LangGraph → MCP server → SQLite/RAG/BigQuery → LLM), not mocks.
Assertions are anchored to the synthetic data generated with seed 42.

## How to run

```bash
uv run python -m evals.run            # deterministic + LLM-as-judge
uv run python -m evals.run --sem-juiz # deterministic layer only
```

Needs `OPENAI_API_KEY` (agent + judge) and, for the *analytics* category,
BigQuery credentials in `.env`. Doesn't run in CI (consumes API + secrets);
it's a manual harness and these results are version-controlled.

## Evaluation layers

- **Deterministic** — which MCP tool was called, substrings/regex in the response,
  and the confirmation gate state (interrupt). Cheap and reproducible.
- **LLM-as-judge** — a `gpt-4o-mini` judge evaluates the response against a
  natural-language rubric, only where string matching would be too fragile.

A case passes when **all** of its checks pass. Cases marked as
*stretch* exercise known limits (e.g., name disambiguation, reasoning
across policy + data) and may fail on purpose — they're signal, not noise.


## Results

**Overall accuracy:** 26/28 (93%) · **judge:** yes · **total latency:** 374s · **run on:** 2026-07-11


### By category

| Category | Passed / Total |
|---|---|
| analytics | 4/4 |
| cruzamento | 1/2 |
| desambiguacao | 2/3 |
| escrita | 4/4 |
| governanca | 3/3 |
| operacional | 4/4 |
| politica | 4/4 |
| roteamento | 4/4 |

### By case

| Case | Category | Result | Checks that failed |
|---|---|---|---|
| R1 | roteamento | ✅ | — |
| R2 | roteamento | ✅ | — |
| R3 | roteamento | ✅ | — |
| R4 | roteamento | ✅ | — |
| O1 | operacional | ✅ | — |
| O2 | operacional | ✅ | — |
| O3 | operacional | ✅ | — |
| O4 | operacional | ✅ | — |
| D1 *(stretch)* | desambiguacao | ❌ | judge |
| D2 | desambiguacao | ✅ | — |
| D3 | desambiguacao | ✅ | — |
| P1 | politica | ✅ | — |
| P2 | politica | ✅ | — |
| P3 | politica | ✅ | — |
| P4 | politica | ✅ | — |
| A1 | analytics | ✅ | — |
| A2 | analytics | ✅ | — |
| A3 | analytics | ✅ | — |
| A4 | analytics | ✅ | — |
| W1 | escrita | ✅ | — |
| W2 | escrita | ✅ | — |
| W3 | escrita | ✅ | — |
| W4 | escrita | ✅ | — |
| C1 *(stretch)* | cruzamento | ✅ | — |
| C2 *(stretch)* | cruzamento | ❌ | judge |
| G1 | governanca | ✅ | — |
| G2 | governanca | ✅ | — |
| G3 | governanca | ✅ | — |
