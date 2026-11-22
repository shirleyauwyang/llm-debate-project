
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

SYSTEM_NAMES = {
    "Baseline": "Baseline",
    "A": "Model 1",
    "B": "Model 2",
    "C": "Model 3",
}

EXPECTED_STAGES = {
    "Baseline": 1,
    "A": 2,
    "B": 3,
    "C": 4,
}


def save_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def answer_status(agent):
    status = agent.get("correctness")

    if status == "correct":
        return "Correct"
    if status == "wrong":
        return "Wrong"
    if status == "invalid":
        return "Invalid"

    raise ValueError(f"Unexpected correctness status: {status}")


def transition_name(before, after):
    return f"{before} -> {after}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("runs/final/results.json")
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("final_analysis")
    )
    args = parser.parse_args()

    with args.results.open(encoding="utf-8") as f:
        data = json.load(f)

    if data.get("mock"):
        raise ValueError("Expected real experiment results, not mock data.")

    transition_counts = Counter()
    stage_counts = Counter()
    validity_counts = Counter()
    record_counts = Counter()

    for record in data["records"]:
        dataset = record["dataset"]
        system = record["system"]

        if system not in SYSTEM_NAMES:
            continue

        stages = record["stages"]
        record_counts[(dataset, system)] += 1

        if len(stages) != EXPECTED_STAGES[system]:
            raise ValueError(
                f"Unexpected stage count for {dataset}/{system}/"
                f"{record['id']}: {len(stages)}"
            )

        expected_agents = 1 if system == "Baseline" else 3

        for stage_index, stage in enumerate(stages):
            if len(stage) != expected_agents:
                raise ValueError(
                    f"Unexpected agent count for {dataset}/{system}/"
                    f"{record['id']} at stage {stage_index}"
                )

            for agent in stage:
                status = answer_status(agent)
                stage_counts[
                    (dataset, system, stage_index, status)
                ] += 1

                if status == "Invalid":
                    reason = agent.get("invalid_reason") or "unknown"
                    validity_counts[
                        (dataset, system, stage_index, "invalid", reason)
                    ] += 1

                if agent.get("finish") == "length":
                    validity_counts[
                        (dataset, system, stage_index, "truncated", "length")
                    ] += 1

        # Compare each agent to the same agent in the previous stage.
        for stage_index in range(1, len(stages)):
            previous_stage = stages[stage_index - 1]
            current_stage = stages[stage_index]

            for agent_index in range(expected_agents):
                before = answer_status(previous_stage[agent_index])
                after = answer_status(current_stage[agent_index])

                transition_counts[
                    (
                        dataset,
                        system,
                        stage_index,
                        transition_name(before, after),
                    )
                ] += 1

    for (dataset, system), count in record_counts.items():
        if count != 50:
            raise ValueError(
                f"Expected 50 questions for {dataset}/{system}; got {count}"
            )

    transition_rows = []
    for (dataset, system, round_number, transition), count in sorted(
        transition_counts.items()
    ):
        transition_rows.append({
            "dataset": dataset,
            "system": system,
            "model": SYSTEM_NAMES[system],
            "debate_round": round_number,
            "transition": transition,
            "count": count,
        })

    stage_rows = []
    for (dataset, system, stage, status), count in sorted(
        stage_counts.items()
    ):
        stage_rows.append({
            "dataset": dataset,
            "system": system,
            "model": SYSTEM_NAMES[system],
            "stage": stage,
            "stage_type": "Initial" if stage == 0 else "Debate",
            "status": status,
            "count": count,
        })

    validity_rows = []
    for (dataset, system, stage, issue, reason), count in sorted(
        validity_counts.items()
    ):
        validity_rows.append({
            "dataset": dataset,
            "system": system,
            "model": SYSTEM_NAMES[system],
            "stage": stage,
            "issue": issue,
            "reason": reason,
            "count": count,
        })

    summary_rows = []

    for dataset, system in sorted(record_counts):
        counts = Counter()

        for (d, s, round_number, transition), value in (
            transition_counts.items()
        ):
            if d == dataset and s == system:
                counts[transition] += value

        corrections = counts["Wrong -> Correct"]
        new_errors = counts["Correct -> Wrong"]

        summary_rows.append({
            "dataset": dataset,
            "system": system,
            "model": SYSTEM_NAMES[system],
            "questions": record_counts[(dataset, system)],
            "wrong_to_correct": corrections,
            "correct_to_wrong": new_errors,
            "correct_to_correct": counts["Correct -> Correct"],
            "wrong_to_wrong": counts["Wrong -> Wrong"],
            "invalid_to_correct": counts["Invalid -> Correct"],
            "correct_to_invalid": counts["Correct -> Invalid"],
            "wrong_to_invalid": counts["Wrong -> Invalid"],
            "invalid_to_wrong": counts["Invalid -> Wrong"],
            "invalid_to_invalid": counts["Invalid -> Invalid"],
            "net_valid_corrections": corrections - new_errors,
        })

    args.out.mkdir(parents=True, exist_ok=True)

    save_csv(
        args.out / "agent_transition_counts.csv",
        transition_rows,
        [
            "dataset", "system", "model", "debate_round",
            "transition", "count"
        ],
    )

    save_csv(
        args.out / "agent_stage_status.csv",
        stage_rows,
        [
            "dataset", "system", "model", "stage",
            "stage_type", "status", "count"
        ],
    )

    save_csv(
        args.out / "response_validity_summary.csv",
        validity_rows,
        [
            "dataset", "system", "model", "stage",
            "issue", "reason", "count"
        ],
    )

    save_csv(
        args.out / "transition_summary.csv",
        summary_rows,
        [
            "dataset", "system", "model", "questions",
            "wrong_to_correct", "correct_to_wrong",
            "correct_to_correct", "wrong_to_wrong",
            "invalid_to_correct", "correct_to_invalid",
            "wrong_to_invalid", "invalid_to_wrong",
            "invalid_to_invalid", "net_valid_corrections"
        ],
    )

    print("\nTRANSITION ANALYSIS")
    print("=" * 60)

    for row in summary_rows:
        print(
            f"{row['dataset']:6} | {row['model']:8} | "
            f"Wrong->Correct: {row['wrong_to_correct']:3} | "
            f"Correct->Wrong: {row['correct_to_wrong']:3} | "
            f"Net: {row['net_valid_corrections']:+3}"
        )

    print(f"\nSaved four CSV files to: {args.out.resolve()}")


if __name__ == "__main__":
    main()