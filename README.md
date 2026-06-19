# AR Collections Agent — Self-Optimization Eval

An LLM-as-a-Judge evaluation harness that tests whether a self-optimizing
collections agent actually got better after an optimization cycle — and catches
the case where the headline metrics say yes but a per-dimension judge says no.

Built as an application artifact for the Peakflo PM Intern (Agentic Workflows) role.
See **`teardown.md`** for the writeup.

## Contents

| File | What it is |
|------|------------|
| `index.html` | Interactive dashboard — open in any browser. The story, start to finish. |
| `eval_harness.py` | The runnable judge: scores transcripts, aggregates, calibrates. |
| `transcripts.json` | Synthetic v1/v2 collection transcripts + ledger + human labels. |
| `results.json` | Output of a real run (what the dashboard renders). |
| `teardown.md` | 1-page PM writeup: the finding, why it matters, what to ship next. |

## Run it

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-...
python eval_harness.py          # scores all transcripts with the LLM judge, writes results.json
```

No API key handy? Reproduce the aggregates from the saved per-transcript scores:

```bash
python eval_harness.py --offline
```

Expected output:

```
Overall score:  v1_baseline = 3.83   v2_optimized = 4.3
Factual accuracy: v1 = 4.75  ->  v2 = 3.75
Judge mean gap vs humans (positive = judge too lenient):
   factual_accuracy: +0.5
   ...
```

Judge model is configurable via `JUDGE_MODEL` (default `claude-sonnet-4-6`).

## Note

Synthetic data only — no real customer information. This demonstrates the
measurement method for validating agent self-optimization; it does not connect
to any production system.
