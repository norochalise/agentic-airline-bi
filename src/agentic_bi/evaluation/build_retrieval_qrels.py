import json
from typing import Any

from agentic_bi.config import EVALS_DIR
from agentic_bi.tools.knowledge_search import _load_retrieval_assets

EVAL_FILE = EVALS_DIR / "retrieval_cases.json"


def load_cases() -> list[dict[str, Any]]:
    with EVAL_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)["cases"]


def normalize_source(source: str) -> str:
    return source.replace("\\", "/").split("/")[-1]


def is_candidate_chunk(chunk: dict[str, Any], case: dict[str, Any]) -> bool:

    if normalize_source(chunk["source"]) != case["expected_document"]:
        return False

    relevant_pages = case.get("relevant_pages")

    # PDFs: inspect only verified evidence pages.
    if relevant_pages is not None:
        return chunk.get("page_number") in relevant_pages

    # TXT: inspect all chunks from the verified source.
    return True


def main() -> None:
    cases = load_cases()

    chunks, _, _ = _load_retrieval_assets()

    print()
    print("=" * 80)
    print("M14 QREL CANDIDATE INSPECTION")
    print("=" * 80)

    for case in cases:
        candidates = [chunk for chunk in chunks if is_candidate_chunk(chunk, case)]

        print()
        print("=" * 80)
        print(case["id"])
        print("=" * 80)

        print(f"Question: {case['question']}")
        print(f"Expected evidence: {case.get('expected_evidence')}")
        print(f"Supporting quote: {case.get('supporting_quote')}")
        print()

        print(f"Candidate chunks: {len(candidates)}")
        print()

        for chunk in candidates:
            print("-" * 80)
            print(f"CHUNK ID: {chunk['chunk_id']}")
            print(f"SOURCE:   {chunk['source']}")
            print(f"PAGE:     {chunk['page_number']}")
            print()
            print(chunk["text"])
            print()


if __name__ == "__main__":
    main()
