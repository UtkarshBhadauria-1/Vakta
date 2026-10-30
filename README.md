# Vakta — AI-Powered University Student Support

Vakta is an academic prototype for answering university support questions. The React/Vite frontend talks to a Python/FastAPI backend. The backend classifies one of seven intents, estimates sentiment with a small local lexicon, retrieves passages from the included FAQ/PDF corpus with Sentence Transformers and FAISS, and calls Groq only when relevant evidence is available and a server-side key is configured. Answers include source references; unsupported questions receive an explicit limitation response.

> **Prototype boundary:** the sample FAQ is illustrative, escalation is a local flag only, telemetry is in memory, and this is not an official university service. No ticketing or staff-notification integration is connected.

## Architecture

1. The student submits a question from the responsive React 19, Vite, and Tailwind chat.
2. Vite proxies relative `/api/*` requests to FastAPI on port 8000.
3. FastAPI validates the question and recent conversation turns with Pydantic, classifies one of seven intents, and computes a local sentiment cue.
4. Sentence Transformers embeds the search query; FAISS returns the top-k FAQ/PDF chunks with title, path, chunk, and optional page metadata intact.
5. If the evidence threshold is met, the backend sends the question, retrieved passages, and limited follow-up context to Groq. The Groq key and configurable model name remain server-only. Without evidence, generation is skipped and the limitation is stated.
6. The answer and source references return to the chat. When session analytics are opted out, chat and feedback requests carry `X-Telemetry-Opt-Out`; the backend skips telemetry writes.

## Project structure

```text
<project-root>/
├── frontend/                       # React 19, Vite, Tailwind client
│   ├── public/                      # favicon and route manifest
│   └── src/                         # chat UI, API client, styles
├── backend/
│   ├── app/                         # FastAPI, schemas, classifier, sentiment, RAG, FAISS, telemetry
│   ├── data/
│   │   ├── sample_faq.json          # illustrative indexed corpus
│   │   ├── documents/               # optional local PDFs
│   │   ├── raw/academic_ai_assistant/ # preserved Kaggle competition files (not yet indexed)
│   │   ├── dataset-original-500.csv # untouched 500-row source baseline
│   │   ├── dataset.csv              # 5,000-row source + synthetic metadata dataset
│   │   └── HCL_BRIEF_SCHEMA_CROSSWALK.csv
│   ├── evaluation/                  # small hand-labeled retrieval examples
│   ├── outputs/                     # saved verification logs and EDA outputs
│   ├── scripts/                     # dataset, EDA, retrieval, and document generation
│   ├── tests/                       # API, RAG, privacy, classifier, and data validation
│   ├── requirements.txt
│   └── requirements-docs.txt        # python-docx for synopsis/report generation
├── deliverables/                    # completed synopsis, report, diagrams, demo guide
├── Project_Brief-Vakta.docx         # supplied HCLTech project brief
├── Project_Synopsis_Template.docx   # supplied synopsis template
├── .env.example                     # safe backend configuration template
├── requirements.txt                 # root forwarding manifest
├── TODO.md                          # completion and remaining owner action
└── README.md
```

The project root retains the supplied project brief (`Project_Brief-Vakta.docx`) and synopsis template (`Project_Synopsis_Template.docx`), together with the source dataset and source data dictionary. There is no separate `docs/` directory in this package. The Kaggle competition files under `backend/data/raw/academic_ai_assistant/` are preserved as raw source data; they are **not** automatically merged into the RAG index or substituted for the HCLTech six-column metadata file.

## Requirements

- Python 3.10 or newer (Python 3.12 was used for the verified environment)
- Node.js 20+ and pnpm 11.25.0 (pinned in `frontend/package.json`)
- Network access on first use to download the Sentence Transformers model; cached model files can be reused
- A newly rotated Groq key for live answer generation. Retrieval, tests, dataset validation, and the evaluation script do not require Groq credentials.

## Local setup

### 1. Configure the backend

From the repository root:

```bash
python3 -m venv backend/.venv
# macOS/Linux
source backend/.venv/bin/activate
# Windows PowerShell: .\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
cp .env.example .env
```

