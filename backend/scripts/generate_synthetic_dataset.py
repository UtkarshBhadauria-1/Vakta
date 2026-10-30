"""
generate_synthetic_dataset.py
─────────────────────────────
Stage 4 — Vakta HCLTech Career Shaper Programme (Project No. 30)

Reads the original 500-row HCL telemetry dataset, preserves all original
field values, then generates 4,500 reproducible synthetic metadata rows so
the combined file contains exactly 5,000 rows. It does not fabricate queries
or bot responses; the official brief/source schema difference is documented
in backend/data/HCL_BRIEF_SCHEMA_CROSSWALK.csv.

Output: backend/data/dataset.csv

Usage (from repository root):
    python backend/scripts/generate_synthetic_dataset.py

Dependencies: stdlib only (csv, random, math, os, pathlib)
Random seed: 42 (fully reproducible)
"""

from __future__ import annotations

import csv
import math
import os
import random
import sys
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]          # …/Vakta
# Read from workspace copy (identical to the HCL-provided original in Downloads;
# the Downloads directory is outside the sandbox path).
ORIGINAL_CSV = REPO_ROOT / "backend" / "data" / "dataset-original-500.csv"
OUTPUT_CSV = REPO_ROOT / "backend" / "data" / "dataset.csv"

# ─── Constants ────────────────────────────────────────────────────────────────

RANDOM_SEED = 42
TARGET_TOTAL = 5_000
ORIGINAL_ROWS = 500
SYNTHETIC_ROWS = TARGET_TOTAL - ORIGINAL_ROWS  # 4,500

INTENTS = ["admissions", "schedule", "fees", "exams", "grievance", "hostel", "library"]
QUERY_TYPES = ["query_type_1", "query_type_2", "query_type_3", "query_type_4", "query_type_5"]

# Weights derived from the 500-row baseline (rounded to nearest count).
INTENT_WEIGHTS = [78, 78, 77, 73, 67, 67, 60]          # sum = 500
QUERY_TYPE_WEIGHTS = [98, 102, 111, 113, 76]             # sum = 500

CONFIDENCE_MIN = 0.602
CONFIDENCE_MAX = 0.999

# Base escalation probability (~7.8 % in original)
ESCALATION_BASE_RATE = 0.078

# Fraction of synthetic rows that carry deliberate anomalies (~3 % → ≈135 rows)
ANOMALY_RATE = 0.03

