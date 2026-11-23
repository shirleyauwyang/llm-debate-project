# Multi-Agent LLM Debate Experiment

## 1. Project Overview

This project investigates how multi-agent debate affects the accuracy, reliability, and computational cost of Large Language Models (LLMs).

The experiment compares a single-agent baseline against multi-agent systems with different numbers of debate rounds. Two datasets, MMLU-Pro and GSM8K, are used to evaluate model performance across different configurations.

The system incorporates independent initial responses, structured debate stages, response auditing, and strict majority voting to examine how answers evolve throughout the debate process.

## 2. Experimental Design

### Datasets

| Dataset | Pilot Questions | Final Questions |
|---|---:|---:|
| MMLU-Pro | 3 | 50 |
| GSM8K | 3 | 50 |
| **Total** | **6** | **100** |

Pilot and final samples are disjoint. Saved question manifests and random seeds support reproducibility.

### Model Configurations

| Configuration | Agents | Debate Rounds |
|---|---:|---:|
| Baseline | 1 | 0 |
| A | 3 | 1 |
| B | 3 | 2 |
| C | 3 | 3 |

The baseline generates an independent answer without debate. The other configurations use three agents that exchange responses across the specified number of debate rounds.

## 3. Experimental Development and Version History

The project underwent two experimental iterations as the experimental design was refined.

### Version 1 (V1) – Original Experiment

The initial experiment used three multi-agent configurations: D, E, and F. These configurations were part of the original experimental design and were used during the earlier pilot phase.

The original pilot analysis results are retained in `results/v1/analysis/` for documentation and reference.

### Version 2 (V2) – Revised Experiment

The experimental design was subsequently revised to provide a clearer comparison between single-agent and multi-agent systems.

V2 introduced four configurations:

- **Baseline:** One agent with no debate.
- **A:** Three agents with one debate round.
- **B:** Three agents with two debate rounds.
- **C:** Three agents with three debate rounds.

The final experiment used V2 across MMLU-Pro and GSM8K, with 50 questions per dataset (100 questions in total).

V2 results, statistical analyses, and visualizations are stored separately from V1 to maintain a clear distinction between the two experimental designs.

Results from V1 and V2 are treated as separate experimental iterations and are not directly combined.

## 4. System Design and Evaluation

### Response Generation and Debate

- Each agent generates an independent initial answer.
- Agents can access previous-stage responses and discussion during subsequent debate rounds.
- Dataset-specific prompts are defined in `prompts.json`.
- A configurable output-token limit is shared across pilot and final experiments.

### Response Auditing and Voting

Every response is audited before voting.

Responses are considered invalid when they contain issues such as abnormal finish reasons, missing or duplicate final-answer lines, malformed answers, or unavailable answer options.

- Original response text is preserved.
- Invalid responses do not contribute votes.
- Invalid responses remain in the primary accuracy denominators.
- Strict majority voting is applied across all configured agent slots.
- An unresolved vote is counted as incorrect.

### Statistical Analysis

The project evaluates model performance and reliability through:

- Accuracy and error rates.
- 95% Wilson confidence intervals.
- McNemar's tests comparing each debate configuration against the paired baseline.
- Stage-level response validity and truncation statistics.
- Token usage and API cost summaries.
- Agent disagreement counts.
- Answer transition tables showing changes across debate stages.

The analysis compares questions for which all four configurations have completed results.

Stage rates are expressed as fractions, while summary accuracy and resolved-vote accuracy are expressed as percentages.

Runtime represents recorded active time across invocations and may omit time after the last checkpoint if an experiment is interrupted.

## 5. Installation and Setup

Open a terminal in the project folder.

Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required dependencies:

```bash
python -m pip install -r requirements.txt
```

## 6. Running Experiments

### 6.1 Offline Testing

The experiment runs in mock mode by default. The following commands test the workflow using synthetic responses without making live API calls.

```bash
python run_pilot.py --cap 1
python debate.py analyze --out runs/mock_pilot

python run_final.py --cap 5
python debate.py analyze --out runs/mock_final
```

Mock outputs are intended for workflow testing only. They cannot measure real model validity, disagreement, truncation, cost, or accuracy.

### 6.2 Live Pilot Experiment

Before running a live experiment:

1. Configure the required API credentials and model settings in a local `.env` file.
2. Verify the model configuration and API pricing settings.
3. Keep API credentials private.
4. Choose an approved USD spending limit using `--cap`.

For example, with an approved USD 1 budget:

```bash
python run_pilot.py --live --cap 1
python debate.py analyze --out runs/pilot
```