Edit the root `.env` locally and set `GROQ_API_KEY` to a **newly rotated** key and `GROQ_MODEL` to a model enabled for your Groq account. `.env` and `.env.*` are ignored by Git (except the safe `.env.example`). Keep the key out of frontend variables, React bundles, screenshots, logs, source files, and ZIP deliverables. If you prefer, export the same environment variables in the backend process environment instead of creating `.env`.

Available settings:

| Environment variable | Default / purpose |
|---|---|
| `GROQ_API_KEY` | Empty by default; backend-only credential, needed only when relevant evidence is found and generation is requested |
| `GROQ_MODEL` | `llama-3.3-70b-versatile`; change to a model available to the account |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` |
| `TOP_K` | `4`, constrained to 1–10 |
| `MIN_RELEVANCE_SCORE` | `0.24`, constrained to 0–1 |
| `ALLOWED_ORIGINS` | Local Vite origins on ports 3000 and 5173; use comma-separated origins if separately hosted |
| `DATA_DIR` | Optional; defaults to `backend/data` |

Start FastAPI from the repository root:

```bash
backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Alternatively, from `backend/` with its virtual environment active:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The first startup loads FAQ/PDF text and builds an in-memory FAISS index. Health: `http://127.0.0.1:8000/api/health`; interactive API documentation: `http://127.0.0.1:8000/docs`.

### 2. Configure the frontend

In a second terminal, from the repository root:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://localhost:3000`. Vite proxies `/api` requests to `http://127.0.0.1:8000`. For a separately hosted API, set `VITE_API_BASE_URL` to the API origin when building and update the backend's `ALLOWED_ORIGINS`. Never place a Groq key in a `VITE_*` variable.

### 3. Add approved campus material

The indexed demo corpus starts with `backend/data/sample_faq.json`. Add FAQs in the same record shape or place machine-readable PDFs in `backend/data/documents/`, then restart the backend. PDF text extraction uses `pypdf`; scanned/image-only PDFs need OCR, which is not implemented. Verify that the institution has approved the material for this use. Adding PDFs does not alter the separate HCLTech analysis dataset.

## API contract

- `GET /api/health` returns service/retrieval readiness, chunk count, whether Groq is configured (boolean only), classifier readiness, and current in-memory telemetry count. It does not return a credential.
- `POST /api/chat` accepts a question of 1–1,200 characters, up to eight recent turns (each 1–1,500 characters) and an optional session ID (maximum 64 characters):

  ```json
  {
    "question": "What time can I study at the library on Saturday?",
    "conversation": [],
    "session_id": null
  }
  ```

  The response includes `answer`, `sources` (`id`, `title`, `source`, `excerpt`, `score`, optional `page`), `used_context`, `session_id`, `intent`, `confidence_score`, `user_query_type`, `escalated`, `escalation_reason`, `requires_clarification`, `sentiment_label`, and `sentiment_score`.
- `POST /api/feedback` accepts `{"session_id":"…","user_rating":1}` through `5`. Ratings update the corresponding in-memory session record only when analytics are enabled.
- Both chat and feedback recognize the `X-Telemetry-Opt-Out` header. `1`, `true`, `yes`, or `on` (case-insensitive) opts out. Opted-out chat returns no new telemetry session ID; opted-out feedback returns a “not recorded” success message and does not mutate the store.

## Dataset, validation, and EDA

`backend/data/dataset.csv` contains 5,000 rows: 500 supplied source rows followed by 4,500 reproducible synthetic metadata rows (seed 42). The original 500-row file is preserved separately. The source has six actual columns: `session_id`, `user_query_type`, `intent`, `confidence_score`, `escalated`, and `user_rating`.

The HCLTech brief lists a seven-field chat-log schema, including `user_query` and `bot_response`, which are absent from the supplied CSV. `backend/data/HCL_BRIEF_SCHEMA_CROSSWALK.csv` documents this mismatch; the missing text is explicitly “not captured” and is not fabricated. Synthetic rows do not contain natural-language student questions or chatbot answers. The Kaggle competition dataset is preserved under `backend/data/raw/academic_ai_assistant/` but is not used by the current RAG pipeline or substituted for the source metadata.

Regenerate and validate the expanded dataset and EDA from the repository root:

