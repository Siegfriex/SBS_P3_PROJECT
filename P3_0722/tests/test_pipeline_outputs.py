from pathlib import Path
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_core_outputs():
    manifest = json.loads((ROOT / "outputs" / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["meetings"] == 42
    assert manifest["counts"]["target_issues"] == 297
    assert manifest["counts"]["retrieval_segments"] == 196686
    assert manifest["gates"]["P2_TEMPORAL_ELIGIBILITY"] == "PASS"


def test_temporal_and_traceability():
    candidates = pd.read_parquet(ROOT / "data" / "retrieval" / "target_segment_candidates.parquet")
    answers = pd.read_parquet(ROOT / "data" / "qa" / "answer_units.parquet")
    assert candidates["temporal_eligible"].all()
    assert (answers["traceability_status"] == "PASS").all()
    assert not answers["answer_unit_id"].duplicated().any()


def test_no_false_publication_gate():
    manifest = json.loads((ROOT / "outputs" / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PIPELINE_CONDITIONAL_REVIEW_REQUIRED"
    assert manifest["gates"]["P4_QRELS"] == "REVIEW_REQUIRED"
    assert manifest["gates"]["P10_FRONTEND_BUNDLE"] == "GENERATED_NOT_PUBLIC"
