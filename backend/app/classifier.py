from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

INTENTS: tuple[str, ...] = (
    "admissions",
    "schedule",
    "fees",
    "exams",
    "grievance",
    "hostel",
    "library",
)

QUERY_TYPES: tuple[str, ...] = (
    "query_type_1",  # General Information / FAQ lookup
    "query_type_2",  # Academic & Curriculum inquiry
    "query_type_3",  # Administrative & Calendar deadlines
    "query_type_4",  # Procedural & Facilities requests
    "query_type_5",  # Grievance / Complaints / Escalations
)


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    query_type: str
    scores: dict[str, float] = field(default_factory=dict)
    matched: bool = True


class IntentClassifier(Protocol):
    def classify(self, text: str) -> IntentResult: ...


class RuleBasedIntentClassifier:
    """Transparent, deterministic rule-based intent classifier.

    Uses weighted regex patterns for domain nouns and action stems across all
    seven observed HCL university intents. Confidence is calculated from the
    winning pattern mass and relative margin over the runner-up intent, scaled
    between 0.60 and 0.99 for positive matches, dropping to 0.0 for unmatched queries.
    """

    PATTERNS: dict[str, list[tuple[str, float]]] = {
        "hostel": [
            (r"\b(hostel|mess|dorm|dormitory|room\s+allotment|curfew|warden|gate\s+closes?)\b", 3.5),
            (r"\b(roommate|residence|mess\s+food|hostel\s+fee|hostel\s+office)\b", 2.5),
            (r"\b(room|bed|hostel\s+timing)\b", 1.5),
        ],
        "library": [
            (r"\b(library|reading\s+room|study\s+space|borrow|catalogue|librarian)\b", 3.5),
            (r"\b(book|books|journal|journals|fine|library\s+card|reading\s+hall)\b", 2.0),
            (r"\b(printer\s+access|renewal|shelf)\b", 1.5),
        ],
        "fees": [
            (r"\b(tuition|billing|installment|financial\s+aid|scholarship|scholarships|refund)\b", 3.5),
            (r"\b(fee|fees|payment|pay|receipt|dues|cost|accounts?\s+office)\b", 2.5),
            (r"\b(challan|transaction|unpaid)\b", 1.5),
        ],
        "exams": [
            (r"\b(marksheet|revaluation|backlog|hall\s+ticket|gpa|cgpa|attendance)\b", 3.5),
            (r"\b(exam|exams|examination|examinations|mid\s*sem|end\s*sem|viva)\b", 3.0),
            (r"\b(grade|grades|result|results|transcript|admit\s+card|condonation)\b", 2.0),
        ],
        "schedule": [
            (r"\b(calendar|timetable|time\s*table|holiday|holidays|vacation|semester\s+start|orientation\s+date|convocation)\b", 3.5),
            (r"\b(schedule|scheduled|timings?|deadline|deadlines|academic\s+year)\b", 2.5),
            (r"\b(dates?|when\s+is|when\s+are|when\s+does|open\s+on)\b", 0.8),
        ],
        "grievance": [
            (r"\b(complaint|grievance|password|reset|login|wifi|wi-fi|harassment|ragging|stolen|lost|damaged)\b", 3.5),
            (r"\b(issue|problem|broken|helpdesk|not\s+working|error|erp\s+error|unauthorized)\b", 2.5),
            (r"\b(report|admin\s+office|security\s+office)\b", 1.5),
        ],
        "admissions": [
            (r"\b(admission|admissions|course|courses|register|registration|faculty|professor|instructor|syllabus|eligibility|enrollment|degree)\b", 3.5),
            (r"\b(apply|application|branch|curriculum|advising|advisor|elective|credits?)\b", 2.0),
            (r"\b(prerequisite|internship\s+noc|bonafide)\b", 1.5),
        ],
    }

    PROCEDURAL_TERMS: tuple[str, ...] = (
        "how do i",
        "how can i",
        "how to",
        "apply",
        "process",
        "procedure",
        "steps",
        "process to",
        "registration process",
        "where do i apply",
    )

    DEADLINE_TERMS: tuple[str, ...] = (
        "when",
        "date",
        "deadline",
        "due",
        "last date",
        "timing",
        "schedule",
        "calendar",
        "timetable",
        "start date",
        "close",
    )

    def classify(self, text: str) -> IntentResult:
        normalized = text.lower().strip()
        scores: dict[str, float] = {intent: 0.0 for intent in INTENTS}

        for intent, rule_list in self.PATTERNS.items():
            for pattern, weight in rule_list:
                matches = len(re.findall(pattern, normalized))
                scores[intent] += matches * weight

        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_intent, best_score = sorted_scores[0]
        runner_up_intent, runner_up_score = sorted_scores[1]

        # Case 1: Out-of-domain or completely unmatched
        if best_score == 0.0:
            query_type = self._determine_query_type(normalized, "admissions")
            return IntentResult(
                intent="admissions",
                confidence=0.0,
                query_type=query_type,
                scores=scores,
                matched=False,
            )

        # Case 2: Positive match with calculated confidence
        # Margin over runner-up captures ambiguity
        margin = (best_score - runner_up_score) / best_score
        # Calibrated formula matching HCL empirical distribution [0.60, 0.99]
        base_confidence = 0.60 + 0.15 * min(best_score / 3.5, 1.0) + 0.24 * margin
        confidence = round(min(0.99, max(0.50, base_confidence)), 3)

        query_type = self._determine_query_type(normalized, best_intent)
        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            query_type=query_type,
            scores=scores,
            matched=True,
        )

    def _determine_query_type(self, text: str, intent: str) -> str:
        """Map inquiry phrasing to one of HCL's query_type_1 to query_type_5 categories."""
        # query_type_5: Grievances, complaints, critical system faults
        if intent == "grievance" or any(w in text for w in ("complaint", "lost", "broken", "not working", "stolen", "issue", "error", "reset password")):
            return "query_type_5"

        # query_type_4: Procedural requests, forms, facility allotments
        if any(term in text for term in self.PROCEDURAL_TERMS):
            return "query_type_4"

        # query_type_3: Administrative timelines, schedules, calendar deadlines
        if any(term in text for term in self.DEADLINE_TERMS) or intent == "schedule":
            return "query_type_3"

        # query_type_2: Academic & Curriculum specifics
        if intent in {"admissions", "exams"} or any(w in text for w in ("course", "faculty", "professor", "credit", "syllabus", "subject")):
            return "query_type_2"

        # query_type_1: General inquiries / FAQ lookup
        return "query_type_1"