The default output-token cap is 4,096 tokens per response. Use `--max-tokens` to override it for a new run.

To resume an interrupted experiment, use the same manifest, settings, and output folder.

The USD budget can be increased without invalidating the existing checkpoint. However, changing the token cap or prompt requires a fresh run directory.

### Pilot Evaluation

The pilot is expected to produce:

- 24 completed question-configuration records.
- 168 saved completions.

Review the following files:

**Note:** The files listed below are generated locally when an experiment is executed and analyzed. They are not all included in the GitHub repository. The repository contains selected aggregate pilot analysis tables under `pilot/analysis/`, while complete experiment outputs, raw responses, API call logs, and checkpoints are kept locally or shared privately.

| File | Purpose |
|---|---|
| `runs/pilot/results.json` | Saved experiment results and original responses |
| `runs/pilot/calls.jsonl` | Individual API call records and responses |
| `runs/pilot/analysis/summary.csv` | Accuracy and performance summaries |
| `runs/pilot/analysis/stage_audit.csv` | Invalid and truncated responses, token usage, and response validity |
| `runs/pilot/analysis/transitions.csv` | Answer transitions |
| `runs/pilot/analysis/agent_answer_transitions.csv` | Individual agent answer changes |
| `runs/pilot/analysis/transition_counts.csv` | Transition counts |
| `runs/pilot/analysis/voting.csv` | Final voting outcomes |
| `runs/pilot/analysis/run_totals.json` | Estimated spending and recorded active runtime |
| `runs/pilot/analysis/findings.md` | Automated analysis findings |

The analysis may also generate `mcnemar.csv` when statistical comparisons are available.

A unanimous pilot leaves the disagreement check inconclusive.

Since the pilot uses a small sample, its results should be treated as a readiness check rather than conclusive evidence of model performance.

### 6.3 Live Final Experiment

Run the final experiment only after reviewing the pilot and approving the full-run budget.

Use the same model, prompts, and output-token cap as the approved pilot.

For example, with an approved USD 10 budget:

```bash
python run_final.py --live --cap 10
python debate.py analyze --out runs/final
```

The final experiment is expected to produce:

- 400 completed question-configuration records.
- 2,800 saved completions.

Cost is estimated using recorded API usage and configured prices. Transport retries may incur additional charges that are not reflected in saved completions.

If the budget guard stops the experiment, rerun the same command with a higher approved budget to resume from the SQLite checkpoint.

## 7. Reproducibility and Data Management

Experiment reproducibility is supported through:

- Saved pilot and final question manifests.
- Recorded random seeds.
- Fixed dataset revisions and fingerprints.
- Consistent prompts and model configurations.
- Checkpoint-based experiment resumption.
- Recorded token usage and API cost estimates.

Keep API credentials, virtual environments, checkpoints, and raw experiment outputs out of the repository.

Pilot, final, and offline experiments use separate output folders under `runs/`.

## 8. Project Structure

```text
llm-debate-project/
│
├── debate.py
├── audit.py
├── analysis.py
├── confidence_interval.py
├── cumulative_accuracy.py
├── transition_analysis.py
├── create_charts.py
│
├── run_pilot.py
├── run_final.py
│
├── prompts.json
├── pilot_manifest.json
├── final_manifest.json
│
├── requirements.txt
├── requirements-lock.txt
├── .gitignore
├── README.md
│
└── results/
    │
    ├── v1/
    │   └── analysis/
    │       ├── summary.csv
    │       ├── transitions.csv
    │       └── voting.csv
    │
    └── v2/
        │
        ├── pilot/
        │   └── analysis/
        │       └── stage_audit.csv
        │
        ├── final/
        │   └── analysis/
        │       ├── summary.csv
        │       ├── mcnemar.csv
        │       ├── transitions.csv
        │       ├── agent_answer_transitions.csv
        │       ├── transition_counts.csv
        │       ├── stage_audit.csv
        │       ├── voting.csv
        │       ├── run_totals.json
        │       └── findings.md
        │
        └── charts/
            ├── accuracy_by_configuration.png
            ├── answer_transitions_by_configuration.png
            ├── api_cost_vs_accuracy.png
            ├── corrections_by_round.png
            └── cumulative_accuracy.png
```

**Note:** Raw experiment outputs, API logs, checkpoints, and other temporary files may be maintained separately from the published analysis files.

## 9. Acknowledgements

This project was developed as part of a university assignment exploring multi-agent LLM systems, collaborative reasoning, and the evaluation of debate-based approaches.