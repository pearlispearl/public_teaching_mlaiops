# Lab 5, Task 5: cost report

Provider `gcp`, region `asia-southeast1`. All figures are THB. Billing source: Cloud Billing Reports exported as CSV
for the billing days 22 to 23 October: filtered by label `lab=5` (`reports/lab5-billing-label.csv`), the same days
unfiltered and grouped by SKU (`reports/lab5-billing-sku.csv`), and October by service (`reports/lab5-billing-oct.csv`).
Exports were taken on 2026-10-23, so usage from the last hours may not be posted yet.

## 1. Estimate, made before running

**72 THB** (`reports/lab5-estimate.md`, committed before Task 1). Of that, 36 THB was one Vertex endpoint
(`n1-standard-4`) for a 4-hour cap, 12 THB contingency, and 24 THB for everything else.

## 2. Actual, from billing, filtered by tag

**9.95 THB** with the filter `lab=5` (6 Vertex AI SKUs: pipeline run fee, pipeline compute, and the serving endpoint).

The tag filter misses two things I created without the label, which only show up unfiltered:

| Not tagged `lab=5` | THB | Why it has no label |
|---|---|---|
| Gemini calls (LLM step) | 0.24 | I labelled the jobs and resources I create, but did not set labels on the model requests, so the usage carries none. Next time: set `lab=5` on every generate call |
| Artifact Registry storage | 0.36 | The registry repository was created in an earlier lab and holds all labs' images |

All-in for the same two billing days it is **10.54 THB** (9.95 + 0.24 + 0.36, 10.54 after rounding). The lab's own list of
failure modes names this one: untagged resources make the report differ from billing. I report both numbers
rather than pick the one that is closer. Bounds: the whole of October on the project is 20.73 THB (Vertex AI 11.66,
Artifact Registry 5.26, Cloud Run 3.78, Cloud Storage 0.04), an upper bound; the Artifact Registry and Cloud Run
lines match what the Lab 1 to 4 export showed (5.24 and about 3.8), so most of them were spent before Lab 5.
The tag-filtered figure also excludes any Lab 5 usage that fell on other billing days (Vertex AI for October is 11.66
against 10.19 inside these two days). Not yet counted: AWS, which is on a $100 credit and shows no charge yet because
billing lags.

## 3. The gap

**-62.05 THB (-86.2% against 72) by tag; -61.46 THB (-85.3%) all-in.** Even against the October upper bound of
20.73 the gap is -71.2%. **This is outside the lab's 20% limit and I am not going to adjust either number to hide it.**
The estimate was too high, and almost all of the gap is one decision. The table compares the estimate with the
all-in figure, because the estimate included components (LLM, storage) that carry no tag:

| Component | Estimate | Actual | Gap |
|---|---|---|---|
| Serving, Vertex endpoint | 36.00 | 1.80 | -34.20 |
| Contingency | 12.00 | 0.00 | -12.00 |
| LLM tokens | 5.00 | 0.24 | -4.76 |
| Serving after (Cloud Run) | 3.00 | 0.00 | -3.00 |
| Training and pipeline steps | 8.00 | 5.13 | -2.87 |
| Storage | 3.00 | 0.36 | -2.64 |
| Pipeline run fee | 5.00 | 3.02 | -1.98 |
| Monitoring | 0.00 | 0.00 | 0.00 |
| **Total** | **72.00** | **10.55** | **-61.45** |

(10.55 here and 10.54 above are the same total rounded differently.)

* **The endpoint.** I budgeted the worst case for the only component that could hurt: 4 hours at 8.9 THB/h. It was
  billed for 0.79 core-hours, which on four cores is about 0.2 hours, 1.80 THB. I deleted it the same session. The
  hourly rate itself was right: 1.80 THB / 0.1975 h is 9.1 THB/h, within about 2% of the 8.9 I derived from my earlier
  bill. The unit price held; the quantity of hours was the error, and 4 hours was a cap, not an expectation.
* **The billed time is shorter than my own timestamps.** The deploy request was at 23:16 (Bangkok) and the endpoint
  was removed around 23:43, about 27 minutes, but billing shows about 12 minutes. My explanation, not confirmed: the
  replica only bills once it is up, and pulling a 1.2 GB image and loading the model took a good part of that time.
  The other possibility is that some usage is not posted yet. If it posts, the serving figure rises by at most
  about 2.2 THB at the same rate.
* **Contingency (12) and Cloud Run (3) were never spent.** I assumed about 5 runs; billing shows 3 billed pipeline
  jobs, which suggests that runs that failed at job creation were not billed (an inference from the count, not
  something I confirmed). I did not move serving to Cloud Run, so that line stayed
  at zero (see section 6).
