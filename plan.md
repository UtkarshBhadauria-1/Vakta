# Vakta UI redesign plan

## Scope and architecture

This change is a presentation and product-branding redesign of the existing student-support application, not a new project. Keep the React/Vite/Tailwind frontend and Python/FastAPI backend in their current directories. Preserve the `/api/health` and `/api/chat` endpoints, Pydantic request/response schemas, server-side Groq configuration, retrieval index, FAISS/Sentence Transformers flow, and source attribution. Do not introduce mock replies, browser credentials, new persistence, or an incompatible API.

The frontend work is centered in `frontend/src/App.jsx` and `frontend/src/index.css`: retain the existing API client and conversation state flow; replace the generated welcome chat bubble with a true welcome state; retain the message/source/loading/error states; add the requested dark sidebar navigation, responsive drawer toggle, compact top bar, and grounded-answer composer. Update browser metadata, route title, and error copy to the Vakta brand. Use an original inline SVG speech/waveform mark; do not copy the absent reference screenshot's logo.

Update the existing README/checklist and FastAPI/Groq assistant display name where user-facing. Leave backend endpoint paths, Pydantic schemas, request bodies, response shape, retrieval settings, and environment variable names untouched.

## Project structure

- `frontend/src/App.jsx`: sidebar, brand mark, topic selections, welcome screen, conversation rendering, citations, health status, and composer interactions.
- `frontend/src/index.css`: restrained navy/teal shell, responsive sidebar drawer, workspace/welcome layout, message/source styles, composer, and accessibility states.
- `frontend/src/api.js`: existing `/api/health` and `/api/chat` client; only user-visible fallback wording may change.
- `frontend/index.html`, `frontend/public/manus-routes.json`: Vakta title/description and route label.
- `backend/app/main.py`, `backend/app/rag.py`: update the assistant display name only; preserve API behavior and RAG pipeline.
- `README.md`, `TODO.md`, `plan.md`: align project branding and record the scoped redesign.

## Design direction

- **Design Movement**: Restrained contemporary campus software, with the clarity of an editorial help desk and a deep-teal navigation rail.
- **Core Principles**: calm hierarchy; compact, legible controls; evidence-forward answers; mobile layouts that remain fully usable.
- **Color Philosophy**: deep navy/teal sidebar gives the app a distinctive anchor; off-white welcome/conversation surfaces reduce glare; blue-teal actions draw attention only to the current next step.
- **Layout Paradigm**: full-height bordered shell with a fixed-width left navigation, slim top bar, flexible main workspace, centered empty state, and a conversation composer at the bottom. On narrow screens, the sidebar becomes an overlay drawer.
- **Signature Elements**: original speech-outline/waveform logo; restrained teal active-navigation stripe; compact source cards attached to assistant answers.
- **Interaction Philosophy**: navigation selection changes the topic context without discarding an active conversation; New Chat explicitly resets it; Enter sends and Shift+Enter adds a line; loading/errors and service status remain visible and honest.
- **Animation**: short, subtle message entrance and drawer transition only; respect reduced-motion preferences; avoid ambient or decorative animation.
- **Typography System**: system sans stack for navigation and controls, with a slightly stronger display weight for the centered welcome title; clear 12–15px text with restrained utility labels.
- **Brand Essence**: “Vakta is the campus companion that helps students find grounded answers from university information”; personality: calm, clear, dependable.
- **Brand Voice**: warm, direct, and transparent. Example lines: “Welcome to Vakta” and “Answers are grounded in indexed university information.”
- **Wordmark & Logo**: “Vakta” wordmark beside an inline SVG speech bubble containing a small waveform; original to this application.
- **Signature Brand Color**: deep teal `#0B3B45`, accented with blue-teal `#367D8C`.
