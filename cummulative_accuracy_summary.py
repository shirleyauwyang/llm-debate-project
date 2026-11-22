
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

SYSTEMS = ["Baseline", "A", "B", "C"]
DATASETS = ["gsm8k", "mmlu"]
CHECKPOINTS = [13, 18, 19, 25, 45, 50]


def save_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


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
        raise ValueError("Mock results are not allowed.")

    # Preserve the question order from the experiment file.
    question_order = defaultdict(list)
    seen_ids = defaultdict(set)
    answers = defaultdict(dict)

    for record in data["records"]:
        dataset = record["dataset"]
        system = record["system"]
        question_id = str(record["id"])

        if dataset not in DATASETS or system not in SYSTEMS:
            continue

        if question_id not in seen_ids[dataset]:
            seen_ids[dataset].add(question_id)
            question_order[dataset].append(question_id)

        key = (dataset, system)
        if question_id in answers[key]:
            raise ValueError(f"Duplicate result: {key}, {question_id}")

        if not isinstance(record["correct"], bool):
            raise ValueError(f"Invalid correctness: {key}, {question_id}")

        answers[key][question_id] = record["correct"]

    cumulative_rows = []
    checkpoint_rows = []
    final_rows = []
    divergence_rows = []

    for dataset in DATASETS:
        ids = question_order[dataset]

        if len(ids) != 50:
            raise ValueError(f"{dataset}: expected 50 questions, got {len(ids)}")

        cumulative = {}

        for system in SYSTEMS:
            key = (dataset, system)

            if set(answers[key]) != set(ids):
                raise ValueError(f"Missing or extra questions for {key}")

            correct_so_far = 0
            cumulative[system] = []

            for question_number, question_id in enumerate(ids, start=1):
                is_correct = answers[key][question_id]

                correct_so_far += int(is_correct)
                accuracy = 100 * correct_so_far / question_number

                cumulative[system].append(accuracy)

                row = {
                    "dataset": dataset,
                    "system": system,
                    "question_number": question_number,
                    "question_id": question_id,
                    "correct": int(is_correct),
                    "cumulative_correct": correct_so_far,
                    "cumulative_errors": question_number - correct_so_far,
                    "cumulative_accuracy_pct": round(accuracy, 4),
                    "cumulative_error_pct": round(100 - accuracy, 4),
                }

                cumulative_rows.append(row)

                if question_number in CHECKPOINTS:
                    checkpoint_rows.append(row.copy())

            final_rows.append({
                "dataset": dataset,
                "system": system,
                "total_questions": len(ids),
                "correct_answers": correct_so_far,
                "final_accuracy_pct": round(cumulative[system][-1], 4),
            })

        # First question where cumulative accuracy differs.
        for system_a, system_b in [
            ("A", "B"),
            ("B", "C"),
            ("A", "C"),
        ]:
            first_difference = next(
                (
                    i + 1
                    for i, (a, b) in enumerate(
                        zip(cumulative[system_a], cumulative[system_b])
                    )
                    if abs(a - b) > 1e-9
                ),
                None
            )

            divergence_rows.append({
                "dataset": dataset,
                "system_a": system_a,
                "system_b": system_b,
                "first_cumulative_difference_question": first_difference,
            })

    args.out.mkdir(parents=True, exist_ok=True)

    save_csv(
        args.out / "cumulative_accuracy.csv",
        cumulative_rows,
        list(cumulative_rows[0])
    )
    save_csv(
        args.out / "accuracy_checkpoints.csv",
        checkpoint_rows,
        list(checkpoint_rows[0])
    )
    save_csv(
        args.out / "final_accuracy_summary.csv",
        final_rows,
        list(final_rows[0])
    )
    save_csv(
        args.out / "first_divergence.csv",
        divergence_rows,
        list(divergence_rows[0])
    )

    print("\nFINAL ACCURACY")
    for row in final_rows:
        print(
            f"{row['dataset']:6} | {row['system']:8} | "
            f"{row['final_accuracy_pct']:.2f}%"
        )

    print("\nFIRST CUMULATIVE DIFFERENCE")
    for row in divergence_rows:
        print(
            f"{row['dataset']:6} | "
            f"{row['system_a']} vs {row['system_b']} | "
            f"Question {row['first_cumulative_difference_question']}"
        )

    print(f"\nCSV files saved to: {args.out.resolve()}")


if __name__ == "__main__":
    main()