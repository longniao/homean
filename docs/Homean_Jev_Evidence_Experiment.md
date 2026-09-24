# Jev evidence-check experiment

Status: local evaluation harness implemented, real Jev inference **not yet run**.
The owner configured `TYPESAFE_API_KEY` on the Mac mini; its presence in the
project's `backend/.env` was verified on 2026-09-22 without exposing the value.
Jev authentication and real inference remain untested. No production pipeline,
report status, database, or deployment has been changed by this experiment.

## Hypothesis and scope

A semantic check may catch claims that cite a real transcript segment but change
its meaning. Example: “there might be a water mark” becoming “the window leaks.”
The intended benefit is less agent review effort and fewer unsupported claims.
This is not verification of property condition, an inspection, or permission to
send a report. All existing human confirmation requirements remain in force.

The first experiment evaluates individual claims against supplied text. It does
not transcribe audio, generate reports, measure report completeness, or compare
the end-to-end output quality of Jev and the current report generator.

## What is included

- `backend/evals/real_estate_evidence_v1.json`: 100 agent-authored synthetic cases
  from 25 short scenarios, with 50 supported and 50 unsupported claims. Each has
  an expected label and rationale. **These labels have not been independently
  reviewed by a human and are not a production-quality gold dataset.**
- The 60-case development and 40-case holdout sets keep all claims from a given
  scenario together. Do not tune prompts or thresholds on holdout results.
- Cases cover uncertainty, negation, source attribution, room identity, time,
  quantities, corrections, preferences, causal inference, questions, compound
  claims, missing evidence, conflicting sources and embedded instructions.
- `backend/app/verticals/evaluations/real_estate_evidence_v1.yaml`: versioned,
  English-parameterized experimental rubric, pinned model `jev-1.13.0`, thresholds
  and dated price assumptions. Loaded once when the evaluation command starts;
  deliberately separate from the active production vertical pack.
- `backend/app/evaluation/evidence.py`: replaceable evaluator interface, Jev
  HTTP implementation, offline control, validation and metric reporting. No
  production settings, database queries, customer data exports or state changes.
- Tests use `httpx.MockTransport`; they never call a paid service.

## Run locally

From `backend/`, validate all fixtures without credentials or network calls:

```sh
uv run python -m app.evaluation.evidence
```

Run the local reference control:

```sh
uv run python -m app.evaluation.evidence --provider baseline \
  --output /tmp/homean-evidence-baseline.json
```

The control accepts every claim that has a nonempty evidence excerpt. All bundled
cases have such an excerpt. Its 100% miss rate on the 50 unsupported claims is
therefore **by construction**, not a measured failure rate of Homean's current
LLM. It illustrates the limitation of reference validity without semantic checks.

For real inference, set `TYPESAFE_API_KEY` securely in the process environment.
Do not paste the key into chat, commit it, or put it in command-line arguments.
The script does not automatically read `.env`. If it is stored in the gitignored
root `.env`, `uv run --env-file ../.env python ...` explicitly loads it.

Start with four synthetic development cases (one scenario, two of each label):

```sh
uv run python -m app.evaluation.evidence --provider jev \
  --split development --limit 4 --output /tmp/homean-jev-smoke.json
```

Then measure development performance, fix the rubric if necessary, freeze its
version, and run the holdout once:

```sh
uv run python -m app.evaluation.evidence --provider jev \
  --split development --output /tmp/homean-jev-development.json
uv run python -m app.evaluation.evidence --provider jev \
  --split holdout --output /tmp/homean-jev-holdout.json
```

Output paths must not already exist. The CLI only reads the bundled synthetic
dataset: there is no arbitrary-input or production-export flag. `--limit` is
1–100 and caps selected cases. Calls run serially with one attempt per case,
a 15-second HTTP timeout, and no automatic retries. Authentication failures,
rate limiting and overload stop further requests; rerun later after inspecting
the failure. Redirects are not followed. These limits avoid an unbounded paid
evaluation run; estimated cost is not a hard dollar budget.

## Interpret results

The model receives only `evidence`, `claim` and the rubric; expected labels,
rationales, scenario/category IDs and split names never enter the request.
The check uses a Noul answer (probability of semantic support). Noul does not
have a separate confidence field. The initial, **uncalibrated** thresholds are:

- Probability >= 0.85: `supported` for evaluation only.
- Probability <= 0.15: `flagged` for evaluation only.
- Between them: `uncertain`, counted as needing review.
- Failure, malformed response or unexpected model version: `error`, unassessed.

No outcome means approved, verified or sendable. Thresholds should be chosen
using independently reviewed development cases and the cost of missed issues
versus needless review, not copied directly into the production send gate.

JSON output includes dataset/rubric hashes, their versions, requested and returned
model, thresholds, category breakdowns, per-case probabilities, p50/p95 latency,
token usage and estimated cost. It omits evidence/claim text and vendor error
bodies. Metrics explicitly distinguish:

- False positives: supported cases flagged or uncertain, divided by assessed
  supported cases.
- False negatives: unsupported cases marked supported, divided by assessed
  unsupported cases.
- Review recall/precision and total review burden; marking everything uncertain
  cannot masquerade as a useful low-effort checker.
- Coverage and unsupported cases missed **or unassessed**, including cases not
  attempted after a fatal error. Undefined rates are `null`, never zero.
- Cost from recorded successful responses. Failed calls may still be billed,
  so incomplete runs explicitly flag that their recorded cost may undercount.

The dated estimate uses $0.042 per million input tokens, output free. Check the
provider's current price before a substantial run. Small synthetic cases cannot
predict production latency, token counts, calibration or accuracy.

## Validation and next decision

Offline tests cover label leakage, API payloads, response validation, bounds,
timeouts, model-version drift, redirects, fail-stop behavior, metric denominators,
fixture splits and CLI defaults. Passing these tests proves harness behavior,
**not that Jev detects report errors**.

Local verification on 2026-09-22: all **26** tests in
`tests/test_evidence_evaluation.py` passed; Ruff lint passed. The offline CLI
validated all 100 cases across 15 categories and the citation-only control
completed with the expected 50 missed unsupported claims and no inference cost.
No Jev accuracy, latency or actual billing result is available yet.

Before production integration:

1. Run real inference and independently review the synthetic labels and errors.
2. Compare against a generative-model checker using the same frozen inputs and
   rubric, if Jev's initial results justify the extra experiment. Neither this
   comparison nor an end-to-end pipeline benchmark has been performed yet.
3. With appropriate data permission and retention arrangements, evaluate a
   representative, independently labeled sample of real showing text. Keep
   related visits/claims out of both tuning and holdout sets.
4. Only after benefit is demonstrated, consider an optional shadow check after
   observation extraction/report generation. A future integration must scope
   reads by workspace and preserve original evidence links, timestamps, generator
   metadata and review state, recording checker metadata separately.
5. Display issues for the agent only after review usability is tested. Provider
   failures must stay visible; they must never silently become a passed check.
   Human confirmation remains mandatory regardless of the model's probability.

## Primary references checked 2026-09-22

- [TypeSafe API contract](https://docs.typesafe.ai/api)
- [TypeSafe probability and confidence semantics](https://docs.typesafe.ai/confidence)
- [TypeSafe quick start](https://docs.typesafe.ai/introduction/quickstart)
- [Jev price and text-only capabilities](https://openrouter.ai/typesafe/jev-1.13/api)
- [TypeSafe privacy policy](https://typesafe.ai/legal/privacy-policy): says inputs
  are not used for model training, service hosting is in the US, and does not give
  a fixed input-retention duration. This experiment transmits synthetic text only.
