"""
test_dataset_validation.py
──────────────────────────
Stage 4 — Vakta HCLTech Career Shaper Programme (Project No. 30)

Validates the combined 5,000-row dataset (backend/data/dataset.csv)
that is produced by backend/scripts/generate_synthetic_dataset.py.

Run from repository root:
    pytest backend/tests/test_dataset_validation.py -v
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_CSV = REPO_ROOT / "backend" / "data" / "dataset.csv"
ORIGINAL_CSV = REPO_ROOT / "backend" / "data" / "dataset-original-500.csv"
DATA_DICT_CSV = REPO_ROOT / "backend" / "data" / "data_dictionary.csv"
CROSSWALK_CSV = REPO_ROOT / "backend" / "data" / "HCL_BRIEF_SCHEMA_CROSSWALK.csv"

# ─── Expected constants ───────────────────────────────────────────────────────

EXPECTED_COLUMNS = [
    "session_id",
    "user_query_type",
    "intent",
    "confidence_score",
    "escalated",
    "user_rating",
]
EXPECTED_TOTAL_ROWS = 5_000
ORIGINAL_ROWS = 500
SYNTHETIC_ROWS = 4_500

VALID_INTENTS = {"admissions", "schedule", "fees", "exams", "grievance", "hostel", "library"}
VALID_QUERY_TYPES = {"query_type_1", "query_type_2", "query_type_3", "query_type_4", "query_type_5"}
VALID_ESCALATED = {"0", "1"}
VALID_RATINGS = {"1", "2", "3", "4", "5"}

CONFIDENCE_MIN = 0.602
CONFIDENCE_MAX = 0.999

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dataset() -> list[dict[str, str]]:
    """Load backend/data/dataset.csv once for all tests in this module."""
    if not DATASET_CSV.exists():
        pytest.skip(
            f"Dataset not found at {DATASET_CSV}. "
            "Run backend/scripts/generate_synthetic_dataset.py first."
        )
    rows: list[dict[str, str]] = []
    with DATASET_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


# ─── Schema tests ─────────────────────────────────────────────────────────────


class TestSchema:
    """Verify the file exists, has the right columns, and row count."""

    def test_file_exists(self) -> None:
        assert DATASET_CSV.exists(), f"dataset.csv not found at {DATASET_CSV}"

    def test_total_row_count(self, dataset: list[dict]) -> None:
        assert len(dataset) == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} rows, got {len(dataset)}"
        )

    def test_column_names_and_order(self, dataset: list[dict]) -> None:
        actual = list(dataset[0].keys()) if dataset else []
        assert actual == EXPECTED_COLUMNS, (
            f"Columns mismatch.\n  Expected: {EXPECTED_COLUMNS}\n  Got:      {actual}"
        )

    def test_no_extra_columns(self, dataset: list[dict]) -> None:
        extra = set(dataset[0].keys()) - set(EXPECTED_COLUMNS)
        assert not extra, f"Unexpected extra columns: {extra}"


# ─── Session ID tests ─────────────────────────────────────────────────────────


class TestSessionIds:
    """Validate session_id format, uniqueness, and sequential range."""

    def test_session_ids_are_unique(self, dataset: list[dict]) -> None:
        ids = [r["session_id"] for r in dataset]
        assert len(ids) == len(set(ids)), "Duplicate session_id values found"

    def test_session_ids_sequential(self, dataset: list[dict]) -> None:
        expected = [f"S{n:04d}" for n in range(1, EXPECTED_TOTAL_ROWS + 1)]
        actual = [r["session_id"] for r in dataset]
        assert actual == expected, (
            f"Session IDs not sequential. First mismatch at index "
            f"{next(i for i,(a,e) in enumerate(zip(actual,expected)) if a!=e)}"
        )

    def test_original_range(self, dataset: list[dict]) -> None:
        original_ids = [r["session_id"] for r in dataset[:ORIGINAL_ROWS]]
        assert original_ids[0] == "S0001"
        assert original_ids[-1] == f"S{ORIGINAL_ROWS:04d}"

    def test_synthetic_range(self, dataset: list[dict]) -> None:
        synthetic_ids = [r["session_id"] for r in dataset[ORIGINAL_ROWS:]]
        assert synthetic_ids[0] == f"S{ORIGINAL_ROWS + 1:04d}"
        assert synthetic_ids[-1] == f"S{EXPECTED_TOTAL_ROWS:04d}"


# ─── Value domain tests ───────────────────────────────────────────────────────


class TestValueDomains:
    """Check that every cell contains a value from its allowed domain."""

    def test_no_blank_values(self, dataset: list[dict]) -> None:
        blanks = [
            (i + 1, col)
            for i, row in enumerate(dataset)
            for col in EXPECTED_COLUMNS
            if row.get(col, "").strip() == ""
        ]
        assert not blanks, f"Blank values found (row, col): {blanks[:10]}"

    def test_intent_values(self, dataset: list[dict]) -> None:
        bad = {r["intent"] for r in dataset if r["intent"] not in VALID_INTENTS}
        assert not bad, f"Unknown intent values: {bad}"

    def test_all_seven_intents_present(self, dataset: list[dict]) -> None:
        found = {r["intent"] for r in dataset}
        missing = VALID_INTENTS - found
        assert not missing, f"Intents missing from dataset: {missing}"

    def test_query_type_values(self, dataset: list[dict]) -> None:
        bad = {r["user_query_type"] for r in dataset if r["user_query_type"] not in VALID_QUERY_TYPES}
        assert not bad, f"Unknown user_query_type values: {bad}"

    def test_all_five_query_types_present(self, dataset: list[dict]) -> None:
        found = {r["user_query_type"] for r in dataset}
        missing = VALID_QUERY_TYPES - found
        assert not missing, f"Query types missing from dataset: {missing}"

    def test_escalated_values(self, dataset: list[dict]) -> None:
        bad = {r["escalated"] for r in dataset if r["escalated"] not in VALID_ESCALATED}
        assert not bad, f"Invalid escalated values: {bad}"

    def test_user_rating_values(self, dataset: list[dict]) -> None:
        bad = {r["user_rating"] for r in dataset if r["user_rating"] not in VALID_RATINGS}
        assert not bad, f"Invalid user_rating values: {bad}"

    def test_confidence_score_numeric(self, dataset: list[dict]) -> None:
        non_numeric = [
            (i + 1, r["confidence_score"])
            for i, r in enumerate(dataset)
            if not _is_float(r["confidence_score"])
        ]
        assert not non_numeric, f"Non-numeric confidence_score rows: {non_numeric[:5]}"

    def test_confidence_score_range(self, dataset: list[dict]) -> None:
        out_of_range = [
            (i + 1, float(r["confidence_score"]))
            for i, r in enumerate(dataset)
            if _is_float(r["confidence_score"])
            and not (CONFIDENCE_MIN - 1e-6 <= float(r["confidence_score"]) <= CONFIDENCE_MAX + 1e-6)
        ]
        assert not out_of_range, (
            f"confidence_score values outside [{CONFIDENCE_MIN}, {CONFIDENCE_MAX}]: "
            f"{out_of_range[:5]}"
        )


# ─── Original rows preserved ──────────────────────────────────────────────────


class TestOriginalRowsPreserved:
    """The first 500 rows must match the expected format (already loaded from original)."""

    def test_original_row_count(self, dataset: list[dict]) -> None:
        assert len(dataset) >= ORIGINAL_ROWS

    def test_original_rows_have_correct_columns(self, dataset: list[dict]) -> None:
        for i, row in enumerate(dataset[:ORIGINAL_ROWS], start=1):
            assert list(row.keys()) == EXPECTED_COLUMNS, (
                f"Row {i}: column mismatch {list(row.keys())}"
            )

    def test_original_session_ids_format(self, dataset: list[dict]) -> None:
        for i, row in enumerate(dataset[:ORIGINAL_ROWS], start=1):
            sid = row["session_id"]
            assert sid.startswith("S") and len(sid) == 5 and sid[1:].isdigit(), (
                f"Row {i}: unexpected session_id format '{sid}'"
            )

    def test_original_field_values_match_separate_source_copy(self, dataset: list[dict]) -> None:
        with ORIGINAL_CSV.open(newline="", encoding="utf-8-sig") as fh:
            source = list(csv.DictReader(fh))
        assert len(source) == ORIGINAL_ROWS
        assert dataset[:ORIGINAL_ROWS] == source

    def test_missing_official_brief_fields_are_documented_not_fabricated(self) -> None:
        with CROSSWALK_CSV.open(newline="", encoding="utf-8") as fh:
            crosswalk = {row["official_brief_field"]: row for row in csv.DictReader(fh)}
        assert crosswalk["user_query"]["availability"] == "not captured"
        assert crosswalk["bot_response"]["availability"] == "not captured"


# ─── Synthetic rows ───────────────────────────────────────────────────────────


class TestSyntheticRows:
    """Validate synthetic-specific properties."""

    def test_synthetic_row_count(self, dataset: list[dict]) -> None:
        synth = dataset[ORIGINAL_ROWS:]
        assert len(synth) == SYNTHETIC_ROWS, (
            f"Expected {SYNTHETIC_ROWS} synthetic rows, got {len(synth)}"
        )

    def test_synthetic_session_ids_start_correctly(self, dataset: list[dict]) -> None:
        first_synth = dataset[ORIGINAL_ROWS]
        assert first_synth["session_id"] == f"S{ORIGINAL_ROWS + 1:04d}"

    def test_synthetic_session_ids_end_correctly(self, dataset: list[dict]) -> None:
        last = dataset[-1]
        assert last["session_id"] == f"S{EXPECTED_TOTAL_ROWS:04d}"


# ─── Statistical sanity checks ────────────────────────────────────────────────


class TestStatisticalSanity:
    """Lightweight plausibility checks on the combined distribution."""

    def test_escalation_rate_plausible(self, dataset: list[dict]) -> None:
        """Overall escalation rate should be between 5 % and 20 %."""
        esc = sum(1 for r in dataset if r["escalated"] == "1")
        rate = esc / len(dataset)
        assert 0.05 <= rate <= 0.20, (
            f"Escalation rate {rate:.1%} is outside the plausible range [5 %, 20 %]"
        )

    def test_confidence_mean_plausible(self, dataset: list[dict]) -> None:
        """Mean confidence score should stay near the original ~0.797."""
        scores = [float(r["confidence_score"]) for r in dataset]
        mean = sum(scores) / len(scores)
        assert 0.740 <= mean <= 0.850, (
            f"Mean confidence score {mean:.3f} is outside [0.740, 0.850]"
        )

    def test_each_intent_has_reasonable_share(self, dataset: list[dict]) -> None:
        """Each intent should hold at least 5 % of rows."""
        n = len(dataset)
        for intent in VALID_INTENTS:
            cnt = sum(1 for r in dataset if r["intent"] == intent)
            pct = cnt / n
            assert pct >= 0.05, (
                f"Intent '{intent}' has only {pct:.1%} of rows (expected ≥ 5 %)"
            )

    def test_each_query_type_has_reasonable_share(self, dataset: list[dict]) -> None:
        """Each query type should hold at least 10 % of rows."""
        n = len(dataset)
        for qt in VALID_QUERY_TYPES:
            cnt = sum(1 for r in dataset if r["user_query_type"] == qt)
            pct = cnt / n
            assert pct >= 0.10, (
                f"Query type '{qt}' has only {pct:.1%} of rows (expected ≥ 10 %)"
            )

    def test_all_ratings_present(self, dataset: list[dict]) -> None:
        ratings = {r["user_rating"] for r in dataset}
        assert ratings == VALID_RATINGS, f"Missing rating values: {VALID_RATINGS - ratings}"

    def test_grievance_escalation_higher_than_admissions(self, dataset: list[dict]) -> None:
        """Grievance should escalate more often than admissions."""
        def esc_rate(intent: str) -> float:
            rows = [r for r in dataset if r["intent"] == intent]
            return sum(1 for r in rows if r["escalated"] == "1") / len(rows) if rows else 0

        assert esc_rate("grievance") > esc_rate("admissions"), (
            "Expected grievance escalation rate > admissions escalation rate"
        )


# ─── Data dictionary tests ────────────────────────────────────────────────────


class TestDataDictionary:
    """Verify the project-local data dictionary is populated and consistent."""

    def test_data_dict_exists(self) -> None:
        assert DATA_DICT_CSV.exists(), f"data_dictionary.csv not found at {DATA_DICT_CSV}"

    def test_data_dict_covers_all_columns(self) -> None:
        if not DATA_DICT_CSV.exists():
            pytest.skip("data_dictionary.csv not found")
        with DATA_DICT_CSV.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        covered = {r["column_name"] for r in rows}
        assert covered == set(EXPECTED_COLUMNS), (
            f"Data dictionary missing columns: {set(EXPECTED_COLUMNS) - covered}"
        )

    def test_data_dict_descriptions_not_placeholder(self) -> None:
        if not DATA_DICT_CSV.exists():
            pytest.skip("data_dictionary.csv not found")
        with DATA_DICT_CSV.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        # Find the description column (may be 'description' or 'description_fill_in')
        desc_col = None
        for col in rows[0].keys():
            if "description" in col.lower():
                desc_col = col
                break
        assert desc_col, "No description column found in data_dictionary.csv"
        placeholder_rows = [
            r["column_name"]
            for r in rows
            if "[Learner to fill in" in r.get(desc_col, "")
        ]
        assert not placeholder_rows, (
            f"Placeholder descriptions still present for: {placeholder_rows}"
        )


# ─── Utility ──────────────────────────────────────────────────────────────────

def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False
