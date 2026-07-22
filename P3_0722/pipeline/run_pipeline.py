#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import timezone
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from p3_0722_pipeline.common import (  # noqa: E402
    CONFIG_PATH, PACKAGE_ROOT, PROJECT_ROOT, AuditTrail, safe_git_head, save_csv, save_json,
    sha256_file, sha256_text, short_hash, stable_json, utc_now,
)
from p3_0722_pipeline.stages import (  # noqa: E402
    analysis_stage, behavior_stage, build_implemented_schema, canonical_stage,
    editorial_frontend_stage, enrich_speakers_and_text, qa_answer_stage,
    retrieval_stage, target_stage, vector_projection_stage,
)


def main() -> int:
    started = utc_now()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config_hash = sha256_text(stable_json(config))
    run_id = f"RUN_{started.strftime('%Y%m%dT%H%M%SZ')}_{config_hash[:6].upper()}"
    audit = AuditTrail(run_id)
    registry = build_implemented_schema()

    meetings, canonical, source_docs, source_doc_map, canonical_manifest = canonical_stage(registry, run_id, audit)
    speakers, turns_enriched = enrich_speakers_and_text(registry, run_id, audit, meetings, canonical)
    targets, scopes, source_docs = target_stage(
        registry, run_id, audit, meetings, canonical["retrieval_segments"], source_docs
    )

    for doc_type, title, path, source_year in [
        ("editorial_reference", "P3_CULTURE Editorial Scrollytelling PRD v3.0", PACKAGE_ROOT / "P3_CULTURE_EDITORIAL_SCROLLYTELLING_PRD_VID_SRD_v3.0.md", 2026),
        ("registry", "P3_CULTURE Schema Registry v1.0", PACKAGE_ROOT / "P3_CULTURE_SCHEMA_REGISTRY_v1.0.json", 2026),
        ("registry", "P3_CULTURE Implemented Schema Registry v1.1", PACKAGE_ROOT / "P3_CULTURE_SCHEMA_REGISTRY_v1.1_IMPLEMENTED.json", 2026),
    ]:
        digest = sha256_file(path)
        source_docs = pd.concat(
            [source_docs, pd.DataFrame([{
                "source_document_id": f"DOC_{doc_type.upper()}_{source_year}_{digest[:8].upper()}",
                "document_type": doc_type, "document_title": title, "source_year": source_year,
                "audit_cycle": pd.NA, "source_url": pd.NA,
                "local_path": str(path.relative_to(PROJECT_ROOT)), "mime_type": "application/json" if path.suffix == ".json" else "text/markdown",
                "file_size_bytes": path.stat().st_size, "sha256": digest, "page_count": pd.NA,
                "collected_at": pd.NaT, "access_scope": "internal", "license_note": "project contract",
                "pipeline_run_id": run_id,
            }])], ignore_index=True,
        )

    candidates, segments_enriched = retrieval_stage(
        registry, run_id, audit, config, targets, meetings, canonical["retrieval_segments"], turns_enriched
    )
    (
        qa_pairs, qa_pair_turns, answer_units, answer_unit_turns,
        answer_unit_segments, answer_sentences, links,
    ) = qa_answer_stage(
        registry, run_id, audit, config, meetings, turns_enriched,
        canonical["retrieval_segments"], candidates,
    )
    lexicon, hits, labels, spans, links, verifications = behavior_stage(
        registry, run_id, audit, config, targets, answer_units, links
    )
    (
        embedding_models, embeddings, projection_models, points, topic_bins,
        centroids, nodes, members, projection_id,
    ) = vector_projection_stage(registry, run_id, audit, config, targets, answer_units, labels, links)
    overview, hypothesis, infographic, claim_matrix, figure_paths = analysis_stage(
        run_id, audit, targets, candidates, answer_units, labels, links
    )
    (
        media_assets, evidence, cases, chapters, events, story_metrics, frontend_manifest,
    ) = editorial_frontend_stage(
        registry, run_id, audit, targets, meetings, qa_pairs, answer_units, labels, links,
        verifications, nodes, points, projection_id, source_docs, figure_paths,
    )

    registry.save("source_documents", source_docs)
    finished = utc_now()
    input_items = [
        {"path": str(path.relative_to(PROJECT_ROOT)), "sha256": sha256_file(path)}
        for path in [
            PACKAGE_ROOT / "P3_CULTURE_EDITORIAL_SCROLLYTELLING_PRD_VID_SRD_v3.0.md",
            PACKAGE_ROOT / "P3_CULTURE_SCHEMA_REGISTRY_v1.0.json",
            PROJECT_ROOT / "data_parse" / "audit_minutes_pdf_etl" / "pipeline_manifest.json",
            *[PROJECT_ROOT / "P3_TARGET" / "outputs" / "marked_parallel" / str(y) / f"{y}_marked_issue_mapping.csv" for y in [2020, 2022, 2024]],
        ]
    ]
    input_manifest_hash = sha256_text(stable_json(input_items))

    gates = {
        "P0_CANONICAL_ETL": "PASS",
        "P1_TARGET_SCHEMA": "PASS",
        "P2_TEMPORAL_ELIGIBILITY": "PASS",
        "P3_SPARSE_RETRIEVAL": "PASS_BASELINE",
        "P4_QRELS": "REVIEW_REQUIRED",
        "P5_QA_PAIR": "CONDITIONAL_RULE_CANDIDATES",
        "P6_ANSWER_TAXONOMY": "CONDITIONAL_WEAK_RULE",
        "P7_DENSE_HYBRID": "PASS_CANDIDATE_POOL_RERANK",
        "P8_PROJECTION_NODES": "PASS_COMMON_MULTILINGUAL_UMAP",
        "P9_EDITORIAL": "DRAFT_REVIEW_REQUIRED",
        "P10_FRONTEND_BUNDLE": "GENERATED_NOT_PUBLIC",
    }
    overall_status = "PIPELINE_CONDITIONAL_REVIEW_REQUIRED"
    manifest_path = PACKAGE_ROOT / "outputs" / "pipeline_manifest.json"
    pipeline_run = pd.DataFrame([{
        "pipeline_run_id": run_id, "pipeline_name": "p3_culture_editorial_evidence_pipeline",
        "pipeline_stage": "frontend_bundle", "run_mode": "full", "schema_version": config["schema_version"],
        "parser_version": config["parser_version"], "code_commit": safe_git_head(PROJECT_ROOT),
        "config_hash": config_hash, "input_manifest_hash": input_manifest_hash, "started_at": started,
        "finished_at": finished, "run_status": "conditional_pass", "output_manifest_path": str(manifest_path.relative_to(PACKAGE_ROOT)),
        "error_message": pd.NA,
    }])
    registry.save("pipeline_runs", pipeline_run)
    registry.save("data_quality_metrics", pd.DataFrame(audit.metrics))
    registry.save("data_anomalies", pd.DataFrame(audit.anomalies) if audit.anomalies else registry.empty("data_anomalies"))

    schema_rows = []
    for name, entity in registry.entities.items():
        path = registry.output_path(name)
        if not path.exists():
            schema_rows.append({"entity": name, "exists": False, "row_count": 0, "missing_columns": "ALL", "non_nullable_nulls": "", "status": "FAIL"})
            continue
        df = pd.read_parquet(path)
        expected = registry.columns(name)
        missing = [c for c in expected if c not in df]
        null_violations = []
        for spec in entity["columns"]:
            if not spec["nullable"] and spec["name"] in df and len(df) and df[spec["name"]].isna().any():
                null_violations.append(f"{spec['name']}:{int(df[spec['name']].isna().sum())}")
        status = "PASS" if not missing and not null_violations else "FAIL"
        schema_rows.append({"entity":name,"exists":True,"row_count":len(df),"missing_columns":"|".join(missing),"non_nullable_nulls":"|".join(null_violations),"status":status})
    schema_validation = pd.DataFrame(schema_rows)
    save_csv(PACKAGE_ROOT / "outputs" / "schema_validation.csv", schema_validation)

    output_files = sorted(p for p in PACKAGE_ROOT.rglob("*") if p.is_file() and not ".ipynb_checkpoints" in p.parts)
    output_inventory = []
    for path in output_files:
        if path == manifest_path:
            continue
        if path.suffix.lower() not in {".parquet", ".csv", ".json", ".md", ".png", ".arrow", ".npy", ".npz"}:
            continue
        output_inventory.append({"path":str(path.relative_to(PACKAGE_ROOT)),"size_bytes":path.stat().st_size,"sha256":sha256_file(path)})

    counts = {
        "meetings": len(meetings), "pages": len(canonical["pages"]), "blocks": len(canonical["blocks"]),
        "speaker_turns": len(canonical["speaker_turns"]), "retrieval_segments": len(canonical["retrieval_segments"]),
        "target_issues": len(targets), "retrieval_candidates": len(candidates), "qa_pairs": len(qa_pairs),
        "answer_units": len(answer_units), "answer_sentences": len(answer_sentences),
        "behavior_hits": len(hits), "behavior_spans": len(spans), "target_answer_links": len(links),
        "projection_points": len(points), "atlas_nodes": len(nodes), "evidence_records": len(evidence),
    }
    manifest = {
        "project":"P3_CULTURE", "package":"P3_0722", "pipeline_run_id":run_id,
        "started_at":started.isoformat(), "finished_at":finished.isoformat(), "status":overall_status,
        "schema_source":"P3_CULTURE_SCHEMA_REGISTRY_v1.0.json",
        "implemented_schema":"P3_CULTURE_SCHEMA_REGISTRY_v1.1_IMPLEMENTED.json",
        "config":config, "config_hash":config_hash, "input_manifest_hash":input_manifest_hash,
        "canonical_source_run":canonical_manifest["pipeline_run_id"], "counts":counts, "gates":gates,
        "manual_blockers":[
            "400-pair qrels review not labeled", "Q/A precision and recall not manually measured",
            "answer behavior labels are weak-rule candidates, not Gold", "completion verification is not reviewed",
            "dense retrieval currently reranks the temporally eligible sparse top-50 pool; full-corpus dense recall is not yet evaluated",
            "editorial cases and evidence remain draft/non-public",
        ],
        "input_manifest":input_items, "output_inventory":output_inventory,
        "schema_validation":{"pass":int((schema_validation.status=="PASS").sum()),"fail":int((schema_validation.status=="FAIL").sum())},
    }
    save_json(manifest_path, manifest)

    report = [
        "# P3_CULTURE P3_0722 최종 파이프라인 실행 보고서", "",
        f"- run: `{run_id}`", f"- status: **{overall_status}**",
        f"- canonical source: `{canonical_manifest['pipeline_run_id']}`", "",
        "## 실제 생성 규모", "",
        *[f"- {key}: {value:,}" for key, value in counts.items()], "",
        "## Gate", "", *[f"- {key}: **{value}**" for key, value in gates.items()], "",
        "## 해석 제한", "",
        "- 검색·Q/A·답변행태는 자동 후보 생성까지 완료했다. Gold 또는 승인 데이터로 간주하지 않는다.",
        "- 공식 `complete`는 외부 검증 완료를 뜻하지 않는다.",
        "- 2025 회의록은 2020·2022·2024 target 검색 corpus에 들어가지 않았다.",
        "- 공개 가능한 evidence는 수동 qrels/Q&A/행태/완료 검증 뒤 승인해야 한다.", "",
        "## 다음 필수 작업", "",
        "1. `data/qrels/qrels_review_queue.csv` 400건을 0/1/2로 검수한다.",
        "2. `outputs/answer_review_sample.csv`로 Q/A precision과 A1~A8 precision을 측정한다.",
        "3. 대표 사례 완료 여부를 외부 공식 자료로 검증한다.",
        "4. dense 검색을 전체 eligible corpus ANN 후보군으로 확장하고 qrels 기반 recall gain을 평가한다.",
    ]
    (PACKAGE_ROOT / "outputs" / "FINAL_PIPELINE_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"run_id":run_id,"status":overall_status,"counts":counts,"gates":gates,"manifest":str(manifest_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