* **LLM (5 vs 0.24).** I had assumed about 150 calls. The window shows 11,734 input and 1,415 output units, the cache
  measurement run; the other Gemini usage (0.73 THB for October in total) fell on other billing days.
* **Storage (3 vs 0.36)** and the **run fee (5 vs 3.02)** were estimated from the first-run rates with rounding up.
* What I would change next time: size the endpoint line by expected hours with a separate hard cap, rather than
  budgeting the cap, and list the LLM calls I plan to make. The risk I named in the estimate, a forgotten
  endpoint at about 213 THB per day, did not happen: it was deleted the same day.

## 4. Breakdown by component (billing days 22 to 23 October)

The first three rows are the 9.95 THB that carries the `lab=5` tag; the last two are the untagged lines.

| Component | THB | SKUs |
|---|---|---|
| Training and pipeline steps (compute) | 5.13 | Training/Pipelines on E2 core 2.90, E2 RAM 1.55, SSD PD 0.68 |
| Pipeline run fee | 3.02 | Managed Pipeline job count, 3 jobs |
| Serving (Vertex endpoint) | 1.80 | N1 predefined core 1.20 (0.79 h), RAM 0.60 (2.97 GiB-h) |
| Storage | 0.36 | Artifact Registry storage 0.36; Cloud Storage operations 0.00 |
| LLM tokens | 0.24 | Gemini 2.5 Flash input 0.12, output 0.12 |
| Monitoring and logging | 0.00 | Cloud Logging 0.00 (0.01 GiB) |
| **Total** | **10.54** | |

Training and pipeline steps are one line in billing: every pipeline step runs on the same E2 compute, so I cannot
split "training" from the other steps with this export.

## 5. Cost per 1,000 predictions at three utilisation levels

Serving cost basis: one `n1-standard-4` Vertex endpoint at **9.11 THB/hour** (derived from the billing above:
(1.20 + 0.60) / (0.79 / 4)). Throughput **31.1 req/s** at 10 concurrent clients, measured on this endpoint
(`reports/lab5-k6-vertex-vus10.txt`; 31.8 req/s at 5 clients). Computed with `cost_per_1k_predictions` in `src/costs.py`.

| Utilisation | THB per 1,000 predictions |
|---|---|
| 5% | 1.6281 |
| 25% | 0.3256 |
| 80% | 0.1018 |

Which one I believe: none of these, and the reason is the point. This system reads each of 240 machines about every
10 minutes, which is about 0.4 requests per second, so real utilisation of this endpoint would be about 1.3%, and the
cost about 6.33 THB per 1,000 predictions. That is an assumption about traffic, not something I measured; the
service is not in production. At that rate a warm endpoint is a poor fit and scheduled batch inference or a
scale-to-zero service is the right shape. Note also that the measured p95 at 10 clients was 325 ms against my
250 ms target, so even the cheap end of this table is for an endpoint that misses its latency target at that load.

## 6. One optimisation I applied

**What I applied: shorter LLM prompt plus a deterministic guard in front of the model** (Tasks 7 to 9,
`reports/lab5-llm.md`). I did not apply a serving change, and I say so because the estimate planned one: there was
no time left to move serving to Cloud Run and re-measure, so I do not report a Cloud Run figure.

| | Before | After |
|---|---|---|
| Configuration | v2 prompt, every request goes to the model | v4 prompt (shorter, summary at most 25 words) plus guard that decides missing-machine and impossible-reading cases in code |
| THB per 1,000 requests | 9.0832 | 4.557 (-50%) |
| Golden-set result | 12/13, baseline | 13/13, gate passed |
| At an assumed 30,000 requests a month | about 273 THB | about 137 THB |
| Latency | not measured for the LLM step | not measured; the guard answers 3 of 13 cases without calling the model |

What it cost me: the summaries are shorter (25 words instead of 60), and part of the saving is a property of my test
set, which over-represents bad inputs (3 of 13 cases are decided by the guard at zero token cost); real traffic would
save less. The saving comes with a check, not instead of one: the shorter prompt alone failed the gate
(wo-004 and wo-013 regressed) and the guard is what brought it back to 13/13. Prices are the verified rates in
`src/llmcost.py` (gemini-2.5-flash), after correcting an earlier placeholder that was about 40% off.

## Budget and what remains

Term spend: about 368 THB (357.49 from the export I used for the estimate, plus 10.54 for Lab 5), under the 800 THB
limit. The last check is 24 hours after teardown: run `python scripts/teardown_verify.py --lab 5` and compare the bill
for 24 to 25 October with this report. If the endpoint or compute lines move, section 3 gets a correction.
