#!/usr/bin/env python3
"""Evaluate whether labeled sample FAQ documents appear in FAISS top-k results."""

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.documents import chunk_documents, load_documents
from app.retriever import FaissRetriever, SentenceTransformerEmbedder
from app.settings import Settings


def evaluate(k: int, questions_path: Path) -> tuple[float, float, int]:
    config = Settings()
    documents = load_documents(config.data_dir)
    chunks = chunk_documents(documents)
    if not chunks:
        raise RuntimeError(f"No chunks available in {config.data_dir}")

    retriever = FaissRetriever(chunks, SentenceTransformerEmbedder(config.embedding_model))
    samples = json.loads(questions_path.read_text(encoding="utf-8"))
    if not samples:
        raise ValueError("Evaluation dataset is empty")

    total_recall = 0.0
    total_hit = 0
    for sample in samples:
        expected = set(sample["expected_document_ids"])
        results = retriever.search(sample["question"], top_k=k)
        found = {result.chunk.document_id for result in results}
        hits = expected & found
        recall = len(hits) / len(expected) if expected else 0.0
        total_recall += recall
        total_hit += bool(hits)
        print(
            f"Q: {sample['question']}\n"
            f"  expected={sorted(expected)} retrieved={[r.chunk.document_id for r in results]} "
            f"recall@{k}={recall:.2f}"
        )

    count = len(samples)
    return total_hit / count, total_recall / count, count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=3, help="Number of retrieved chunks (default: 3)")
    parser.add_argument(
        "--questions",
        type=Path,
        default=BACKEND_DIR / "evaluation" / "sample_questions.json",
        help="JSON file containing questions and expected_document_ids",
    )
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be at least 1")
    hit_rate, recall, count = evaluate(args.k, args.questions)
    print(f"\nResults over {count} samples: HitRate@{args.k}={hit_rate:.3f}, Recall@{args.k}={recall:.3f}")
    print("Interpretation is limited by the small, hand-labeled demonstration dataset; see README.")


if __name__ == "__main__":
    main()
