# Dataset provenance and interpretation

`dataset-original-500.csv` is the project-local copy of the supplied 500-row `dataset-Vakta.csv`. The two files were verified byte-identical before remediation (SHA-256: `cbf1fbd353623819c462ad76e4277c264b7dcfe41af5dc91ecb44c4d743f7526`). Keep this source copy unchanged. `dataset.csv` is the 5,000-row working set: its first 500 records retain the source field values and its remaining 4,500 rows are reproducibly generated metadata (seed 42), not real conversations.

The official brief's “Chat log” line lists seven fields: `session_id`, `user_query`, `intent`, `confidence_score`, `bot_response`, `escalated`, and `rating`. The actual source CSV has six fields: `session_id`, `user_query_type`, `intent`, `confidence_score`, `escalated`, and `user_rating`. It contains no raw question or answer text. The crosswalk at `HCL_BRIEF_SCHEMA_CROSSWALK.csv` documents each mapping. Missing `user_query` and `bot_response` values are not reconstructed or fabricated. The working dataset and its dictionary retain the actual six-column source schema so no original information is dropped.

The 4,500 generated rows contain only categorical/numeric metadata. Their ratings and labels are simulated; they must not be interpreted as real learner feedback, natural-language examples, model training records, or measured chatbot behavior. The dataset has no captured user question, generated bot answer, or response-time column. See the data dictionary and generated EDA summary before interpreting any aggregate as a real-world measure.

The app's live telemetry uses a small in-memory store and does not persist raw question/answer text. The `escalated` flag records a local workflow flag; it does not prove that a person or office was contacted.
