#!/usr/bin/env python3
"""
LLM-as-a-Judge evaluation harness for an AR collections agent.

What this does:
  1. Loads collection-agent transcripts (two cohorts: a baseline and a
     post-self-optimization version).
  2. Scores each transcript on a finance-specific rubric using an LLM judge.
  3. Aggregates per-cohort, per-dimension scores and reports the delta.
  4. Calibrates the judge against a sample of independent human labels.

What this is NOT: it is not Peakflo's product, and it does not touch any real
system. It is the *measurement layer* you would build to verify the claim that
a self-optimizing agent's "each execution is smarter than the last."

Run:
    export ANTHROPIC_API_KEY=sk-...
    pip install anthropic
    python eval_harness.py            # scores all transcripts, writes results.json
    python eval_harness.py --offline  # recompute aggregates from a prior results.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

MODEL = os.environ.get("JUDGE_MODEL", "claude-sonnet-4-6")
HERE = Path(__file__).parent
TRANSCRIPTS_PATH = HERE / "transcripts.json"
RESULTS_PATH = HERE / "results.json"

DIMENSIONS = [
    ("factual_accuracy", "Are all stated figures (invoice amount, balance, days overdue) correct and precise? A wrong or vague dollar figure quoted to a customer is a critical failure for a finance product."),
    ("promise_capture", "Did the agent secure and record a specific payment commitment (amount + date) when one was possible? N/A if no commitment was achievable (e.g. a dispute)."),
    ("tone_compliance", "Is the tone professional, respectful, and compliant with collections norms (no harassment, pressure, or false urgency)?"),
    ("escalation", "Did the agent escalate to a human when it should (disputes, hardship, complex negotiation) and avoid escalating routine cases?"),
    ("system_action", "Did the agent log the correct action to the system of record (commitment, dispute reference, confirmation) so the workflow is traceable?"),
]

RUBRIC_TEXT = "\n".join(f"- {name}: {desc}" for name, desc in DIMENSIONS)

JUDGE_SYSTEM = (
    "You are an evaluation judge for an autonomous accounts-receivable collections agent. "
    "You score a transcript against a fixed rubric. Be strict and consistent. "
    "You are scoring the AGENT's behavior, not the customer's. "
    "Important limitation you must respect: you are NOT given the authoritative ledger value for "
    "the invoice, so judge factual_accuracy only on internal consistency and plausibility of what "
    "the agent said, not against ground truth you do not have."
)

JUDGE_USER_TEMPLATE = """Score the following collection {channel} transcript.

RUBRIC (score each dimension 1-5, or "NA" if not applicable):
{rubric}

TRANSCRIPT:
{transcript}

Respond with ONLY a JSON object, no prose, in exactly this shape:
{{"factual_accuracy": <1-5 or "NA">, "promise_capture": <1-5 or "NA">, "tone_compliance": <1-5 or "NA">, "escalation": <1-5 or "NA">, "system_action": <1-5 or "NA">, "rationale": "<one sentence>"}}"""


def judge_transcript(client, t):
    """Call the LLM judge on a single transcript, return parsed scores."""
    msg = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=JUDGE_SYSTEM,
        messages=[{
            "role": "user",
            "content": JUDGE_USER_TEMPLATE.format(
                channel=t["channel"], rubric=RUBRIC_TEXT, transcript=t["transcript"]
            ),
        }],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def norm(v):
    """Normalize a score cell: int 1-5, or None for NA/missing."""
    if isinstance(v, (int, float)):
        return float(v)
    return None


def aggregate(scored):
    """Per-cohort, per-dimension means, excluding NA cells."""
    cohorts = {}
    for s in scored:
        cohorts.setdefault(s["cohort"], []).append(s["scores"])
    out = {}
    for cohort, rows in cohorts.items():
        dims = {}
        for name, _ in DIMENSIONS:
            vals = [norm(r.get(name)) for r in rows]
            vals = [v for v in vals if v is not None]
            dims[name] = round(sum(vals) / len(vals), 2) if vals else None
        present = [v for v in dims.values() if v is not None]
        dims["_overall"] = round(sum(present) / len(present), 2) if present else None
        out[cohort] = dims
    return out


def calibrate(scored, human_labels):
    """Compare judge scores to human labels on the sampled subset."""
    rows = []
    for s in scored:
        labels = human_labels.get(s["id"])
        if not labels:
            continue
        for name, _ in DIMENSIONS:
            j, h = norm(s["scores"].get(name)), norm(labels.get(name))
            if j is None or h is None:
                continue
            rows.append({"id": s["id"], "dimension": name, "judge": j,
                         "human": h, "gap": round(j - h, 2)})
    by_dim = {}
    for r in rows:
        by_dim.setdefault(r["dimension"], []).append(r["gap"])
    bias = {d: round(sum(g) / len(g), 2) for d, g in by_dim.items()}
    return {"pairs": rows, "mean_gap_by_dimension": bias}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="recompute aggregates from existing per-transcript scores")
    args = ap.parse_args()

    data = json.loads(TRANSCRIPTS_PATH.read_text())
    human_labels = {k: v for k, v in data["human_labels"].items() if not k.startswith("_")}

    if args.offline:
        scored = json.loads(RESULTS_PATH.read_text())["transcripts"]
    else:
        try:
            from anthropic import Anthropic
        except ImportError:
            sys.exit("Missing dependency. Run: pip install anthropic")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("Set ANTHROPIC_API_KEY to run the judge.")
        client = Anthropic()
        scored = []
        for t in data["transcripts"]:
            print(f"  judging {t['id']} ...", file=sys.stderr)
            res = judge_transcript(client, t)
            rationale = res.pop("rationale", "")
            scored.append({"id": t["id"], "cohort": t["cohort"],
                           "channel": t["channel"], "invoice": t["invoice"],
                           "scores": res, "rationale": rationale})

    results = {
        "model": MODEL,
        "rubric": [{"name": n, "description": d} for n, d in DIMENSIONS],
        "transcripts": scored,
        "aggregates": aggregate(scored),
        "calibration": calibrate(scored, human_labels),
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    agg = results["aggregates"]
    print("\nOverall score:  v1_baseline = {}   v2_optimized = {}".format(
        agg.get("v1_baseline", {}).get("_overall"),
        agg.get("v2_optimized", {}).get("_overall")))
    print("Factual accuracy: v1 = {}  ->  v2 = {}".format(
        agg.get("v1_baseline", {}).get("factual_accuracy"),
        agg.get("v2_optimized", {}).get("factual_accuracy")))
    print("Judge mean gap vs humans (positive = judge too lenient):")
    for d, g in results["calibration"]["mean_gap_by_dimension"].items():
        print(f"   {d}: {g:+}")
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
