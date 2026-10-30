from __future__ import annotations

import re
from dataclasses import dataclass

EXPLICIT_HUMAN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(speak|talk|connect|transfer|put)\s+(me\s+|us\s+)?(to|with)?\s*(a\s+|an\s+|the\s+)?(university\s+|campus\s+|live\s+|real\s+)?(human|person|officer|agent|staff|representative|helpdesk|counselor|someone|somebody)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(talk|speak)\s+to\s+(someone|somebody|a\s+real\s+person|a\s+human|a\s+staff\s+member)\b", re.IGNORECASE),
    re.compile(r"\b(human\s+(agent|officer|support|representative|assistance|help)|real\s+person)\b", re.IGNORECASE),
    re.compile(r"\b(contact|reach)\s+(the\s+)?(university\s+)?(helpdesk|office|officer|staff|admin)\s+(directly|in\s+person)?\b", re.IGNORECASE),
    re.compile(r"\b(i\s+need\s+a\s+human|i\s+want\s+a\s+human|need\s+to\s+talk\s+to\s+a\s+person|want\s+to\s+speak\s+to\s+a\s+human)\b", re.IGNORECASE),
)

LOCAL_HANDOFF_DISCLOSURE = (
    "This prototype cannot create a support ticket or send a message to university staff. "
    "No staff member has been notified. Please contact your university's official student-support channel directly."
)

EXPLICIT_ESCALATION_ANSWER = (
    "I have marked this conversation for possible staff follow-up in Vakta. "
    + LOCAL_HANDOFF_DISCLOSURE
)

GRIEVANCE_ESCALATION_NOTICE = (
    "\n\n[Human Follow-Up Recommended]: This grievance is flagged locally in the current chat. "
    + LOCAL_HANDOFF_DISCLOSURE
)

GRIEVANCE_NO_EVIDENCE_ANSWER = (
    "I couldn't find reliable information about that in the university documents currently indexed. "
    "This grievance is flagged locally in Vakta, but no support ticket or staff notification is created. "
    "Please contact your university's official Grievance Cell or student-support channel directly."
)

NEGATIVE_SENTIMENT_NO_EVIDENCE_ANSWER = (
    "I'm sorry this has been frustrating. I couldn't find reliable information about that in the "
    "university documents currently indexed. I have marked the conversation locally for possible "
    "follow-up, but this prototype does not create a ticket or notify staff. Please contact your "
    "university's official student-support channel directly."
)

LOW_CONFIDENCE_CLARIFICATION_ANSWER = (
    "I couldn't find reliable information about that in the university documents currently indexed. "
    "I am also not completely certain which category your question falls under. Could you please clarify your "
    "request, or let me know if it relates to admissions, exams, fees, hostel, academic schedule, library, or a student grievance?"
)


@dataclass(frozen=True)
class EscalationDecision:
    escalated: bool
    escalation_reason: str | None
    requires_clarification: bool
    priority_rule: str
    suggested_answer: str | None = None


def check_explicit_human_request(text: str) -> bool:
    """Detect an explicit request for a human without matching substrings like 'humanities'."""
    clean = text.strip()
    return any(pattern.search(clean) for pattern in EXPLICIT_HUMAN_PATTERNS)


def evaluate_escalation(
    question: str,
    intent: str,
    confidence_score: float,
    evidence_count: int,
    sentiment_label: str = "neutral",
) -> EscalationDecision:
    """Apply ordered local triage flags; no branch sends an actual staff handoff."""
    if check_explicit_human_request(question):
        return EscalationDecision(True, "explicit_request", False, "rule_a_explicit_request", EXPLICIT_ESCALATION_ANSWER)

    if intent == "grievance":
        return EscalationDecision(
            True,
            "grievance",
            False,
            "rule_b_grievance_intent",
            GRIEVANCE_NO_EVIDENCE_ANSWER if evidence_count == 0 else None,
        )

    if confidence_score < 0.60:
        return EscalationDecision(
            False,
            "low_confidence",
            True,
            "rule_c_low_confidence",
            LOW_CONFIDENCE_CLARIFICATION_ANSWER if evidence_count == 0 else None,
        )

    if sentiment_label == "negative" and evidence_count == 0:
        return EscalationDecision(
            True,
            "negative_sentiment",
            False,
            "rule_d_negative_sentiment_without_evidence",
            NEGATIVE_SENTIMENT_NO_EVIDENCE_ANSWER,
        )

    if evidence_count == 0:
        return EscalationDecision(False, "insufficient_evidence", False, "rule_e_insufficient_evidence")

    return EscalationDecision(False, None, False, "rule_f_grounded_answer")
