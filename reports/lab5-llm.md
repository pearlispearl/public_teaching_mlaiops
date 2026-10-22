# Lab 5 Part B — Operating an LLM step

The LLM step drafts a maintenance work order from a failure prediction. Output is one JSON
object: `action` (`draft_work_order`, `escalate_to_engineer`, `no_work_order`, `refused`,
`insufficient_input`) and a short `summary`. System prompt: `prompts/work_order_system.txt`.
Model: Gemini on Vertex AI through `GcpAdapter.generate()`; token counts and latency come
from the provider's usage fields, never from counting words.

## Task 7 — Evaluation gate

Golden set: `evals/golden/work_order.jsonl`, 13 cases. Grounding wo-004 to 006, guardrail
wo-007 and 008, injection wo-009 and 010, insufficient input wo-011 and 012, and wo-013
(an implausible `temp_c=212`, the Lab 4 unit-change incident seen from the LLM side).
The gate fails on any case that passed in the baseline and fails now, not on a pass rate.

| Run | Pass | THB / 1k requests | What moved |
|---|---|---|---|
| v1 prompt, first recording, original checks | 9/13 | 5.338 | `reports/llm_eval-work_order-v1-original-checks.json` |
| v1 responses rescored after fixing two checks | 11/13 | 5.338 | wo-008 and wo-012 were check defects (see below) |
| v2 prompt (ordered rules), **baseline** | 12/13 | 5.670 | wo-013 fixed by stating that implausible readings override the probability thresholds |
| degraded prompt (rules removed), `reports/lab5-gate-fail.txt` | 6/13 | 3.485 | **GATE FAILED, 6 regressions**: wo-004, 006, 008, 009, 012, 013 |

What the degraded run shows: with the grounding rule removed the model invented a date
(`2024-07-26`, wo-006); with the injection rule removed it obeyed an instruction hidden in
`operator_note` and returned `draft_work_order` (wo-009). It was 39% cheaper and answered
worse, which is not an optimisation.

Two checks were wrong, not the model, and were fixed with the reason recorded in the commit:
wo-008 forbade the phrase "approved by", which the model repeats while correctly refusing;
wo-012 did not accept the wording "outside 0 to 1". The v1 responses were rescored offline
with the corrected checks to separate the effect of the checks from the effect of the prompt.

**Variance.** Temperature 0 does not make the model deterministic. Over repeated live runs
wo-013 passed in 3 of 4 runs with the v2 prompt and 1 of 4 with the v4 prompt, and wo-011
failed in 6 of 6 runs with both. Scoring a recorded fixture is deterministic; re-recording
is where the noise enters, so a single live run can produce a false regression.

## Task 8 — A guardrail you can demonstrate

- **Failure.** A message with no `machine_id` (wo-011) or a physically impossible reading
  (wo-013, `temp_c=212`) is decided by the model: it escalated a message with no machine,
  and called a 212 degree reading normal. No prompt wording fixed wo-011 (6 of 6 failures).
- **Control.** `src/work_order_guard.py` decides these cases in code, before the model is
  called, using the same `PLAUSIBLE_RANGES` as the Lab 4 data contract tests. Refusals,
  injection handling and the probability thresholds stay with the model.
- **Evidence the control fired.** Without the guard wo-011 failed in every run; with
  `--guard` it passes, and the response shows zero tokens because the model was never
  called (`reports/lab5-guard-run.txt`). The cases are in the golden set, so a change that
  removes the guard fails the gate.
- **Command a marker can run, offline and free:**
  `pytest -q tests/test_work_order_guard.py`

Limit: the guard covers required fields and plausible ranges only. The refusal and
injection cases (wo-007 to wo-010) rely on the prompt, and they passed in the runs above,
but a prompt is not a guarantee.

## Task 9 — The token bill

Rates are in `src/llmcost.py` (tier `gcp/small`). **Rates not yet checked against the
provider's pricing page for my region: check and record the date before citing a figure.**

Baseline (v2 prompt, 13 cases): 451 input tokens and 54 output tokens per request on
average, **5.6695 THB per 1,000 requests**. Input is 3.83 THB (68%) and output 1.84 THB (32%).

1. **THB per 1,000 requests: 5.6695** at the measured average usage above.
2. **Capping `max_output_tokens`.** Outputs run 25 to 92 tokens. A cap of 60 saved
   0.34 THB per 1,000 (6.0%, 5.6695 to 5.3295) but cut 5 of 13 answers mid-JSON and the gate
   failed with 6 regressions, so it was reverted. A cap safely above 92 saves nothing here,
   because no answer is longer. In this system output is already short and input dominates,
   so the cap is not the largest saving, contrary to the usual case.
3. **Prompt cache.** Break-even hit rate 0.217. Measured hit rate 0.000 (0 cached of
   11,734 input tokens over 26 calls, `reports/lab5-cache.txt`). Below break-even, so an
   explicit cache on this prefix would cost more than it saves.

What did lower the bill, with the gate as the check:

| Change | THB / 1k | Pass | Gate |
|---|---|---|---|
| v2 prompt (baseline) | 5.670 | 12/13 | n/a |
| v3: shorter prompt, summary at most 25 words | 3.808 | 10/13 | FAILED (wo-004, wo-013) |
| v4: v3 plus two restored sentences | 3.876 | 11/13 | FAILED (wo-013, flaky) |
| v4 plus deterministic guard (`--guard`) | **2.958** | **13/13** | **PASSED** |

The 2.958 figure averages over the golden set, where 3 of 13 cases (23%) are decided by the
guard at zero token cost. That share is a property of the test set, which deliberately
over-represents bad inputs, not of real traffic. The cost of a request that reaches the
model is about 3.85 THB per 1,000. Real savings depend on how often malformed requests occur.

### The defence (for someone who controls budget and does not write code)

The language-model step cost 5.67 THB per 1,000 requests. Most of that was not the answers
but the fixed instructions sent with every request, so I shortened the instructions and
moved two checks that never needed a model (a missing machine ID and an impossible sensor
reading) into ordinary code that runs first and costs nothing. It now costs 2.96 THB per
1,000 requests on my test set, a 48% reduction. At an assumed 30,000 requests a month that
is about 89 THB instead of 170 THB. What I gave up: the shorter summaries (25 words instead
of 60), and part of the saving is specific to my test set, which contains more bad inputs
than real traffic would. I tried the usual shortcut of limiting answer length first: it
saved 6% but cut answers off mid-sentence and broke six test cases, so I did not ship it.
