"""Generate five charts from saved results. No API calls."""
import argparse
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, MaxNLocator

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--results", type=Path, default=Path("runs/final/results.json"))
parser.add_argument("--out", type=Path, default=Path("charts"))
args = parser.parse_args()
data = json.loads(args.results.read_text(encoding="utf-8"))
systems = ("Baseline", "A", "B", "C")
datasets = {"mmlu": "MMLU-Pro", "gsm8k": "GSM8K"}
colors = ("#536582", "#087E91", "#7557AA", "#B54F24")
groups = {(d, s): [] for d in datasets for s in systems}
for row in data["records"]:
    groups[row["dataset"], row["system"]].append(row)
if data.get("mock") or any(len(group) != 50 for group in groups.values()):
    parser.error("Use the completed live V2 final results with 50 records per dataset and system.")

counts = Counter()
accuracy = {}
cost = {}
for (dataset, system), rows in groups.items():
    accuracy[dataset, system] = 100 * sum(row["correct"] for row in rows) / len(rows)
    cost[dataset, system] = sum(row["cost"] for row in rows)
    for row in rows:
        for round_no, (previous, current) in enumerate(zip(row["stages"], row["stages"][1:]), 1):
            for before, after in zip(previous, current):
                counts[dataset, system, round_no, before["correctness"], after["correctness"]] += 1

args.out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})

def panels(title, note=None):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5), sharey=True)
    fig.suptitle(title, fontsize=18, fontweight="bold", y=.98)
    fig.subplots_adjust(left=.09, right=.96, bottom=.19, top=.78, wspace=.22)
    for ax, name in zip(axes, datasets.values()):
        ax.set_title(name, fontweight="bold", pad=9)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#DFE5EB")
    if note:
        fig.text(.5, .025, note, ha="center", fontsize=9)
    return fig, axes

def save(fig, name):
    path = args.out / (name + ".png")
    fig.savefig(path, dpi=250, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(path)

def transition_bars(by_round):
    title = "Corrections and new errors by debate round" if by_round else "Transition of answers by configuration"
    note = ("Round 1 pools A, B, and C. Round 2 pools B and C. Round 3 uses C."
            if by_round else "Each configuration includes all its debate rounds. Baseline has no debate.")
    fig, axes = panels(title, note)
    labels = ["Round 1\n450 comparisons", "Round 2\n300 comparisons", "Round 3\n150 comparisons"] if by_round else ["A", "B", "C"]
    maximum = 0
    for dataset, ax in zip(datasets, axes):
        for offset, before, after, color in [
            (-.18, "wrong", "correct", "#087E91"),
            (.18, "correct", "wrong", "#B54F24"),
        ]:
            values = [
                sum(counts[dataset, s, r, before, after] for s in systems)
                if by_round else sum(counts[dataset, s, r, before, after] for r in (1, 2, 3))
                for r, s in enumerate(systems[1:], 1)
            ]
            maximum = max(maximum, *values)
            bars = ax.bar([i + offset for i in range(3)], values, width=.34,
                          color=color, label=f"{before.title()} → {after.title()}")
            ax.bar_label(bars, padding=3, color=color, fontweight="bold")
        ax.set_xticks(range(3), labels)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    axes[0].set_ylim(0, max(3, maximum * 1.22))
    axes[0].set_ylabel("Agent transitions")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .91),
               ncol=2, frameon=False)
    save(fig, "corrections_by_round" if by_round else "answer_transitions_by_configuration")

transition_bars(True)
transition_bars(False)

fig, axes = panels("Cumulative accuracy by number of questions",
                   "Questions follow saved run order. Labels show accuracy after question 50.")
for dataset, ax in zip(datasets, axes):
    endpoints = []
    for system, color in zip(systems, colors):
        correct = 0
        values = []
        for i, row in enumerate(groups[dataset, system], 1):
            correct += row["correct"]
            values.append(100 * correct / i)
        ax.plot(range(1, 51), values, color=color, label=system, linewidth=2)
        endpoints.append((values[-1], system, color))
    label_y = 0
    for value, system, color in sorted(endpoints):
        label_y = max(value, label_y + 5)
        ax.annotate(f"{system} {value:.0f}%", xy=(50, value), xytext=(53, label_y),
                    fontsize=9, color=color, va="center",
                    arrowprops={"arrowstyle": "-", "color": color, "lw": .8})
    ax.set(xlim=(1, 66), ylim=(0, 115), xlabel="Questions evaluated")
    ax.yaxis.set_major_formatter(PercentFormatter(100))
axes[0].set_ylabel("Cumulative accuracy")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .91),
           ncol=4, frameon=False)
save(fig, "cumulative_accuracy")

fig, axes = panels("API cost vs. accuracy",
                   "Each point covers 50 questions. Cost is estimated from recorded API usage.")
max_cost = max(cost.values())
for dataset, ax in zip(datasets, axes):
    offsets = ((0, 12), (0, -19), (0, 14), (0, -19))
    if dataset == "gsm8k":
        offsets = ((0, 14), (-8, -18), (0, 18), (11, -46))
    for (system, color), offset in zip(zip(systems, colors), offsets):
        x, y = cost[dataset, system], accuracy[dataset, system]
        ax.scatter(x, y, color=color, s=65, zorder=3)
        ax.annotate(f"{system}\n{y:.0f}% · ${x:.3f}", (x, y),
                    xytext=offset, textcoords="offset points",
                    ha="center", va="bottom" if offset[1] > 0 else "top",
                    fontsize=9, color=color,
                    arrowprops={"arrowstyle": "-", "color": color, "lw": .7,
                                "shrinkB": 5})
    ax.set(xlim=(-max_cost*.09, max_cost*1.2), ylim=(75, 103), xlabel="Estimated cost (USD)")
    ax.yaxis.set_major_formatter(PercentFormatter(100))
axes[0].set_ylabel("Accuracy")
save(fig, "api_cost_vs_accuracy")

fig, axes = panels("Accuracy by configuration", "Each bar represents 50 questions.")
for dataset, ax in zip(datasets, axes):
    bars = ax.bar(systems, [accuracy[dataset, s] for s in systems], color=colors)
    ax.bar_label(bars, fmt="%.0f%%", padding=4, fontweight="bold")
    ax.set_ylim(0, 107)
    ax.yaxis.set_major_formatter(PercentFormatter(100))
axes[0].set_ylabel("Accuracy")
save(fig, "accuracy_by_configuration")