COLUMNS = [
    "session_id",
    "user_query_type",
    "intent",
    "confidence_score",
    "escalated",
    "user_rating",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def weighted_choice(population: list[str], weights: list[int], rng: random.Random) -> str:
    """Return one element sampled proportionally to weights (stdlib-only)."""
    total = sum(weights)
    r = rng.uniform(0, total)
    cumulative = 0
    for item, w in zip(population, weights):
        cumulative += w
        if r <= cumulative:
            return item
    return population[-1]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def generate_confidence(intent: str, rng: random.Random) -> float:
    """
    Sample a confidence score.

    Grievance intent has a wider spread and a slightly lower centre to
    reflect harder classification.  All other intents cluster around the
    original mean (~0.797) with std ~0.118.
    """
    if intent == "grievance":
        # Wider spread: mean ~0.760, std ~0.150
        raw = rng.gauss(0.760, 0.150)
    else:
        raw = rng.gauss(0.797, 0.118)
    return round(clamp(raw, CONFIDENCE_MIN, CONFIDENCE_MAX), 3)


def escalation_flag(intent: str, confidence: float, is_anomaly: bool, rng: random.Random) -> int:
    """
    Derive the escalated flag (0 or 1).

    Priority rules (matching the live escalation.py logic direction):
      1. Anomaly row with explicit high-confidence escalation (inverted signal).
      2. Grievance intent → elevated rate (~15 %).
      3. Low confidence (<0.65) → slightly elevated (~12 %).
      4. Otherwise → baseline rate (~5 %).
    """
    if is_anomaly and rng.random() < 0.60:
        # Anomaly: high confidence + escalated (inverted signal)
        return 1
    if intent == "grievance":
        return 1 if rng.random() < 0.15 else 0
    if confidence < 0.65:
        return 1 if rng.random() < 0.12 else 0
    return 1 if rng.random() < 0.05 else 0


def generate_rating(intent: str, escalated: int, confidence: float, rng: random.Random) -> int:
    """
    Generate a discrete user rating (1–5).

    Heuristics:
      - Escalated grievance → skew low (1–2).
      - High confidence (≥0.85) → skew high (4–5).
      - Otherwise → roughly uniform with a slight central bias.
    """
    if intent == "grievance" and escalated == 1:
        # Skew low
        return rng.choices([1, 2, 3, 4, 5], weights=[35, 30, 20, 10, 5], k=1)[0]
    if confidence >= 0.85:
        # Skew high
        return rng.choices([1, 2, 3, 4, 5], weights=[5, 10, 20, 35, 30], k=1)[0]
    # Central bias
    return rng.choices([1, 2, 3, 4, 5], weights=[15, 20, 30, 20, 15], k=1)[0]


# ─── Main generation logic ────────────────────────────────────────────────────

def read_original_rows() -> list[dict[str, str]]:
    """Read the 500-row HCL source file and return all rows as dicts."""
    if not ORIGINAL_CSV.exists():
        sys.exit(f"ERROR: Original dataset not found at {ORIGINAL_CSV}")

    with ORIGINAL_CSV.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            sys.exit(f"ERROR: Original dataset schema mismatch: expected {COLUMNS}, got {reader.fieldnames}")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(row.get(column) is None for column in COLUMNS):
                sys.exit(f"ERROR: Original dataset row {row_number} has an invalid number of fields")
            # Do not strip or normalize values: the source records are the baseline.
            rows.append({column: row[column] for column in COLUMNS})

    if len(rows) != ORIGINAL_ROWS:
        sys.exit(f"ERROR: Expected {ORIGINAL_ROWS} original rows, found {len(rows)}; output not written.")
    return rows


def generate_synthetic_rows(rng: random.Random) -> list[dict[str, str]]:
    """Generate 4,500 synthetic rows."""
    rows: list[dict[str, str]] = []

    # Determine which row indices carry anomalies (deterministic given seed)
    anomaly_count = math.ceil(SYNTHETIC_ROWS * ANOMALY_RATE)
    anomaly_indices = set(rng.sample(range(SYNTHETIC_ROWS), anomaly_count))

    for i in range(SYNTHETIC_ROWS):
        session_num = ORIGINAL_ROWS + i + 1          # S0501 … S5000
        session_id = f"S{session_num:04d}"

        intent = weighted_choice(INTENTS, INTENT_WEIGHTS, rng)
        query_type = weighted_choice(QUERY_TYPES, QUERY_TYPE_WEIGHTS, rng)
        confidence = generate_confidence(intent, rng)
        is_anomaly = i in anomaly_indices
        escalated = escalation_flag(intent, confidence, is_anomaly, rng)
        rating = generate_rating(intent, escalated, confidence, rng)

        rows.append(
            {
                "session_id": session_id,
                "user_query_type": query_type,
                "intent": intent,
                "confidence_score": str(confidence),
                "escalated": str(escalated),
                "user_rating": str(rating),
            }
        )

    return rows


def validate_combined(rows: list[dict[str, str]]) -> None:
    """Lightweight sanity checks on the combined 5,000-row dataset."""
    errors: list[str] = []

    # Row count
    if len(rows) != TARGET_TOTAL:
        errors.append(f"Row count: expected {TARGET_TOTAL}, got {len(rows)}")

    # Column names
    actual_cols = list(rows[0].keys()) if rows else []
    if actual_cols != COLUMNS:
        errors.append(f"Columns mismatch: {actual_cols} ≠ {COLUMNS}")

    # Session IDs: sequential, unique, correct format
    session_ids = [r["session_id"] for r in rows]
    expected_ids = [f"S{n:04d}" for n in range(1, TARGET_TOTAL + 1)]
    if session_ids != expected_ids:
        errors.append("Session IDs are not sequential S0001–S5000")

    # No blank values in mandatory columns
    for idx, row in enumerate(rows, start=1):
        for col in COLUMNS:
            if row.get(col, "").strip() == "":
                errors.append(f"Row {idx}: blank value in '{col}'")
                break

    # Intent values
    valid_intents = set(INTENTS)
    bad_intents = {r["intent"] for r in rows if r["intent"] not in valid_intents}
    if bad_intents:
        errors.append(f"Unknown intent values: {bad_intents}")

    # Query type values
    valid_qt = set(QUERY_TYPES)
    bad_qt = {r["user_query_type"] for r in rows if r["user_query_type"] not in valid_qt}
    if bad_qt:
        errors.append(f"Unknown query_type values: {bad_qt}")

    # Escalated: 0 or 1
    bad_esc = {r["escalated"] for r in rows if r["escalated"] not in {"0", "1"}}
    if bad_esc:
        errors.append(f"Invalid escalated values: {bad_esc}")

    # User rating: 1–5
    bad_rat = {r["user_rating"] for r in rows if r["user_rating"] not in {"1", "2", "3", "4", "5"}}
    if bad_rat:
        errors.append(f"Invalid user_rating values: {bad_rat}")

    # Confidence score in [0.602, 0.999]
    for idx, row in enumerate(rows, start=1):
        try:
            val = float(row["confidence_score"])
        except ValueError:
            errors.append(f"Row {idx}: non-numeric confidence_score '{row['confidence_score']}'")
            continue
        if not (CONFIDENCE_MIN - 1e-6 <= val <= CONFIDENCE_MAX + 1e-6):
            errors.append(
                f"Row {idx}: confidence_score {val} outside [{CONFIDENCE_MIN}, {CONFIDENCE_MAX}]"
            )

    if errors:
        print("\n".join(f"  FAIL: {e}" for e in errors), file=sys.stderr)
        sys.exit("Validation failed — dataset not written.")

    print(f"  Validation passed ({TARGET_TOTAL} rows, {len(COLUMNS)} columns).")


def print_summary(rows: list[dict[str, str]]) -> None:
    """Print distribution summary to stdout."""
    print("\n── Combined dataset summary ─────────────────────────────")
    print(f"  Total rows        : {len(rows)}")
    print(f"  Original rows     : {ORIGINAL_ROWS}  (S0001–S0500, verbatim)")
    print(f"  Synthetic rows    : {SYNTHETIC_ROWS} (S0501–S5000, seed={RANDOM_SEED})")

    # Intent distribution
    intent_counts: dict[str, int] = {}
    for r in rows:
        intent_counts[r["intent"]] = intent_counts.get(r["intent"], 0) + 1
    print("\n  Intent distribution:")
    for intent in sorted(intent_counts, key=lambda x: -intent_counts[x]):
        pct = 100 * intent_counts[intent] / len(rows)
        print(f"    {intent:<12s}: {intent_counts[intent]:5d}  ({pct:.1f} %)")

    # Query type distribution
    qt_counts: dict[str, int] = {}
    for r in rows:
        qt_counts[r["user_query_type"]] = qt_counts.get(r["user_query_type"], 0) + 1
    print("\n  Query type distribution:")
    for qt in sorted(qt_counts):
        pct = 100 * qt_counts[qt] / len(rows)
        print(f"    {qt:<14s}: {qt_counts[qt]:5d}  ({pct:.1f} %)")

    # Escalation
    esc1 = sum(1 for r in rows if r["escalated"] == "1")
    print(f"\n  Escalated=1       : {esc1:5d}  ({100*esc1/len(rows):.1f} %)")
    print(f"  Escalated=0       : {len(rows)-esc1:5d}  ({100*(len(rows)-esc1)/len(rows):.1f} %)")

    # Confidence score stats
    scores = [float(r["confidence_score"]) for r in rows]
    mean_c = sum(scores) / len(scores)
    variance = sum((x - mean_c) ** 2 for x in scores) / len(scores)
    std_c = variance ** 0.5
    print(f"\n  Confidence score  : min={min(scores):.3f}  max={max(scores):.3f}")
    print(f"                      mean={mean_c:.3f}  std={std_c:.3f}")

    # Rating distribution
    rating_counts: dict[str, int] = {}
    for r in rows:
        rating_counts[r["user_rating"]] = rating_counts.get(r["user_rating"], 0) + 1
    print("\n  User rating distribution:")
    for rat in ["1", "2", "3", "4", "5"]:
        cnt = rating_counts.get(rat, 0)
        pct = 100 * cnt / len(rows)
        print(f"    rating {rat}       : {cnt:5d}  ({pct:.1f} %)")
    print("─────────────────────────────────────────────────────────\n")


def main() -> None:
    print(f"Vakta — Stage 4: Synthetic Dataset Generator (seed={RANDOM_SEED})")
    print(f"  Source : {ORIGINAL_CSV}")
    print(f"  Output : {OUTPUT_CSV}")

    # 1. Read original rows
    original_rows = read_original_rows()
    print(f"  Read {len(original_rows)} original rows.")

    # 2. Generate synthetic rows
    rng = random.Random(RANDOM_SEED)
    synthetic_rows = generate_synthetic_rows(rng)
    print(f"  Generated {len(synthetic_rows)} synthetic rows.")

    # 3. Combine
    combined = original_rows + synthetic_rows

    # 4. Validate
    print("  Validating combined dataset...")
    validate_combined(combined)

    # 5. Write the derived output atomically; never modify the source CSV.
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = OUTPUT_CSV.with_suffix(OUTPUT_CSV.suffix + ".tmp")
    with temporary_output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(combined)
    os.replace(temporary_output, OUTPUT_CSV)

    print(f"  Wrote {len(combined)} rows to {OUTPUT_CSV}")
    print_summary(combined)


if __name__ == "__main__":
    main()
