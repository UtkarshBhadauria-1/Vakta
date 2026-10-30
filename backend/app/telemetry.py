from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TelemetryRecord:
    """Represents a session telemetry entry conforming strictly to HCL's six-column schema.

    Stores only the project's six metadata fields; it does not contain raw query
    or answer text. The session identifier is pseudonymous metadata. This design
    minimizes collected content but does not establish legal or DPDP compliance.
    """

    session_id: str
    user_query_type: str
    intent: str
    confidence_score: float
    escalated: int
    user_rating: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize strictly into the six HCL deliverable columns."""
        return {
            "session_id": self.session_id,
            "user_query_type": self.user_query_type,
            "intent": self.intent,
            "confidence_score": self.confidence_score,
            "escalated": self.escalated,
            "user_rating": self.user_rating,
        }


class TelemetryStore:
    """Thread-safe in-memory store for session telemetry records.

    Note: Because this is an in-memory prototype store, telemetry is reset
    whenever the backend process restarts.
    """

    def __init__(self) -> None:
        self._records: list[TelemetryRecord] = []
        self._index_by_session: dict[str, int] = {}
        self._lock = threading.Lock()
        self._counter = 1

    def generate_session_id(self) -> str:
        """Atomically generate the next sequential session ID (e.g., S0001)."""
        with self._lock:
            session_id = f"S{self._counter:04d}"
            self._counter += 1
            return session_id

    def record(
        self,
        session_id: str,
        user_query_type: str,
        intent: str,
        confidence_score: float,
        escalated: int = 0,
        user_rating: int | None = None,
    ) -> TelemetryRecord:
        """Create or update a telemetry record for a session without creating duplicates."""
        new_record = TelemetryRecord(
            session_id=session_id,
            user_query_type=user_query_type,
            intent=intent,
            confidence_score=round(confidence_score, 3),
            escalated=escalated,
            user_rating=user_rating,
        )

        with self._lock:
            if session_id in self._index_by_session:
                idx = self._index_by_session[session_id]
                existing = self._records[idx]
                merged_rating = user_rating if user_rating is not None else existing.user_rating
                merged_escalated = max(escalated, existing.escalated)
                updated_record = TelemetryRecord(
                    session_id=session_id,
                    user_query_type=user_query_type,
                    intent=intent,
                    confidence_score=round(confidence_score, 3),
                    escalated=merged_escalated,
                    user_rating=merged_rating,
                )
                self._records[idx] = updated_record
                return updated_record

            idx = len(self._records)
            self._records.append(new_record)
            self._index_by_session[session_id] = idx
            return new_record

    def update_rating(self, session_id: str, user_rating: int) -> TelemetryRecord | None:
        """Update the student satisfaction rating for an existing session.

        Allows replacement of a previous rating for the same session.
        Returns the updated record, or None if session does not exist.
        """
        with self._lock:
            if session_id not in self._index_by_session:
                return None
            idx = self._index_by_session[session_id]
            old = self._records[idx]
            updated_record = TelemetryRecord(
                session_id=old.session_id,
                user_query_type=old.user_query_type,
                intent=old.intent,
                confidence_score=old.confidence_score,
                escalated=old.escalated,
                user_rating=user_rating,
            )
            self._records[idx] = updated_record
            return updated_record

    def get_records(self) -> list[TelemetryRecord]:
        with self._lock:
            return list(self._records)

    def get_record(self, session_id: str) -> TelemetryRecord | None:
        with self._lock:
            if session_id not in self._index_by_session:
                return None
            return self._records[self._index_by_session[session_id]]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._index_by_session.clear()
            self._counter = 1
