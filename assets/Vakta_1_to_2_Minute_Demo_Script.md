# Vakta — 1–2 minute demonstration script

## Before the recording

1. Revoke/rotate the Groq credential that appeared in the uploaded archive. Put only the replacement key in the backend's secure environment or ignored root `.env`; never show or narrate the key.
2. Start FastAPI on port 8000 and Vite on port 3000 using the README setup steps. Wait for the retrieval index to become ready.
3. Open the chat at `http://localhost:3000`. Use fictional questions only. Do not enter student names, IDs, grades, health information, or private records.
4. Confirm `GET /api/health` reports retrieval ready. Its `groq_configured` value is only a boolean; it never returns the key.

## Timed sequence (about 100 seconds)

**0:00–0:12 — Introduce the prototype.** Show the Vakta welcome screen, seven support topics, live retrieval status, source-aware conversation area, and the session-analytics control. Say: “This is an academic prototype over an illustrative FAQ corpus—not an official university service.”

**0:12–0:35 — Demonstrate retrieval-grounded help.** Ask: “How do I add or drop a class, and where is the deadline?” Let the answer finish, point to the returned source card, and open or read its title/excerpt. Say that sources are retrieved from the local corpus; do not imply that the sample FAQ contains current official policy.

**0:35–0:48 — Demonstrate a follow-up.** Ask: “Where can I find the deadline?” Show the continuing thread. Explain that recent student turns can disambiguate a follow-up, while retrieved university passages remain the factual evidence.

**0:48–1:02 — Demonstrate the privacy control.** Switch session analytics off. Ask a neutral fictional question. Point out that the preference remains off in this browser. The API response should have no new session ID, and the feedback control should not appear for that answer. Do not claim that this is a legal certification or full anonymity guarantee.

**1:02–1:17 — Demonstrate honest escalation.** With analytics still off, ask: “I want to speak with a real person about a grievance.” Show the local escalation notice and say: “The demo flags the case locally; it does not create a ticket or notify staff.” Do not describe this as an actual human handoff.

**1:17–1:32 — Demonstrate evidence limits.** Ask: “What is the serial number of the university bus?” Show the no-evidence limitation response if that query falls below the configured relevance threshold. If this corpus contains a matching approved document, use a different clearly unsupported campus-detail question; do not present a generated answer as verified if a source is missing.

**1:32–1:40 — Close with limitations.** State: “The intent and sentiment labels are heuristics; the FAQ is illustrative; 4,500 rows in the analysis CSV are synthetic metadata; and deployment, authentication, and staff ticketing are not implemented.”

## If the Groq answer service is not configured

Do not attempt to use the exposed credential. Confirm that a newly rotated key has been supplied through the secure backend environment. Until then, demonstrate `/api/health`, retrieval readiness, the no-evidence path, tests, and the retrieval evaluation output. With relevant evidence but no key, the API deliberately returns a service-configuration error rather than inventing an answer.

## Suggested supporting evidence

- `backend/outputs/eda/summary.txt` and the four PNG charts for dataset findings.
- The eight-sample retrieval evaluation output, described only as a small hand-labeled demonstration result.
- `deliverables/Vakta_HCLTech_Project_Report.docx` for architecture, data limitations, and test results.