```bash
backend/.venv/bin/python backend/scripts/generate_synthetic_dataset.py
backend/.venv/bin/python backend/scripts/eda_analysis.py
```

The EDA script produces four genuine PNG charts plus `summary.json` and `summary.txt` under `backend/outputs/eda/`. In the verified run, the data had 5,000 rows, 0 missing cells, 0 duplicate session IDs, 0 duplicate full rows, no invalid allowed values, and exact first-500-row value preservation. The confidence mean was 0.7946; these are dataset properties, not model accuracy or real user traffic.

## Retrieval evaluation and tests

From the repository root:

```bash
backend/.venv/bin/python backend/scripts/evaluate_retrieval.py --k 3
backend/.venv/bin/python -m pytest -q
backend/.venv/bin/python -m compileall -q backend/app backend/scripts backend/tests
cd frontend && pnpm build
```

The saved evaluation result was HitRate@3 = 1.000 and Recall@3 = 1.000 on **eight** hand-labeled questions. It is a small curated demonstration set, not a robust benchmark. The questions are aligned to a small FAQ collection, expected document IDs were manually labeled, paraphrase coverage is limited, and retrieval hits do not establish answer correctness, intent accuracy, sentiment accuracy, or hallucination rate. In the final local verification, **81 backend tests passed**, Python compilation passed, and the Vite production build succeeded. The Groq SDK boundary is tested with a mock; a live Groq call was not made in this verification run.

## Reports, synopsis, and demonstration

Completed materials are in `deliverables/`:

- `Vakta_HCLTech_Project_Synopsis.docx` — completed from the supplied HCLTech template with source diagrams and an unsigned ethical declaration.
- `Vakta_HCLTech_Project_Report.docx` — detailed report with the measured dataset, retrieval, test, and build results and embedded EDA charts.
- `Vakta_1_to_2_Minute_Demo_Script.md` — concise demonstration sequence and sample questions.
- `assets/` — architecture and Level 0 data-flow diagrams used in the documents.

Recreate documents after refreshing test/build/evaluation evidence and EDA outputs:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-docs.txt
backend/.venv/bin/python backend/scripts/generate_submission_docs.py
```

Learner name, roll number, college/campus, mentor, and official submission date were not present in the supplied project files; the synopsis states that transparently rather than inventing them. Its signature and ethical checkboxes remain blank for the learner. The source licence and DPDP Act compliance have not been independently certified; obtain human/mentor review before submission.

## Privacy, limitations, and owner actions

- The uploaded archive contained a Groq credential. Treat it as compromised: revoke/rotate it with the provider before live use. The credential value was not copied into project source or deliverables; use the new key only in a secure server-side environment.
- User questions and retrieved passages may be sent to Groq when answer generation is enabled. The prototype does not implement automatic PII redaction; do not enter sensitive student identifiers or confidential records.
- The sentiment score and classifier confidence are heuristics. They are not calibrated predictive probabilities and have no labeled performance evaluation.
- Telemetry stores metadata only, in memory, and is reset when FastAPI restarts. The opt-out prevents new chat/feedback telemetry, but browser preference state is local to that browser.
- Escalation currently sets a local flag and displays a direct limitation; no person is notified, no support ticket is created, and no response-time promise is made.
- There is no authentication, production deployment, durable database, admin content workflow, OCR, or monitoring. Do not present the sample FAQ as official policy.

## Troubleshooting

- **Backend says index is not ready:** inspect startup logs; confirm `backend/data/sample_faq.json` is readable and the Sentence Transformers model can download or is cached.
- **Evidence found but answer generation reports missing configuration:** set a valid, newly rotated `GROQ_API_KEY` in the backend environment and restart FastAPI; do not place it in frontend files.
- **Frontend shows API unavailable:** start FastAPI on port 8000 and Vite on 3000; confirm the Vite `/api` proxy target and `ALLOWED_ORIGINS` for a separately hosted client.
- **No source text from a PDF:** use a text-readable PDF; OCR for scanned documents is not included.
- **Kaggle raw data:** files are preserved for later review. Competition credentials and dataset rules are separate from Vakta's current FAQ/PDF retrieval corpus.
# Vakta
