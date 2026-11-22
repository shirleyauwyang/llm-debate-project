
import json
import math
from collections import defaultdict

# Load experiment results
with open("runs_v2/final/results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

records = data["records"]

# 95% Wilson confidence interval
def wilson_ci(correct, total, z=1.96):
    if total == 0:
        return 0.0, 0.0

    p = correct / total
    z2 = z ** 2

    denominator = 1 + z2 / total

    center = (p + z2 / (2 * total)) / denominator

    margin = (
        z
        * math.sqrt(
            p * (1 - p) / total
            + z2 / (4 * total ** 2)
        )
        / denominator
    )

    return center - margin, center + margin


# Group results by dataset and system
groups = defaultdict(list)

for record in records:
    dataset = record["dataset"]
    system = record["system"]

    groups[("All Datasets", system)].append(record)

    if dataset == "mmlu":
        dataset = "MMLU-Pro"
    elif dataset == "gsm8k":
        dataset = "GSM8K"

    groups[(dataset, system)].append(record)


# Display results
systems = ["Baseline", "A", "B", "C"]
datasets = ["All Datasets", "GSM8K", "MMLU-Pro"]

print(
    f"{'Dataset':<16}"
    f"{'System':<12}"
    f"{'Accuracy':>12}"
    f"{'95% CI Lower':>16}"
    f"{'95% CI Upper':>16}"
)

print("-" * 72)

for dataset in datasets:
    for system in systems:
        group = groups[(dataset, system)]

        total = len(group)
        correct = sum(r["correct"] for r in group)

        accuracy = correct / total
        lower, upper = wilson_ci(correct, total)

        print(
            f"{dataset:<16}"
            f"{system:<12}"
            f"{accuracy:>11.2%}"
            f"{lower:>16.2%}"
            f"{upper:>16.2%}"
        )