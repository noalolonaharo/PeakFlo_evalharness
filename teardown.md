# Evaluating self-optimization in an AR collections agent

**A measurement artifact for the Peakflo PM Intern application — Agentic Workflows**

The JD asks the PM to "assist in evaluating our agentic systems' self-optimization (leveraging LLM-as-a-Judge frameworks) to ensure each execution is smarter than the last." This is my attempt to do that job before having it: build the measurement layer that would tell you whether a self-optimization cycle actually made an agent better — and catch it when the answer is "not the way you think."

## TL;DR

I ran an LLM-as-a-Judge eval over two cohorts of AR collection transcripts — a baseline and a post-self-optimization version. Every headline metric improved: completion rate held at 100%, the overall score rose 3.83 → 4.30, payment-promise capture jumped 78%, tone climbed 27%. **Scored per-dimension instead of as one number, the same data shows factual accuracy fell 21% (4.75 → 3.75).** The agent learned to be warmer and close commitments, and started quoting wrong or imprecise balances on voice calls. Then the part that matters most: calibrating the judge against human labels shows it's accurate on tone and promise capture but runs lenient *specifically* on factual accuracy — it can't reliably catch a wrong dollar figure, because a wrong figure is plausible and the judge isn't given the ledger. A system that self-optimizes against this judge will trade accuracy for tone and report itself as improving.

## Why this is the right thing to measure

"Each execution smarter than the last" is a claim, and an aggregate score is the easiest way to fool yourself about it. Collapsing a five-dimension rubric to one number lets a large gain on easy-to-judge dimensions (tone, promise capture) mask a regression on the hardest and highest-stakes one (factual accuracy). For a finance product the asymmetry is severe: a slightly stiff tone costs nothing, but telling a customer the wrong balance triggers disputes, damages trust, and corrupts the record the rest of the workflow runs on. The eval has to be dimension-aware and weighted toward what a finance customer actually can't tolerate.

## What I built

- **Rubric** — five dimensions a collections team cares about: factual accuracy, promise capture, tone & compliance, escalation correctness, system-of-record action.
- **`eval_harness.py`** — scores each transcript with an LLM judge (`claude-sonnet-4-6`), aggregates per cohort, and calibrates the judge against a sample of human labels. Runnable with an API key; `--offline` reproduces the exact numbers in the dashboard from the saved scores.
- **`index.html`** — a dashboard that walks the finding: the apparent win, the per-dimension reveal, the two offending transcripts, and the judge-calibration result.
- **Synthetic data** — eight hand-authored voice + email transcripts. No real customer data.

## The finding, in order

1. **Apparent win.** On the metrics a team usually watches, v2 ships.
2. **Reveal.** Four dimensions rose; factual accuracy retreated. The two failures are both voice calls — one quoted `$11,480` against a `$12,480` ledger balance, the other said "around twenty-eight thousand" for `$27,900`. Spoken, imprecise, unrecoverable.
3. **Meta-layer.** The judge's mean gap vs. humans is `0.0` on every dimension except factual accuracy, where it's `+0.5` (too lenient) — and the leniency concentrates exactly on the wrong-number transcripts. The optimizer's grader is blind where the regression happened.

## What I'd ship next

1. **Ground-truth accuracy check.** Stop asking an LLM whether a number is right. Extract every amount/date the agent states and diff it deterministically against the ledger. Factual accuracy becomes truth, not plausibility — and the optimizer can no longer game it.
2. **Per-decision audit log.** Record the value quoted, its source, and the judge's verdict per execution, so a regression is one query away instead of a customer escalation weeks later.

A reasonable target metric to gate releases on: **zero tolerance on factual accuracy** (any quoted figure that fails the ledger diff blocks promotion of that agent version), with tone and promise capture tracked as improvement metrics rather than gates.

Both recommendations line up with public Peakflo customer feedback — invoice-classification accuracy, and wanting audit visibility into why an agent made a given decision.

## Scope and honesty

This runs on synthetic transcripts, not Peakflo's live system — I don't have access to it and didn't want to pretend otherwise. The value here is the method and the failure mode it surfaces, plus working code that produced the numbers. If the real system already has a deterministic ground-truth check upstream of the LLM judge, then the specific blind spot I'm modeling is already closed — and I'd want to know that, because it would change what's worth measuring next.
