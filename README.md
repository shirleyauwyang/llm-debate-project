# AI_LLM_Project

V2 of the DeepSeek multi-agent debate experiment. The included manifests reuse the
existing seed-42 samples. The pilot has 3 questions per dataset and the final
has 50 per dataset. The two samples are disjoint.

| Configuration | Agents | Debate rounds |
|---|---:|---:|
| Baseline | 1 | 0 |
| A (formerly D) | 3 | 1 |
| B (formerly E) | 3 | 2 |
| C (formerly F) | 3 | 3 |

## Setup

Unzip the project and open a terminal in the AI_LLM_Project folder. Use the
Python environment from the original project, or create one and install the

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Try the workflow offline

```bash
python run_pilot.py --cap 1
python debate.py analyze --out runs/mock_pilot
python run_final.py --cap 5
python debate.py analyze --out runs/mock_final
```

These commands use synthetic responses and verify the workflow. Mock outputs
cannot measure real model validity, disagreement, truncation, cost, or accuracy.

## Run the live pilot after approval

Copy the verified API settings from the previous project into a local `.env`
file in this folder. Use `.env.example` for the required variable names.
Keep your API key private. Set a USD budget you approve with `--cap`.
For example, if your approved pilot budget is USD 1, run:

```bash
python run_pilot.py --live --cap 1
python debate.py analyze --out runs/pilot
```

The default output cap is 4,096 tokens per response. `--max-tokens` overrides
it for a new run. To resume, use the same manifest, settings, and output folder.
You can raise the USD budget without invalidating the checkpoint. A changed
token cap or prompt requires a fresh run directory.

Check that the pilot reports 24 question-configuration records and 168 saved
completions. Open `runs/pilot/analysis/stage_audit.csv` to review invalid and
truncated counts, token usage, valid-response accuracy, and disagreements.
Open `results.json` to inspect examples of disagreeing peers and the original
response text. A unanimous pilot leaves the disagreement check inconclusive.
Use `run_totals.json` to review the estimated spend and recorded active
runtime. The pilot is small, so treat the rates as a readiness check.

## Run the live final after reviewing the pilot and approving the full run

Use the same model, prompts, and output-token cap as in the approved pilot.
Choose an approved full-run USD budget. For example, for an approved USD 10 cap:

```bash
python run_final.py --live --cap 10
python debate.py analyze --out runs/final
```

Expect 400 completed question-configuration records and 2,800 saved
completions. Cost is estimated from recorded usage and configured prices.
Transport retries may incur charges absent from the saved completions.
If the budget guard stops the run, rerun the same command with a higher
approved budget to resume from the SQLite checkpoint.

## V1 to V2

- Added a one-agent baseline and renamed debate configurations A, B, and C.
- Kept independent initial answers, previous-stage-only debate context, and
  strict majority voting across all configured agent slots.
- Added dataset-specific prompts in prompts.json and a configurable output
  cap shared by pilot and final.
- Audit every response before voting. Abnormal finishes, missing or duplicate
  final-answer lines, malformed answers, and unavailable options are invalid.
  Raw text is saved. Invalid answers contribute no vote and remain in all
  primary denominators. An unresolved vote counts as incorrect.
- Preserved Wilson intervals, accuracy, error rates, and cost summaries.
  McNemar tests compare each debate configuration against the paired baseline.
  Added stage validity and truncation statistics, token distributions,
  disagreement counts, and three-status transition tables.
- The analysis compares questions with all four configurations complete.
  Stage rates are fractions. Summary accuracy and resolved-vote accuracy
  are percentages. Runtime sums recorded active time across invocations and
  can omit time after the last checkpoint if interrupted.
- Pilot, final, and offline runs use separate folders under runs.
