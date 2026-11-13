# PRD: gst-tax-mcp

Repo: github.com/zoeb-nomi/gst-tax-mcp. Status: v0, nine tools shipped.

## 1. Problem

Anyone who puts an LLM in front of Indian GST questions gets confident numbers that are sometimes wrong: a rate that changed on a date, a due date that depends on filer type and state, an input credit that section 17(5) blocks. Agent builders have to hand-write this logic or trust the model. Small-business finance tools and CA firms re-check every figure by hand. The cost today is rework, and a wrong due date or credit claim that becomes a notice.

## 2. Users and use cases

1. **Agent builder** wires the server into any MCP client so the agent calls tools for rates, deadlines and liability instead of guessing.
2. **CA firm** reconciles a client's purchase books against GSTR-2B and sees matched, mismatched, missing and blocked credit before filing GSTR-3B.
3. **SMB finance tool** validates an e-invoice (IRN hash, GSTIN checksum, mandatory fields, tax math) and checks GSTR-3B turnover against ITR receipts before a mismatch is flagged by the department.

## 3. Goals and success metrics

| Metric | Today | Target |
|---|---|---|
| Tools exposed over MCP stdio | 9 (README.md) | 9, no regressions |
| Unit tests on the core engine | 33 (tests/, README.md) | Every tool covered, rule-table changes need a test |
| Same input gives same output | By design, no model in the loop (docs/architecture.md); no repeat-run test committed | Asserted in tests |
| Accuracy against official sources | 47/47 on a 47-case set, each expected answer from a CBIC notification or the Act; a model answering from memory scores 33/40 on the first 40 (eval/README.md) | Held-out set of fresh cases, 100% on the regression set on every change |
| Agent end-to-end correctness | Not measured yet | Measured by a benchmark, see agent-eval-bench |
| Rule-table coverage | Curated sample (README.md, Honest limits) | Not measured yet; define coverage first |

## 4. Non-goals

- Not a tax opinion, not a filing or e-invoice submission service.
- No calls to the GST portal; no storing of client data.
- No model inside the tools.
- No guessing of figures the tools cannot source (ITR gross receipts, projected income). The caller supplies them.

## 5. Solution

Nine deterministic Python tools served over MCP stdio, backed by rule tables in `gst_mcp/core/data.py`: applicability, HSN/SAC classification with rate history, liability, ITC reconciliation, filing deadlines, GSTR-1 buckets, e-invoice validation, turnover crossover, advance tax. A LangGraph ReAct agent loads the tools over MCP and writes a filing pack. Synthetic fixtures and recorded transcripts back the demos.

Design decisions and trade-offs:
- **Deterministic tools, not model answers.** Same input, same output, auditable. Cost: coverage is only as wide as the tables, and every rate change needs a human edit.
- **Rates carry an effective date.** Answers are right for the invoice date, not today. Cost: larger tables.
- **MCP over stdio, agent does not import the engine.** Any host that can spawn a subprocess can use it. Cost: process spawn and JSON overhead per session.
- **Caller supplies unsourceable inputs.** No invented numbers. Cost: the agent must ask, so flows are longer.
- **LLM on top, not inside.** The agent plans calls and explains; every number comes from a tool response.

## 6. Risks and mitigations

- **Tax accuracy.** Tables are a curated sample and may be stale. Mitigation: state it in the README, add a golden set checked against notifications, show the rule row and effective date in every answer.
- **Misuse as advice.** Mitigation: not-a-tax-opinion notice, outputs list reasons and flags, a human signs off.
- **Agent misuse of correct tools.** The agent can call the wrong tool or misread output. Mitigation: evaluate the agent layer separately (agent-eval-bench).
- **Rule drift.** Law changes after release. Mitigation: dated rows, a documented update procedure, a check on table age.
- **Sensitive data.** Real client files passed into tools. Mitigation: synthetic fixtures only in the repo, no logging of inputs.

## 7. Roadmap

**Now**
- Add a golden set of cases checked against CBIC notifications and report a pass rate.
- Add a determinism test (same input twice).
- Document the table-update procedure and add an "as of" date to the tables.

**Next**
- Widen the rule tables beyond the curated sample, starting with the most-used HSN/SAC codes.
- Run the agent through the evaluation bench against these tools.
- Publish an install snippet for common MCP clients.

**Later**
- Automated pipeline to detect new notifications and open a table-change review.
- More ITC and e-invoice edge cases from real reconciliation failures.
- Optional Node package for hosts without Python.

## 8. Open questions

- What does "accurate" mean here: agreement with a CA, or with the notification text?
- How wide must the tables be before this is safe for anything beyond demos?
- Who owns table updates once the repo has outside users?
- Does the ITR crossover belong in a GST server or in its own?
