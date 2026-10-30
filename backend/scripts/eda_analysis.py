"""Validate and visualize the supplied/synthetic Vakta metadata dataset.

Run from the repository root with the backend environment active:
    python backend/scripts/eda_analysis.py
Outputs are saved in backend/outputs/eda. The script does not modify source datasets.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/vakta-matplotlib-cache")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "backend/data/dataset.csv"
ORIGINAL = ROOT / "backend/data/dataset-original-500.csv"
DICTIONARY = ROOT / "backend/data/data_dictionary.csv"
OUTPUT = ROOT / "backend/outputs/eda"
EXPECTED_COLUMNS = [
    "session_id", "user_query_type", "intent", "confidence_score", "escalated", "user_rating"
]
INTENTS = ["admissions", "schedule", "fees", "exams", "grievance", "hostel", "library"]
QUERY_TYPES = [f"query_type_{i}" for i in range(1, 6)]
EXPECTED_TOTAL = 5_000
EXPECTED_ORIGINAL = 500


class DatasetError(ValueError):
    pass


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise DatasetError(f"Required dataset file is missing: {path.relative_to(ROOT)}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    return fields, rows


def quantile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def run_eda() -> dict[str, Any]:
    fields, rows = load_csv(DATASET)
    source_fields, source_rows = load_csv(ORIGINAL)
    if fields != EXPECTED_COLUMNS:
        raise DatasetError(f"dataset.csv schema mismatch: expected {EXPECTED_COLUMNS}, got {fields}")
    if source_fields != EXPECTED_COLUMNS:
        raise DatasetError(f"source schema mismatch: expected {EXPECTED_COLUMNS}, got {source_fields}")
    if len(rows) != EXPECTED_TOTAL:
        raise DatasetError(f"Expected {EXPECTED_TOTAL} working records, found {len(rows)}")
    if len(source_rows) != EXPECTED_ORIGINAL:
        raise DatasetError(f"Expected {EXPECTED_ORIGINAL} original records, found {len(source_rows)}")

    original_preserved = rows[:EXPECTED_ORIGINAL] == source_rows
    if not original_preserved:
        raise DatasetError("The first 500 records in dataset.csv differ from dataset-original-500.csv")

    missing_cells = sum(not (row.get(column) or "").strip() for row in rows for column in EXPECTED_COLUMNS)
    session_ids = [row["session_id"] for row in rows]
    duplicate_ids = len(session_ids) - len(set(session_ids))
    duplicate_rows = len(rows) - len({tuple(row.get(column, "") for column in EXPECTED_COLUMNS) for row in rows})
    expected_ids = [f"S{index:04d}" for index in range(1, EXPECTED_TOTAL + 1)]
    sequential_ids = session_ids == expected_ids
    bad_intents = sorted({row["intent"] for row in rows} - set(INTENTS))
    bad_query_types = sorted({row["user_query_type"] for row in rows} - set(QUERY_TYPES))
    bad_escalated = sorted({row["escalated"] for row in rows} - {"0", "1"})
    bad_ratings = sorted({row["user_rating"] for row in rows} - {"1", "2", "3", "4", "5"})

    confidence: list[float] = []
    bad_confidence_rows: list[str] = []
    for row in rows:
        try:
            value = float(row["confidence_score"])
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError
            confidence.append(value)
        except (TypeError, ValueError):
            bad_confidence_rows.append(row.get("session_id", "unknown"))
    if len(confidence) != len(rows):
        raise DatasetError(f"Invalid confidence values in {len(bad_confidence_rows)} rows")

    dictionary_fields: list[str] = []
    dictionary_placeholders: list[str] = []
    if DICTIONARY.exists():
        _, dictionary_rows = load_csv(DICTIONARY)
        dictionary_fields = [row.get("column_name", "") for row in dictionary_rows]
        dictionary_placeholders = [
            row.get("column_name", "") for row in dictionary_rows
            if not row.get("description", "").strip()
            or any(token in row.get("description", "").casefold() for token in ("fill in", "todo", "placeholder"))
        ]
    dictionary_complete = set(dictionary_fields) == set(EXPECTED_COLUMNS) and not dictionary_placeholders

    sorted_confidence = sorted(confidence)
    q1 = quantile(sorted_confidence, 0.25)
    q3 = quantile(sorted_confidence, 0.75)
    iqr = q3 - q1
    outlier_count = sum(value < q1 - 1.5 * iqr or value > q3 + 1.5 * iqr for value in confidence)
    confidence_stats = {
        "count": len(confidence),
        "min": round(min(confidence), 4),
        "max": round(max(confidence), 4),
        "mean": round(statistics.mean(confidence), 4),
        "median": round(statistics.median(confidence), 4),
        "stdev_population": round(statistics.pstdev(confidence), 4),
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr_1_5_outlier_count": outlier_count,
    }

    intent_counts = Counter(row["intent"] for row in rows)
    query_type_counts = Counter(row["user_query_type"] for row in rows)
    escalation_counts = Counter(row["escalated"] for row in rows)
    rating_counts = Counter(row["user_rating"] for row in rows)
    escalation_by_intent: dict[str, dict[str, int | float]] = {}
    for intent in INTENTS:
        group = [row for row in rows if row["intent"] == intent]
        escalated_n = sum(row["escalated"] == "1" for row in group)
        escalation_by_intent[intent] = {
            "records": len(group),
            "escalated": escalated_n,
            "rate": round(escalated_n / len(group), 4) if group else 0.0,
        }
    split = {
        "original_500": rows[:EXPECTED_ORIGINAL],
        "synthetic_4500": rows[EXPECTED_ORIGINAL:],
    }
    group_metrics: dict[str, dict[str, Any]] = {}
    for name, group in split.items():
        group_metrics[name] = {
            "rows": len(group),
            "escalated": sum(row["escalated"] == "1" for row in group),
            "escalation_rate": round(sum(row["escalated"] == "1" for row in group) / len(group), 4),
            "mean_confidence": round(statistics.mean(float(row["confidence_score"]) for row in group), 4),
            "rating_distribution": dict(sorted(Counter(row["user_rating"] for row in group).items())),
        }

    quality = {
        "expected_six_column_schema": fields == EXPECTED_COLUMNS,
        "original_500_value_rows_preserved": original_preserved,
        "original_row_count": len(source_rows),
        "combined_row_count": len(rows),
        "synthetic_row_count": len(rows) - EXPECTED_ORIGINAL,
        "missing_cells": missing_cells,
        "duplicate_session_ids": duplicate_ids,
        "duplicate_full_rows": duplicate_rows,
        "session_ids_sequential_S0001_to_S5000": sequential_ids,
        "invalid_intents": bad_intents,
        "invalid_query_types": bad_query_types,
        "invalid_escalated_values": bad_escalated,
        "invalid_ratings": bad_ratings,
        "invalid_confidence_rows": bad_confidence_rows,
        "data_dictionary_covers_columns_without_placeholders": dictionary_complete,
    }
    if any((missing_cells, duplicate_ids, duplicate_rows, not sequential_ids, bad_intents, bad_query_types, bad_escalated, bad_ratings, bad_confidence_rows)):
        raise DatasetError("Dataset quality checks failed; see EDA summary details before proceeding")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.titleweight": "bold", "axes.edgecolor": "#d5dfe3",
        "axes.labelcolor": "#43565f", "text.color": "#23343b",
        "xtick.color": "#53666d", "ytick.color": "#53666d",
        "axes.grid": True, "grid.color": "#eaf0f2", "grid.linewidth": 0.8,
        "figure.facecolor": "white", "axes.facecolor": "white",
    })

    ordered_intents = sorted(INTENTS, key=lambda item: intent_counts[item])
    fig, ax = plt.subplots(figsize=(9.5, 5.4), constrained_layout=True)
    bars = ax.barh(ordered_intents, [intent_counts[item] for item in ordered_intents], color="#287f88")
    ax.set_title("Intent distribution", loc="left", pad=14)
    ax.set_xlabel("Records (original 500 + synthetic 4,500)")
    ax.set_ylabel("")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    for bar, intent in zip(bars, ordered_intents):
        count = intent_counts[intent]
        ax.text(bar.get_width() + max(rows.__len__() * 0.004, 1), bar.get_y() + bar.get_height() / 2,
                f"{count:,}  ({count / len(rows):.1%})", va="center", color="#42565d", fontsize=9)
    ax.set_xlim(0, max(intent_counts.values()) * 1.28)
    fig.savefig(OUTPUT / "01_intent_distribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 5.4), constrained_layout=True)
    ax.hist(confidence, bins=20, range=(0, 1), color="#3b9890", edgecolor="white", linewidth=0.8)
    ax.axvline(confidence_stats["mean"], color="#b45f4b", linestyle="--", linewidth=1.8,
               label=f"Mean {confidence_stats['mean']:.3f}")
    ax.set_title("Classifier confidence-score distribution", loc="left", pad=14)
    ax.set_xlabel("Rule-based confidence score")
    ax.set_ylabel("Record count")
    ax.legend(frameon=False)
    fig.savefig(OUTPUT / "02_confidence_distribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.2), constrained_layout=True)
    rates = [100 * float(escalation_by_intent[intent]["rate"]) for intent in INTENTS]
    colors = ["#d07b60" if intent == "grievance" else "#528895" for intent in INTENTS]
    bars = ax1.bar(INTENTS, rates, color=colors)
    ax1.set_title("Escalated flag by intent", loc="left", pad=12)
    ax1.set_ylabel("Share of records (%)")
    ax1.tick_params(axis="x", rotation=35)
    ax1.grid(axis="y")
    ax1.grid(axis="x", visible=False)
    for bar, value in zip(bars, rates):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4, f"{value:.1f}%", ha="center", fontsize=8)
    rating_labels = ["1", "2", "3", "4", "5"]
    rating_values = [rating_counts.get(label, 0) for label in rating_labels]
    bars2 = ax2.bar(rating_labels, rating_values, color="#d0a64f")
    ax2.set_title("Rating values in the dataset", loc="left", pad=12)
    ax2.set_xlabel("Rating (1–5)")
    ax2.set_ylabel("Record count")
    ax2.grid(axis="y")
    ax2.grid(axis="x", visible=False)
    for bar, value in zip(bars2, rating_values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(rating_values) * 0.015,
                 f"{value:,}", ha="center", fontsize=8)
    fig.savefig(OUTPUT / "03_escalation_and_feedback.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 5.1), constrained_layout=True)
    bars = ax.bar([f"Type {i}" for i in range(1, 6)], [query_type_counts[item] for item in QUERY_TYPES], color="#5b8f6a")
    ax.set_title("Operational query-type distribution", loc="left", pad=14)
    ax.set_ylabel("Record count")
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    for bar, key in zip(bars, QUERY_TYPES):
        value = query_type_counts[key]
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(query_type_counts.values()) * 0.015,
                f"{value:,}\n{value / len(rows):.1%}", ha="center", fontsize=8)
    fig.savefig(OUTPUT / "04_query_type_distribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    summary: dict[str, Any] = {
        "dataset_file": "backend/data/dataset.csv",
        "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "source_file": "backend/data/dataset-original-500.csv",
        "source_sha256": hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
        "source_schema": fields,
        "official_brief_schema_note": "The brief lists user_query and bot_response, which the supplied CSV did not capture. No values were fabricated; see HCL_BRIEF_SCHEMA_CROSSWALK.csv.",
        "quality": quality,
        "confidence": confidence_stats,
        "intent_counts": dict(sorted(intent_counts.items())),
        "query_type_counts": dict(sorted(query_type_counts.items())),
        "escalation_counts": dict(sorted(escalation_counts.items())),
        "rating_counts": dict(sorted(rating_counts.items())),
        "escalation_by_intent": escalation_by_intent,
        "source_groups": group_metrics,
        "anomaly_interpretation": (
            "No anomaly indicator is stored in the CSV. The generator has a 3% internal branch that can alter an escalation draw, "
            "but the selected rows are not tagged; the EDA reports only measurable data-quality checks and a Tukey IQR count for confidence."
        ),
        "visualizations": [
            "01_intent_distribution.png", "02_confidence_distribution.png",
            "03_escalation_and_feedback.png", "04_query_type_distribution.png",
        ],
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    total_escalated = escalation_counts.get("1", 0)
    summary_text = [
        "Vakta dataset EDA and validation",
        "=================================",
        f"Rows: {len(rows):,} total; {EXPECTED_ORIGINAL:,} supplied source + {len(rows) - EXPECTED_ORIGINAL:,} synthetic metadata rows.",
        f"Schema: {', '.join(fields)} ({len(fields)} columns).",
        f"Original field values preserved: {original_preserved}.",
        f"Dataset SHA-256: {summary['dataset_sha256']}",
        "",
        "Data-quality checks:",
        f"  Missing cells: {missing_cells}; duplicate IDs: {duplicate_ids}; duplicate full rows: {duplicate_rows}.",
        f"  Sequential IDs S0001–S5000: {sequential_ids}; dictionary complete: {dictionary_complete}.",
        f"  Invalid intent/query type/escalation/rating values: {len(bad_intents)}/{len(bad_query_types)}/{len(bad_escalated)}/{len(bad_ratings)}.",
        f"  Invalid confidence rows: {len(bad_confidence_rows)}; Tukey 1.5×IQR confidence outliers: {outlier_count}.",
        "",
        "Observed dataset aggregates (not live application performance):",
        f"  Escalated flag: {total_escalated:,}/{len(rows):,} ({total_escalated / len(rows):.1%}).",
        f"  Confidence: mean {confidence_stats['mean']:.3f}, median {confidence_stats['median']:.3f}, range {confidence_stats['min']:.3f}–{confidence_stats['max']:.3f}.",
        f"  Highest-volume intent: {intent_counts.most_common(1)[0][0]} ({intent_counts.most_common(1)[0][1]:,} rows).",
        f"  Most common rating value: {rating_counts.most_common(1)[0][0]} ({rating_counts.most_common(1)[0][1]:,} rows).",
        "",
        "Interpretation limits:",
        "  The 4,500 generated rows are synthetic metadata, not genuine student conversations or feedback.",
        "  No user_query, bot_response, response-time, or explicit anomaly-label field was captured in the supplied CSV.",
        "  The source brief and supplied CSV schema differ; see backend/data/HCL_BRIEF_SCHEMA_CROSSWALK.csv.",
        "  Synthetic rating values must not be presented as actual satisfaction results.",
    ]
    (OUTPUT / "summary.txt").write_text("\n".join(summary_text) + "\n", encoding="utf-8")
    print("EDA complete. Outputs:")
    for name in summary["visualizations"] + ["summary.json", "summary.txt"]:
        print(f"  backend/outputs/eda/{name}")
    print(f"Validated {len(rows)} rows; original records preserved={original_preserved}; no rows rewritten by this script.")
    return summary


def main() -> None:
    try:
        run_eda()
    except (DatasetError, OSError, KeyError) as exc:
        print(f"EDA validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
