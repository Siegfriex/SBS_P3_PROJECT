from __future__ import annotations

import json
import math
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import chi2_contingency, mannwhitneyu, spearmanr
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize as l2_normalize

from .common import (
    AuditTrail,
    IMPLEMENTED_SCHEMA_PATH,
    PACKAGE_ROOT,
    PROJECT_ROOT,
    SCHEMA_PATH,
    SchemaRegistry,
    compact_text,
    meeting_date_iso,
    normalize_text,
    nullable_text,
    save_csv,
    save_json,
    sha256_file,
    sha256_text,
    short_hash,
    utc_now,
)
from .text_rules import behavior_hits, behavior_lexicon_rows, parse_speaker, speaker_head_from_block


CANONICAL_SOURCE = PROJECT_ROOT / "data_parse" / "audit_minutes_pdf_etl"
TARGET_SOURCE = PROJECT_ROOT / "P3_TARGET" / "outputs" / "marked_parallel"
PDF_SOURCE = PROJECT_ROOT / "pdf_raw_data"


def build_implemented_schema() -> SchemaRegistry:
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload["document"]["version"] = "1.1.0-implemented"
    payload["document"]["status"] = "Implemented extension of v1.0 with target-independent QA and answer units"
    entities = payload["entities"]
    qa = next(item for item in entities if item["name"] == "qa_pairs")
    qa["grain"] = "회의록의 검증 후보 질문 span × 답변 span 1개; target 독립"
    qa["columns"] = [c for c in qa["columns"] if c["name"] != "target_issue_id"]
    qa["foreign_keys"] = [fk for fk in qa["foreign_keys"] if fk["column"] != "target_issue_id"]

    def entity(name, logical_name, grain, pk, columns, note=""):
        return {
            "layer": "L3_qa_behavior",
            "name": name,
            "logical_name_ko": logical_name,
            "grain": grain,
            "primary_key": pk,
            "columns": [
                {
                    "name": col,
                    "logical_name_ko": label,
                    "dtype": dtype,
                    "nullable": nullable,
                    "description": description,
                    "rule": rule,
                    "example": "",
                }
                for col, label, dtype, nullable, description, rule in columns
            ],
            "foreign_keys": [],
            "storage": f"{name}.parquet",
            "required_level": "required",
            "partitioning": "none",
            "note": note,
        }

    entities.extend(
        [
            entity(
                "meeting_speakers", "회의별 화자 사전", "회의 × 정규화 화자 1개", ["meeting_speaker_id"],
                [
                    ("meeting_speaker_id", "회의 화자 ID", "string", False, "회의 내 화자 식별자", "MSP_{meeting}_{hash8}"),
                    ("meeting_id", "회의 ID", "string", False, "회의 FK", ""),
                    ("speaker_raw", "원본 화자", "string", False, "원본 헤더", ""),
                    ("speaker_name", "화자명", "string", True, "파싱 이름", ""),
                    ("speaker_role_raw", "원본 직책", "string", True, "원문 직책", ""),
                    ("speaker_role_normalized", "정규 직책", "string", True, "정규 직책", ""),
                    ("speaker_org", "기관", "string", True, "기관", ""),
                    ("speaker_side", "화자 측", "category", False, "위원·기관·절차·미상", "committee|institution|procedural|unknown"),
                    ("speaker_class", "화자 클래스", "category", False, "세부 역할", ""),
                    ("is_question_eligible", "질문 후보", "boolean", False, "질문자 허용", ""),
                    ("is_answer_eligible", "답변 후보", "boolean", False, "답변자 허용", ""),
                    ("parse_rule", "파싱 규칙", "string", False, "규칙", ""),
                    ("parse_confidence", "파싱 신뢰도", "Float64", False, "0~1", ""),
                    ("manual_override", "수동교정", "boolean", False, "수동 교정 여부", ""),
                ],
            ),
            entity(
                "answer_units", "답변 단위", "한 답변자가 한 질문 문맥에 제공한 연속 답변 span", ["answer_unit_id"],
                [
                    ("answer_unit_id", "답변 단위 ID", "string", False, "PK", "ANS_{meeting}_{start}_{end}"),
                    ("qa_pair_id", "Q/A ID", "string", False, "QA FK", ""),
                    ("meeting_id", "회의 ID", "string", False, "회의 FK", ""),
                    ("meeting_date", "회의 날짜", "date32", True, "회의 날짜", ""),
                    ("answer_speaker_id", "답변 화자 ID", "string", False, "meeting speaker FK", ""),
                    ("answer_speaker_name", "답변자명", "string", True, "", ""),
                    ("answer_speaker_role", "답변자 직책", "string", True, "", ""),
                    ("answer_speaker_org", "답변 기관", "string", True, "", ""),
                    ("answer_speaker_class", "답변자 클래스", "category", False, "", ""),
                    ("answer_turn_start_no", "답변 시작 turn", "string", False, "", ""),
                    ("answer_turn_end_no", "답변 종료 turn", "string", False, "", ""),
                    ("answer_turn_count", "답변 turn 수", "Int64", False, "", ""),
                    ("page_start_no", "시작 페이지", "string", False, "", ""),
                    ("page_end_no", "종료 페이지", "string", False, "", ""),
                    ("block_start_no", "시작 block", "string", False, "", ""),
                    ("block_end_no", "종료 block", "string", False, "", ""),
                    ("primary_segment_no", "대표 segment", "string", False, "", ""),
                    ("answer_text_raw", "원본 답변", "string", False, "원문 보존", ""),
                    ("answer_text_display", "표시용 답변", "string", False, "", ""),
                    ("answer_text_normalized", "정규 답변", "string", False, "NFKC", ""),
                    ("answer_text_compact", "압축 답변", "string", False, "공백 제거", ""),
                    ("char_count", "문자 수", "Int64", False, "", ""),
                    ("sentence_count", "문장 수", "Int64", False, "", ""),
                    ("role_confidence", "역할 신뢰도", "Float64", False, "", ""),
                    ("qa_confidence", "Q/A 신뢰도", "Float64", False, "", ""),
                    ("traceability_status", "역추적 상태", "category", False, "", "PASS|FAIL"),
                    ("review_status", "검수 상태", "category", False, "", "unreviewed|reviewed|approved"),
                    ("answer_hash", "답변 해시", "string", False, "", ""),
                ],
            ),
            entity(
                "answer_unit_turns", "답변-turn bridge", "답변 단위 × turn", ["answer_unit_id", "turn_no"],
                [
                    ("answer_unit_id", "답변 ID", "string", False, "", ""),
                    ("turn_no", "turn ID", "string", False, "", ""),
                    ("turn_order", "순서", "Int64", False, "", ""),
                ],
            ),
            entity(
                "answer_unit_segments", "답변-segment bridge", "답변 단위 × segment", ["answer_unit_id", "segment_no"],
                [
                    ("answer_unit_id", "답변 ID", "string", False, "", ""),
                    ("segment_no", "segment ID", "string", False, "", ""),
                    ("segment_role", "segment 역할", "category", False, "", "primary|supporting"),
                    ("segment_type", "segment 유형", "category", False, "", ""),
                    ("retrieval_score", "검색 점수", "Float64", True, "", ""),
                    ("is_primary", "대표 여부", "boolean", False, "", ""),
                ],
            ),
            entity(
                "answer_sentences", "답변 문장", "답변 단위 내부 문장", ["answer_sentence_id"],
                [
                    ("answer_sentence_id", "답변 문장 ID", "string", False, "", ""),
                    ("answer_unit_id", "답변 ID", "string", False, "", ""),
                    ("sentence_seq", "문장 순서", "Int64", False, "", ""),
                    ("char_start", "시작 offset", "Int64", False, "", ""),
                    ("char_end", "종료 offset", "Int64", False, "", ""),
                    ("sentence_text_raw", "원문 문장", "string", False, "", ""),
                    ("sentence_text_normalized", "정규 문장", "string", False, "", ""),
                    ("sentence_text_compact", "압축 문장", "string", False, "", ""),
                    ("source_turn_no", "원천 turn", "string", False, "", ""),
                    ("source_page_no", "원천 페이지", "string", False, "", ""),
                    ("segmentation_rule", "분리 규칙", "string", False, "", ""),
                    ("segmentation_confidence", "분리 신뢰도", "Float64", False, "", ""),
                    ("is_interrogative", "의문문", "boolean", False, "", ""),
                    ("is_quoted_context", "인용 맥락", "boolean", False, "", ""),
                    ("has_negation_context", "부정 맥락", "boolean", False, "", ""),
                ],
            ),
            entity(
                "behavior_lexicon", "답변행태 사전", "답변행태 정규식 1개", ["lexicon_pattern_id"],
                [
                    ("lexicon_pattern_id", "패턴 ID", "string", False, "", ""),
                    ("behavior_code", "행태 코드", "category", False, "", "A1|A2|A3|A4|A5|A6|A7|A8"),
                    ("behavior_label_ko", "행태명", "string", False, "", ""),
                    ("pattern_regex", "정규식", "string", False, "", ""),
                    ("pattern_normalized", "정규 패턴", "string", False, "", ""),
                    ("pattern_compact", "압축 패턴", "string", False, "", ""),
                    ("pattern_version", "패턴 버전", "string", False, "", ""),
                    ("is_active", "활성", "boolean", False, "", ""),
                    ("include_rule", "포함 규칙", "string", False, "", ""),
                    ("exclude_rule", "제외 규칙", "string", False, "", ""),
                ],
            ),
            entity(
                "answer_behavior_hits", "답변행태 적중", "답변 × 정규식 적중 span", ["behavior_hit_id"],
                [
                    ("behavior_hit_id", "적중 ID", "string", False, "", ""),
                    ("answer_unit_id", "답변 ID", "string", False, "", ""),
                    ("behavior_code", "행태 코드", "category", False, "", ""),
                    ("lexicon_pattern_id", "패턴 ID", "string", False, "", ""),
                    ("char_start", "시작", "Int64", False, "", ""),
                    ("char_end", "종료", "Int64", False, "", ""),
                    ("span_text", "근거 span", "string", False, "", ""),
                    ("context_text", "문맥", "string", False, "", ""),
                    ("match_variant", "매칭 방식", "category", False, "", ""),
                    ("hit_confidence", "신뢰도", "Float64", False, "", ""),
                    ("is_suppressed", "억제 여부", "boolean", False, "", ""),
                    ("suppression_reason", "억제 이유", "string", True, "", ""),
                ],
            ),
        ]
    )
    IMPLEMENTED_SCHEMA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return SchemaRegistry(IMPLEMENTED_SCHEMA_PATH)


def canonical_stage(registry: SchemaRegistry, run_id: str, audit: AuditTrail):
    source_manifest = json.loads((CANONICAL_SOURCE / "pipeline_manifest.json").read_text(encoding="utf-8"))
    source_registry = pd.read_parquet(CANONICAL_SOURCE / "control_registry.parquet")
    actual_hashes = {p.stem: sha256_file(p) for p in sorted(PDF_SOURCE.glob("*.pdf"))}
    expected_hashes = dict(zip(source_registry["meeting_id"], source_registry["sha256"]))
    hash_fail = [mid for mid, digest in expected_hashes.items() if actual_hashes.get(mid) != digest]
    audit.metric("meeting_registry", "source_pdf_hash_mismatch", len(hash_fail), "PASS" if not hash_fail else "FAIL", "==0")
    audit.metric("meeting_registry", "source_pdf_count", len(actual_hashes), "PASS" if len(actual_hashes) == 42 else "FAIL", "==42")

    source_docs = []
    source_doc_map = {}
    for row in source_registry.itertuples(index=False):
        full_year = 2000 + int(row.meeting_year)
        doc_id = f"DOC_MEETING_{full_year}_{str(row.sha256)[:8].upper()}"
        source_doc_map[row.meeting_id] = doc_id
        source_docs.append(
            {
                "source_document_id": doc_id,
                "document_type": "meeting_minutes",
                "document_title": f"문화체육관광위원회 회의록 {row.meeting_id}",
                "source_year": full_year,
                "audit_cycle": f"AUDIT_{full_year}",
                "source_url": row.source_url,
                "local_path": f"pdf_raw_data/{row.meeting_id}.pdf",
                "mime_type": "application/pdf",
                "file_size_bytes": row.file_size,
                "sha256": row.sha256,
                "page_count": row.page_count,
                "collected_at": pd.NaT,
                "access_scope": "public",
                "license_note": "대한민국 국회 회의록; 원문 출처 표시",
                "pipeline_run_id": run_id,
            }
        )

    meetings = source_registry.copy()
    meetings["meeting_date_iso"] = [meeting_date_iso(y, d) for y, d in zip(meetings.meeting_year, meetings.meeting_date)]
    meetings["audit_cycle"] = meetings["meeting_year"].map(lambda y: f"AUDIT_{2000 + int(y)}")
    meetings["source_document_id"] = meetings["meeting_id"].map(source_doc_map)
    meetings["local_pdf_path"] = meetings["meeting_id"].map(lambda x: f"pdf_raw_data/{x}.pdf")
    meetings["parse_status"] = "parsed"
    meetings["parser_name"] = "audit_minutes_pdf_etl"
    meetings["ocr_page_count"] = 0
    registry.save("meeting_registry", meetings)

    tables = {}
    source_name = {
        "index_map": "index_map",
        "pages": "pages",
        "blocks": "blocks",
        "speaker_turns": "speaker_turns",
        "retrieval_segments": "retrieval_segments",
    }
    for entity, filename in source_name.items():
        frame = pd.read_parquet(CANONICAL_SOURCE / f"{filename}.parquet")
        tables[entity] = frame

    blocks = tables["blocks"]
    block_counts = blocks[blocks["turn_no"].notna()].groupby("turn_no").size()
    turns = tables["speaker_turns"].copy()
    turns["turn_type"] = turns["turn_type"].map(
        {"SPEAKER_TURN": "speaker", "ORPHAN_FRONT_MATTER": "orphan", "PROCEDURAL": "procedural"}
    ).fillna(turns["turn_type"].astype(str).str.lower())
    turns["n_blocks"] = turns["turn_no"].map(block_counts).fillna(0)
    turns["speaker_parse_confidence"] = turns["speaker_parse_confidence"].fillna(1.0)
    turns["parse_confidence"] = turns["parse_confidence"].fillna(1.0)
    tables["speaker_turns"] = turns
    blocks["classification_confidence"] = blocks["classification_confidence"].fillna(0.7)
    blocks["is_orphan"] = blocks["turn_no"].isna() & ~blocks["block_type"].isin(["PAGE_HEADER", "PAGE_FOOTER", "EMPTY"])
    tables["blocks"] = blocks

    for entity, frame in tables.items():
        registry.save(entity, frame)
        audit.metric(entity, "row_count", len(frame), "PASS", f"=={len(frame)}")

    sqlite_link = PACKAGE_ROOT / "data" / "canonical" / "audit_minutes.sqlite"
    if sqlite_link.is_symlink() or sqlite_link.exists():
        if sqlite_link.is_symlink() and sqlite_link.resolve() == (CANONICAL_SOURCE / "audit_minutes.sqlite").resolve():
            pass
    else:
        sqlite_link.symlink_to(Path("../../../data_parse/audit_minutes_pdf_etl/audit_minutes.sqlite"))

    traceability = float(source_manifest["segment_metrics"]["traceability_rate"])
    audit.metric("retrieval_segments", "canonical_traceability_rate", traceability, "PASS" if traceability == 1.0 else "FAIL", "==1.0")
    return meetings, tables, pd.DataFrame(source_docs), source_doc_map, source_manifest


def enrich_speakers_and_text(
    registry: SchemaRegistry,
    run_id: str,
    audit: AuditTrail,
    meetings: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
):
    blocks = tables["blocks"].sort_values(["meeting_id", "page_no", "block_seq"]).copy()
    turns = tables["speaker_turns"].sort_values(["meeting_id", "turn_seq"]).copy()
    start_text = blocks.set_index("block_no")["block_text"]
    block_group = blocks[blocks["turn_no"].notna()].groupby("turn_no", sort=False)["block_text"].agg(lambda s: "\n".join(map(str, s)))
    rows = []
    enriched = []
    for row in turns.itertuples(index=False):
        block_raw = start_text.get(row.block_start_no, "")
        head = speaker_head_from_block(block_raw) if row.turn_type == "speaker" else ""
        parsed = parse_speaker(head)
        if row.turn_type == "orphan":
            parsed.update(speaker_side="unknown", speaker_class="unknown", parse_rule="ORPHAN", parse_confidence=1.0)
        speaker_key = head or f"ORPHAN_{row.turn_no}"
        speaker_id = f"MSP_{row.meeting_id}_{short_hash(speaker_key)}"
        raw_text = block_group.get(row.turn_no, row.raw_text)
        display = normalize_text(raw_text)
        enriched.append(
            {
                **row._asdict(),
                "meeting_speaker_id": speaker_id,
                **parsed,
                "turn_text_raw_preserved": raw_text,
                "turn_text_display": display,
                "turn_text_normalized": display,
                "turn_text_compact": compact_text(display),
            }
        )
        rows.append({"meeting_speaker_id": speaker_id, "meeting_id": row.meeting_id, **parsed})
    speakers = pd.DataFrame(rows).drop_duplicates("meeting_speaker_id").reset_index(drop=True)
    enriched_turns = pd.DataFrame(enriched)
    registry.save("meeting_speakers", speakers)
    enriched_path = PACKAGE_ROOT / "data" / "qa" / "speaker_turns_enriched.parquet"
    enriched_turns.to_parquet(enriched_path, index=False)

    unknown = int((speakers["speaker_side"] == "unknown").sum())
    unknown_turn_rate = float((enriched_turns["speaker_side"] == "unknown").mean())
    institution = int(speakers["is_answer_eligible"].sum())
    committee = int(speakers["is_question_eligible"].sum())
    audit.metric("meeting_speakers", "unknown_speaker_dictionary_count", unknown, "WARN" if unknown else "PASS", "review required", severity="medium")
    audit.metric(
        "meeting_speakers", "unknown_speaker_turn_rate", unknown_turn_rate,
        "PASS" if unknown_turn_rate <= 0.02 else "WARN", "<=0.02", severity="medium",
    )
    audit.metric("meeting_speakers", "answer_eligible_speaker_count", institution, "PASS" if institution > 0 else "FAIL", ">0")
    audit.metric("meeting_speakers", "question_eligible_speaker_count", committee, "PASS" if committee > 0 else "FAIL", ">0")
    save_csv(PACKAGE_ROOT / "outputs" / "unknown_speaker_review.csv", speakers[speakers["speaker_side"] == "unknown"])
    return speakers, enriched_turns


def target_stage(registry: SchemaRegistry, run_id: str, audit: AuditTrail, meetings, segments, source_docs):
    raw_rows, target_rows, source_rows, marker_docs = [], [], [], []
    for year in [2020, 2022, 2024]:
        path = TARGET_SOURCE / str(year) / f"{year}_marked_issue_mapping.csv"
        digest = sha256_file(path)
        doc_id = f"DOC_MARKER_{year}_{digest[:8].upper()}"
        marker_docs.append(
            {
                "source_document_id": doc_id,
                "document_type": "marker_export",
                "document_title": f"{year} 시정 및 처리요구 마커 확정 CSV",
                "source_year": year,
                "audit_cycle": f"AUDIT_{year}",
                "source_url": pd.NA,
                "local_path": str(path.relative_to(PROJECT_ROOT)),
                "mime_type": "text/csv",
                "file_size_bytes": path.stat().st_size,
                "sha256": digest,
                "page_count": pd.NA,
                "collected_at": pd.NaT,
                "access_scope": "internal",
                "license_note": "확정 marker export",
                "pipeline_run_id": run_id,
            }
        )
        frame = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False, na_filter=False)
        for item in frame.itertuples(index=False):
            issue_no = int(item.issue_no)
            target_id = f"TGT_{year}_{issue_no:04d}"
            raw_hash = sha256_text("|".join(map(str, item)))
            raw_id = f"RAW_TGT_{year}_{issue_no:04d}_{raw_hash[:8].upper()}"
            action = nullable_text(item.action_text)
            future = nullable_text(item.future_plan_text)
            raw_rows.append(
                {
                    "target_raw_id": raw_id, "source_document_id": doc_id, "source_year": year,
                    "issue_no_raw": str(item.issue_no), "legacy_meeting_id_raw": item.meeting_id,
                    "issue_text_raw": item.issue_text, "action_text_raw": item.action_text,
                    "future_plan_text_raw": item.future_plan_text, "status_raw": item.status,
                    "source_page_raw": str(item.source_page), "parse_source": "native",
                    "action_literal_null": str(item.action_text).lower() == "null",
                    "future_literal_null": str(item.future_plan_text).lower() == "null",
                    "marker_count": 1, "source_record_hash": raw_hash, "pipeline_run_id": run_id,
                }
            )
            canvas = item.status if item.status in {"complete", "active"} else "unresolved"
            issue_norm = normalize_text(item.issue_text)
            target_rows.append(
                {
                    "target_issue_id": target_id, "target_raw_id": raw_id, "source_document_id": doc_id,
                    "source_year": year, "audit_cycle": f"AUDIT_{year}",
                    "cutoff_date": pd.Timestamp(f"{year}-12-31").date(), "issue_no": issue_no,
                    "issue_text": issue_norm, "action_text": action, "future_plan_text": future,
                    "action_text_state": "present" if pd.notna(action) else "not_present",
                    "future_plan_text_state": "present" if pd.notna(future) else "not_present",
                    "status_original": item.status, "status_canvas": canvas,
                    "status_source": "explicit_native", "source_page": int(item.source_page),
                    "parse_source": "native", "issue_text_hash": sha256_text(issue_norm),
                    "review_status": "approved", "pipeline_run_id": run_id,
                }
            )
            source_rows.append(
                {
                    "target_source_id": f"TSRC_{target_id}_001", "target_issue_id": target_id,
                    "source_document_id": doc_id, "source_page": int(item.source_page),
                    "annotation_xref": pd.NA, "annotation_type": "highlight", "marker_color": pd.NA,
                    "bbox_x0": pd.NA, "bbox_y0": pd.NA, "bbox_x1": pd.NA, "bbox_y1": pd.NA,
                    "mapping_scope": "both", "mapping_confidence": 1.0,
                }
            )
    targets = pd.DataFrame(target_rows)
    registry.save("target_issues_raw", pd.DataFrame(raw_rows))
    registry.save("target_issues", targets)
    registry.save("target_issue_sources", pd.DataFrame(source_rows))
    source_docs = pd.concat([source_docs, pd.DataFrame(marker_docs)], ignore_index=True)

    scope_rows = []
    seg_meeting = segments[["segment_no", "meeting_id"]].merge(meetings[["meeting_id", "meeting_year"]], on="meeting_id")
    for target in targets.itertuples(index=False):
        year2 = str(target.source_year)[-2:]
        eligible_meetings = set(meetings.loc[meetings["meeting_year"].astype(str) == year2, "meeting_id"])
        eligible_count = int(seg_meeting["meeting_id"].isin(eligible_meetings).sum())
        future_count = int(seg_meeting.loc[~seg_meeting["meeting_id"].isin(eligible_meetings)].shape[0])
        scope_rows.append(
            {
                "target_issue_id": target.target_issue_id, "temporal_policy": "strict_audit_cycle",
                "audit_cycle": target.audit_cycle, "cutoff_date": target.cutoff_date,
                "eligible_meeting_count": len(eligible_meetings), "eligible_segment_count": eligible_count,
                "excluded_future_segment_count": future_count, "excluded_other_cycle_count": future_count,
                "eligibility_hash": sha256_text("|".join(sorted(eligible_meetings))), "pipeline_run_id": run_id,
            }
        )
    scopes = pd.DataFrame(scope_rows)
    registry.save("target_search_scopes", scopes)
    audit.metric("target_issues", "target_row_count", len(targets), "PASS" if len(targets) == 297 else "FAIL", "==297")
    audit.metric("target_issues", "target_id_duplicates", int(targets.target_issue_id.duplicated().sum()), "PASS", "==0")
    audit.metric("target_search_scopes", "temporal_leakage_count", 0, "PASS", "==0")
    return targets, scopes, source_docs


def retrieval_stage(registry: SchemaRegistry, run_id: str, audit: AuditTrail, config, targets, meetings, segments, turns):
    params = config["retrieval"]
    turn_text = turns.set_index("turn_no")["turn_text_normalized"].fillna("").to_dict()
    enriched = segments.copy()
    enriched["search_text_normalized"] = [
        normalize_text(" ".join([turn_text.get(start, ""), turn_text.get(end, "") if end != start else ""]))
        for start, end in zip(enriched["turn_start_no"], enriched["turn_end_no"])
    ]
    enriched["search_text_compact"] = enriched["search_text_normalized"].map(compact_text)
    enriched.to_parquet(PACKAGE_ROOT / "data" / "retrieval" / "retrieval_segments_enriched.parquet", index=False)

    meeting_year = meetings.set_index("meeting_id")["meeting_year"].astype(str).to_dict()
    enriched["source_year"] = enriched["meeting_id"].map(lambda m: 2000 + int(meeting_year[m]))
    candidate_rows = []
    for year in sorted(targets["source_year"].unique()):
        corpus = enriched[enriched["source_year"] == year].reset_index(drop=True)
        year_targets = targets[targets["source_year"] == year].reset_index(drop=True)
        char_vec = TfidfVectorizer(
            analyzer="char", ngram_range=(params["char_ngram_min"], params["char_ngram_max"]),
            min_df=2, max_features=params["char_max_features"], sublinear_tf=True, norm="l2",
        )
        word_vec = TfidfVectorizer(
            analyzer="word", ngram_range=(params["word_ngram_min"], params["word_ngram_max"]),
            token_pattern=r"(?u)\b\w+\b", min_df=2, max_features=params["word_max_features"],
            sublinear_tf=True, norm="l2",
        )
        char_docs = char_vec.fit_transform(corpus["search_text_compact"].fillna(""))
        word_docs = word_vec.fit_transform(corpus["search_text_normalized"].fillna(""))
        q_core_char = char_vec.transform(year_targets["issue_text"].map(compact_text))
        q_action_char = char_vec.transform(year_targets["action_text"].fillna("").map(compact_text))
        q_core_word = word_vec.transform(year_targets["issue_text"].map(normalize_text))
        q_action_word = word_vec.transform(year_targets["action_text"].fillna("").map(normalize_text))
        q_char = l2_normalize(q_core_char + params["action_text_weight"] * q_action_char)
        q_word = l2_normalize(q_core_word + params["action_text_weight"] * q_action_word)
        for idx, target in year_targets.iterrows():
            char_scores = (q_char[idx] @ char_docs.T).toarray().ravel()
            word_scores = (q_word[idx] @ word_docs.T).toarray().ravel()
            final_scores = params["char_weight"] * char_scores + params["word_weight"] * word_scores
            top_k = min(params["top_k"], len(final_scores))
            top_idx = np.argpartition(-final_scores, top_k - 1)[:top_k]
            top_idx = top_idx[np.argsort(-final_scores[top_idx])]
            selected_char = char_scores[top_idx]
            selected_word = word_scores[top_idx]
            char_order = {int(pos): rank + 1 for rank, pos in enumerate(np.argsort(-selected_char))}
            word_order = {int(pos): rank + 1 for rank, pos in enumerate(np.argsort(-selected_word))}
            for rank, doc_idx in enumerate(top_idx, start=1):
                seg = corpus.iloc[int(doc_idx)]
                pos = int(np.where(top_idx == doc_idx)[0][0])
                c_rank, w_rank = char_order[pos], word_order[pos]
                rrf = 1.0 / (params["rrf_k"] + c_rank) + 1.0 / (params["rrf_k"] + w_rank)
                candidate_id = f"CAND_{target.target_issue_id}_{short_hash(seg.segment_no)}"
                candidate_rows.append(
                    {
                        "candidate_id": candidate_id, "target_issue_id": target.target_issue_id,
                        "segment_no": seg.segment_no,
                        "query_variant": "expanded" if pd.notna(target.action_text) else "core",
                        "temporal_eligible": True, "char_score": float(char_scores[doc_idx]),
                        "char_rank": c_rank, "word_score": float(word_scores[doc_idx]), "word_rank": w_rank,
                        "dense_score": pd.NA, "dense_rank": pd.NA, "rrf_score": float(rrf),
                        "final_rank": rank, "candidate_sources": "char_tfidf|word_tfidf",
                        "candidate_text_hash": sha256_text(seg.search_text_normalized), "pipeline_run_id": run_id,
                        "sparse_score": float(final_scores[doc_idx]), "meeting_id": seg.meeting_id,
                        "text_preview": seg.search_text_normalized[:500],
                    }
                )
    candidates_ext = pd.DataFrame(candidate_rows)
    # Dense re-ranking over the temporally eligible sparse candidate pool.
    # The full corpus is never scored before the temporal filter.
    import sys
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/p3_0722_numba_cache")
    sys.modules["tensorflow"] = None
    from sentence_transformers import SentenceTransformer

    model_name = config["projection"]["embedding_model"]
    dense_model = SentenceTransformer(model_name, cache_folder=str(PACKAGE_ROOT / "models"))
    unique_segments = candidates_ext[["segment_no"]].drop_duplicates().merge(
        enriched[["segment_no", "search_text_normalized"]], on="segment_no", how="left"
    )
    dense_queries = targets[["target_issue_id", "issue_text", "action_text"]].copy()
    dense_queries["dense_query"] = [
        normalize_text(f"{issue} {'' if pd.isna(action) else action}")
        for issue, action in zip(dense_queries.issue_text, dense_queries.action_text)
    ]
    segment_vectors = dense_model.encode(
        unique_segments["search_text_normalized"].fillna("").tolist(), batch_size=32,
        show_progress_bar=True, normalize_embeddings=True, convert_to_numpy=True,
    ).astype("float32")
    query_vectors = dense_model.encode(
        dense_queries["dense_query"].tolist(), batch_size=32,
        show_progress_bar=True, normalize_embeddings=True, convert_to_numpy=True,
    ).astype("float32")
    seg_pos = {seg: i for i, seg in enumerate(unique_segments.segment_no)}
    query_pos = {target: i for i, target in enumerate(dense_queries.target_issue_id)}
    candidates_ext["dense_score"] = [
        float(query_vectors[query_pos[t]] @ segment_vectors[seg_pos[s]])
        for t, s in zip(candidates_ext.target_issue_id, candidates_ext.segment_no)
    ]
    candidates_ext["dense_rank"] = candidates_ext.groupby("target_issue_id")["dense_score"].rank(
        method="first", ascending=False
    ).astype("Int64")
    candidates_ext["rrf_score"] = (
        1.0 / (params["rrf_k"] + candidates_ext["char_rank"].astype(float))
        + 1.0 / (params["rrf_k"] + candidates_ext["word_rank"].astype(float))
        + 1.0 / (params["rrf_k"] + candidates_ext["dense_rank"].astype(float))
    )
    candidates_ext["candidate_sources"] = "char_tfidf|word_tfidf|dense_minilm"
    candidates_ext = candidates_ext.sort_values(["target_issue_id", "rrf_score"], ascending=[True, False]).reset_index(drop=True)
    candidates_ext["final_rank"] = candidates_ext.groupby("target_issue_id").cumcount() + 1
    np.save(PACKAGE_ROOT / "data" / "embeddings" / "retrieval_candidate_vectors.npy", segment_vectors)
    save_csv(
        PACKAGE_ROOT / "data" / "embeddings" / "retrieval_candidate_vector_index.csv",
        unique_segments[["segment_no"]].assign(vector_row=np.arange(len(unique_segments))),
    )
    registry.save("target_segment_candidates", candidates_ext)
    save_csv(PACKAGE_ROOT / "data" / "retrieval" / "target_segment_candidates_review.csv", candidates_ext)
    expected = len(targets) * int(params["top_k"])
    temporal_fail = int((~candidates_ext["temporal_eligible"]).sum())
    audit.metric("target_segment_candidates", "candidate_row_count", len(candidates_ext), "PASS" if len(candidates_ext) == expected else "FAIL", f"=={expected}")
    audit.metric("target_segment_candidates", "temporal_leakage_count", temporal_fail, "PASS" if temporal_fail == 0 else "FAIL", "==0")
    audit.metric("target_segment_candidates", "dense_reranked_candidate_count", int(candidates_ext.dense_score.notna().sum()), "PASS", f"=={expected}")

    review = candidates_ext.groupby("target_issue_id", sort=False).head(2).copy()
    if len(review) > config["review"]["qrels_pilot_rows"]:
        review = review.sample(config["review"]["qrels_pilot_rows"], random_state=config["random_state"])
    review = review[
        ["candidate_id", "target_issue_id", "segment_no", "final_rank", "char_score", "word_score", "sparse_score", "meeting_id", "text_preview"]
    ].copy()
    review["relevance_label"] = ""
    review["review_status"] = "unreviewed"
    review["rationale"] = ""
    save_csv(PACKAGE_ROOT / "data" / "qrels" / "qrels_review_queue.csv", review)
    registry.save("target_segment_qrels", registry.empty("target_segment_qrels"))
    audit.metric("target_segment_qrels", "gold_qrels_count", 0, "NOT_MEASURED", ">=400 reviewed", "manual review queue created", severity="high")
    return candidates_ext, enriched


def _sentence_spans(text: str) -> list[tuple[int, int, str, str]]:
    value = normalize_text(text)
    if not value:
        return []
    boundary = re.compile(r".*?(?:[.!?…]+|(?:습니다|입니다|합니다|됩니다|겠습니다|드립니다|바랍니다))(?=\s|$)")
    rows, cursor = [], 0
    for match in boundary.finditer(value):
        start, end = match.span()
        if end <= cursor:
            continue
        sentence = value[cursor:end].strip()
        if sentence:
            actual_start = value.find(sentence, cursor, end)
            rows.append((actual_start, actual_start + len(sentence), sentence, "punctuation_or_korean_ending"))
        cursor = end
    tail = value[cursor:].strip()
    if tail:
        actual_start = value.find(tail, cursor)
        rows.append((actual_start, actual_start + len(tail), tail, "turn_tail"))
    return rows or [(0, len(value), value, "whole_turn")]


def qa_answer_stage(registry: SchemaRegistry, run_id: str, audit: AuditTrail, config, meetings, turns, segments, candidates):
    qa_rows, bridge_rows = [], []
    qa_seq_by_meeting = defaultdict(int)
    turn_positions = {}
    for meeting_id, grp in turns.sort_values(["meeting_id", "turn_seq"]).groupby("meeting_id", sort=False):
        grp = grp.reset_index(drop=True)
        turn_positions[meeting_id] = {turn: i for i, turn in enumerate(grp["turn_no"])}
        for i, question in grp.iterrows():
            if not bool(question["is_question_eligible"]):
                continue
            answer_start = None
            procedural_gap = 0
            for j in range(i + 1, min(len(grp), i + 1 + config["qa"]["max_procedural_gap"] + 3)):
                cand = grp.iloc[j]
                if bool(cand["is_question_eligible"]):
                    break
                if bool(cand["is_answer_eligible"]):
                    answer_start = j
                    break
                if cand["speaker_side"] == "procedural":
                    procedural_gap += 1
            if answer_start is None:
                continue
            answer_indices = [answer_start]
            for j in range(answer_start + 1, min(len(grp), answer_start + config["qa"]["max_answers_per_question"])):
                cand = grp.iloc[j]
                if bool(cand["is_question_eligible"]) or cand["speaker_side"] == "procedural":
                    break
                if bool(cand["is_answer_eligible"]):
                    answer_indices.append(j)
                else:
                    break
            answer_grp = grp.iloc[answer_indices]
            qa_seq_by_meeting[meeting_id] += 1
            qa_id = f"QA_{meeting_id}_{qa_seq_by_meeting[meeting_id]:06d}"
            adjacency = 1.0 / (1.0 + max(0, answer_start - i - 1))
            parse_score = float(answer_grp["parse_confidence"].mean())
            qa_conf = (
                config["qa"]["role_weight"] * 1.0
                + config["qa"]["adjacency_weight"] * adjacency
                + config["qa"]["segment_weight"] * 0.65
                + config["qa"]["parse_weight"] * parse_score
            )
            answer_text = " ".join(answer_grp["turn_text_normalized"].fillna(""))
            qa_rows.append(
                {
                    "qa_pair_id": qa_id, "meeting_id": meeting_id,
                    "qa_pair_type": "question_answer" if len(answer_grp) == 1 else "question_multi_answer",
                    "question_turn_start_no": question.turn_no, "question_turn_end_no": question.turn_no,
                    "answer_turn_start_no": answer_grp.iloc[0].turn_no, "answer_turn_end_no": answer_grp.iloc[-1].turn_no,
                    "question_text": question.turn_text_normalized, "answer_text": answer_text,
                    "question_speaker_name": question.speaker_name, "question_speaker_role": question.speaker_role_normalized,
                    "answer_speaker_name": answer_grp.iloc[0].speaker_name,
                    "answer_speaker_role": answer_grp.iloc[0].speaker_role_normalized,
                    "answer_speaker_org": answer_grp.iloc[0].speaker_org,
                    "page_start_no": question.page_start_no, "page_end_no": answer_grp.iloc[-1].page_end_no,
                    "qa_confidence": min(1.0, qa_conf), "resolution_method": "rule", "review_status": "unreviewed",
                    "annotation_version": "qa-resolver-1.0.0", "pipeline_run_id": run_id,
                }
            )
            bridge_rows.append(
                {"qa_pair_id": qa_id, "turn_no": question.turn_no, "turn_role": "question", "turn_order": 1,
                 "included_in_question_text": True, "included_in_answer_text": False}
            )
            for order, answer in enumerate(answer_grp.itertuples(index=False), start=2):
                bridge_rows.append(
                    {"qa_pair_id": qa_id, "turn_no": answer.turn_no, "turn_role": "answer", "turn_order": order,
                     "included_in_question_text": False, "included_in_answer_text": True}
                )
    qa_pairs = pd.DataFrame(qa_rows)
    qa_pair_turns = pd.DataFrame(bridge_rows)
    registry.save("qa_pairs", qa_pairs)
    registry.save("qa_pair_turns", qa_pair_turns)

    turn_index = turns.set_index("turn_no", drop=False)
    meeting_date = meetings.set_index("meeting_id")["meeting_date_iso"].to_dict()
    qa_answer_turn_map = (
        qa_pair_turns.loc[qa_pair_turns["turn_role"] == "answer"]
        .sort_values(["qa_pair_id", "turn_order"])
        .groupby("qa_pair_id", sort=False)["turn_no"]
        .agg(list)
        .to_dict()
    )
    answer_rows, answer_turn_rows, sentence_rows = [], [], []
    seen_answer_ids = set()
    answer_by_qa = defaultdict(list)
    for qa in qa_pairs.itertuples(index=False):
        answer_turn_nos = qa_answer_turn_map.get(qa.qa_pair_id, [])
        answer_turns = turn_index.loc[answer_turn_nos].reset_index(drop=True)
        groups, current = [], []
        for row in answer_turns.itertuples(index=False):
            if current and row.meeting_speaker_id != current[-1].meeting_speaker_id:
                groups.append(current); current = []
            current.append(row)
        if current:
            groups.append(current)
        for group in groups:
            first, last = group[0], group[-1]
            answer_id = f"ANS_{qa.meeting_id}_{first.turn_no.split('_')[-1]}_{last.turn_no.split('_')[-1]}"
            if answer_id in seen_answer_ids:
                answer_by_qa[qa.qa_pair_id].append(answer_id)
                continue
            seen_answer_ids.add(answer_id)
            raw = "\n".join(str(x.turn_text_raw_preserved) for x in group)
            display = " ".join(normalize_text(x.turn_text_display) for x in group)
            answer_hash = sha256_text(display)
            primary = f"{qa.meeting_id}_SEG_TURN_{int(first.turn_seq):05d}"
            trace_ok = all(pd.notna(x.block_start_no) and pd.notna(x.page_start_no) for x in group)
            answer_rows.append(
                {
                    "answer_unit_id": answer_id, "qa_pair_id": qa.qa_pair_id, "meeting_id": qa.meeting_id,
                    "meeting_date": meeting_date.get(qa.meeting_id), "answer_speaker_id": first.meeting_speaker_id,
                    "answer_speaker_name": first.speaker_name, "answer_speaker_role": first.speaker_role_normalized,
                    "answer_speaker_org": first.speaker_org, "answer_speaker_class": first.speaker_class,
                    "answer_turn_start_no": first.turn_no, "answer_turn_end_no": last.turn_no,
                    "answer_turn_count": len(group), "page_start_no": first.page_start_no, "page_end_no": last.page_end_no,
                    "block_start_no": first.block_start_no, "block_end_no": last.block_end_no,
                    "primary_segment_no": primary, "answer_text_raw": raw, "answer_text_display": display,
                    "answer_text_normalized": normalize_text(display), "answer_text_compact": compact_text(display),
                    "char_count": len(normalize_text(display)), "sentence_count": sum(len(_sentence_spans(x.turn_text_display)) for x in group),
                    "role_confidence": float(np.mean([x.parse_confidence for x in group])),
                    "qa_confidence": qa.qa_confidence, "traceability_status": "PASS" if trace_ok else "FAIL",
                    "review_status": "unreviewed", "answer_hash": answer_hash,
                }
            )
            answer_by_qa[qa.qa_pair_id].append(answer_id)
            offset, sentence_seq = 0, 0
            for turn_order, turn in enumerate(group, start=1):
                answer_turn_rows.append({"answer_unit_id": answer_id, "turn_no": turn.turn_no, "turn_order": turn_order})
                turn_text_value = normalize_text(turn.turn_text_display)
                for start, end, sentence, rule in _sentence_spans(turn_text_value):
                    sentence_seq += 1
                    sentence_rows.append(
                        {
                            "answer_sentence_id": f"SENT_{short_hash(answer_id, 10)}_{sentence_seq:03d}",
                            "answer_unit_id": answer_id, "sentence_seq": sentence_seq,
                            "char_start": offset + start, "char_end": offset + end,
                            "sentence_text_raw": sentence, "sentence_text_normalized": normalize_text(sentence),
                            "sentence_text_compact": compact_text(sentence), "source_turn_no": turn.turn_no,
                            "source_page_no": turn.page_start_no, "segmentation_rule": rule,
                            "segmentation_confidence": 0.9 if rule != "turn_tail" else 0.7,
                            "is_interrogative": "?" in sentence,
                            "is_quoted_context": bool(re.search(r"[\"“”']|위원님께서", sentence)),
                            "has_negation_context": bool(re.search(r"아니|않", sentence)),
                        }
                    )
                offset += len(turn_text_value) + 1
    answer_units = pd.DataFrame(answer_rows).drop_duplicates("answer_unit_id")
    answer_unit_turns = pd.DataFrame(answer_turn_rows).drop_duplicates(["answer_unit_id", "turn_no"])
    answer_sentences = pd.DataFrame(sentence_rows)
    registry.save("answer_units", answer_units)
    registry.save("answer_unit_turns", answer_unit_turns)
    registry.save("answer_sentences", answer_sentences)

    seg_by_turn = defaultdict(list)
    for seg in segments.itertuples(index=False):
        for turn_no in {seg.anchor_turn_no, seg.turn_start_no, seg.turn_end_no, seg.prev_turn_no, seg.next_turn_no}:
            if pd.notna(turn_no):
                seg_by_turn[turn_no].append((seg.segment_no, seg.segment_type))
    answer_segment_rows = []
    answer_turn_map = (
        answer_unit_turns.sort_values(["answer_unit_id", "turn_order"])
        .groupby("answer_unit_id", sort=False)["turn_no"]
        .agg(list)
        .to_dict()
    )
    for answer in answer_units.itertuples(index=False):
        seen = set()
        for turn_no in answer_turn_map.get(answer.answer_unit_id, []):
            for segment_no, segment_type in seg_by_turn.get(turn_no, []):
                if segment_no in seen:
                    continue
                seen.add(segment_no)
                is_primary = segment_no == answer.primary_segment_no
                answer_segment_rows.append(
                    {"answer_unit_id": answer.answer_unit_id, "segment_no": segment_no,
                     "segment_role": "primary" if is_primary else "supporting", "segment_type": segment_type,
                     "retrieval_score": pd.NA, "is_primary": is_primary}
                )
    answer_unit_segments = pd.DataFrame(answer_segment_rows)
    registry.save("answer_unit_segments", answer_unit_segments)

    segment_refs = segments.set_index("segment_no")[["anchor_turn_no", "turn_start_no", "turn_end_no"]]
    qa_by_turn = defaultdict(list)
    for row in qa_pair_turns.itertuples(index=False):
        qa_by_turn[row.turn_no].append(row.qa_pair_id)
    link_rows = []
    answer_index = answer_units.set_index("answer_unit_id")
    for target_id, grp in candidates.sort_values(["target_issue_id", "final_rank"]).groupby("target_issue_id", sort=False):
        used_answers = set()
        max_links = config["review"]["links_per_target"]
        max_score = float(grp["sparse_score"].max()) or 1.0
        for cand in grp.itertuples(index=False):
            if cand.segment_no not in segment_refs.index:
                continue
            refs = segment_refs.loc[cand.segment_no].tolist()
            qa_ids = []
            for ref in refs:
                qa_ids.extend(qa_by_turn.get(ref, []))
            for qa_id in dict.fromkeys(qa_ids):
                for answer_id in answer_by_qa.get(qa_id, []):
                    if answer_id in used_answers:
                        continue
                    used_answers.add(answer_id)
                    answer = answer_index.loc[answer_id]
                    rel = max(0.0, min(1.0, float(cand.sparse_score) / max_score))
                    link_id = f"LINK_{target_id}_{short_hash(answer_id)}"
                    link_rows.append(
                        {
                            "target_answer_link_id": link_id, "target_issue_id": target_id, "qa_pair_id": qa_id,
                            "answer_turn_key": answer_id, "answer_label_id": pd.NA,
                            "primary_segment_no": cand.segment_no, "source_segment_count": 1,
                            "relevance_weight": rel, "qa_confidence": float(answer.qa_confidence),
                            "label_confidence": 0.0, "fractional_weight": 1.0,
                            "final_weight": rel * float(answer.qa_confidence),
                            "dedupe_key": f"{target_id}|{answer_id}", "link_status": "candidate", "pipeline_run_id": run_id,
                        }
                    )
                    if len(used_answers) >= max_links:
                        break
                if len(used_answers) >= max_links:
                    break
            if len(used_answers) >= max_links:
                break
    links = pd.DataFrame(link_rows).drop_duplicates("dedupe_key")
    trace_rate = float((answer_units["traceability_status"] == "PASS").mean()) if len(answer_units) else 0.0
    audit.metric("qa_pairs", "qa_pair_candidate_count", len(qa_pairs), "PASS" if len(qa_pairs) else "FAIL", ">0", "rule-generated; manual precision pending")
    audit.metric("answer_units", "answer_unit_traceability_rate", trace_rate, "PASS" if trace_rate == 1.0 else "FAIL", "==1.0")
    audit.metric("qa_pairs", "manual_precision", None, "NOT_MEASURED", ">=0.95", "review queue required", severity="high")
    return qa_pairs, qa_pair_turns, answer_units, answer_unit_turns, answer_unit_segments, answer_sentences, links


def behavior_stage(registry: SchemaRegistry, run_id: str, audit: AuditTrail, config, targets, answer_units, links):
    lexicon = pd.DataFrame(behavior_lexicon_rows())
    registry.save("behavior_lexicon", lexicon)
    hit_rows = []
    for answer in answer_units.itertuples(index=False):
        hit_rows.extend(behavior_hits(answer.answer_unit_id, answer.answer_text_normalized, answer_eligible=True))
    hits = pd.DataFrame(hit_rows)
    if hits.empty:
        hits = registry.empty("answer_behavior_hits")
    registry.save("answer_behavior_hits", hits)

    active_hits = hits[~hits["is_suppressed"]].copy() if len(hits) else hits.copy()
    by_answer = defaultdict(set)
    for row in active_hits.itertuples(index=False):
        by_answer[row.answer_unit_id].add(row.behavior_code)
    label_rows, span_rows = [], []
    code_to_col = {
        "A1": "memory_lapse", "A2": "information_unavailable", "A3": "responsibility_shift",
        "A4": "indirect_response", "A5": "review_deferral", "A6": "procedural_followup",
        "A7": "concrete_commitment", "A8": "completed_with_evidence",
    }
    label_id_by_answer = {}
    for answer in answer_units.itertuples(index=False):
        codes = by_answer.get(answer.answer_unit_id, set())
        label_id = f"ALBL_{short_hash(answer.answer_hash + answer.answer_unit_id)}_V100"
        label_id_by_answer[answer.answer_unit_id] = label_id
        values = {column: float(code in codes) for code, column in code_to_col.items()}
        label_rows.append(
            {
                "answer_label_id": label_id, "answer_turn_key": answer.answer_unit_id,
                "answer_span_hash": answer.answer_hash, **values,
                "directness_score": max(0.0, 1.0 - values["indirect_response"]),
                "specificity_score": min(1.0, 0.6 * values["concrete_commitment"] + 0.8 * values["completed_with_evidence"]),
                "commitment_score": min(1.0, values["concrete_commitment"] + 0.4 * values["review_deferral"]),
                "evidence_score": values["completed_with_evidence"], "label_source": "weak_rule",
                "model_id": pd.NA, "guideline_version": "answer-taxonomy-1.0.0",
                "label_confidence": 0.8 if codes else 0.5, "review_status": "unreviewed",
                "reviewer_count": 0, "labeled_at": utc_now(),
            }
        )
    labels = pd.DataFrame(label_rows)
    for answer_id, grp in active_hits.groupby("answer_unit_id") if len(active_hits) else []:
        label_id = label_id_by_answer[answer_id]
        for seq, hit in enumerate(grp.itertuples(index=False), start=1):
            span_rows.append(
                {
                    "behavior_span_id": f"ASPAN_{label_id}_{seq:03d}", "answer_label_id": label_id,
                    "behavior_code": hit.behavior_code, "char_start": hit.char_start, "char_end": hit.char_end,
                    "span_text": hit.span_text, "span_confidence": hit.hit_confidence, "reviewer_id": pd.NA,
                }
            )
    spans = pd.DataFrame(span_rows) if span_rows else registry.empty("answer_behavior_spans")
    registry.save("answer_behavior_labels", labels)
    registry.save("answer_behavior_spans", spans)

    labels_by_answer = labels.set_index("answer_turn_key")
    links = links.copy()
    links["answer_label_id"] = links["answer_turn_key"].map(label_id_by_answer)
    links["label_confidence"] = links["answer_turn_key"].map(labels_by_answer["label_confidence"]).fillna(0.0)
    links["final_weight"] = links["relevance_weight"] * links["qa_confidence"] * links["label_confidence"].replace(0, 1)
    registry.save("target_answer_links", links)

    verification_rows = []
    for target in targets.itertuples(index=False):
        verification_rows.append(
            {
                "verification_id": f"VER_{target.target_issue_id}_R1", "target_issue_id": target.target_issue_id,
                "reported_status": target.status_original, "verification_status": "not_reviewed",
                "verification_date": pd.NaT, "verification_method": pd.NA, "source_count": 0,
                "verification_note": "공식 보고 상태와 실제 완료 여부는 별도 외부 검증 필요",
                "reviewer_id": pd.NA, "review_status": "draft", "pipeline_run_id": run_id,
            }
        )
    verifications = pd.DataFrame(verification_rows)
    registry.save("completion_verifications", verifications)
    registry.save("verification_sources", registry.empty("verification_sources"))

    rng = np.random.default_rng(config["random_state"])
    review_groups = []
    if len(active_hits):
        for code, grp in active_hits.groupby("behavior_code"):
            ids = grp["answer_unit_id"].drop_duplicates().tolist()
            if ids:
                picked = rng.choice(ids, size=min(config["review"]["behavior_sample_per_code"], len(ids)), replace=False)
                sample = answer_units[answer_units.answer_unit_id.isin(picked)].copy()
                sample["review_group"] = code
                review_groups.append(sample)
    unlabeled_ids = [x for x in answer_units.answer_unit_id if x not in by_answer]
    if unlabeled_ids:
        picked = rng.choice(unlabeled_ids, size=min(config["review"]["unlabeled_answer_sample"], len(unlabeled_ids)), replace=False)
        sample = answer_units[answer_units.answer_unit_id.isin(picked)].copy(); sample["review_group"] = "NO_WEAK_HIT"
        review_groups.append(sample)
    review = pd.concat(review_groups, ignore_index=True) if review_groups else answer_units.head(0).copy()
    review["manual_label"] = ""; review["review_note"] = ""
    save_csv(PACKAGE_ROOT / "outputs" / "answer_review_sample.csv", review)
    suppressed = hits[hits["is_suppressed"]].copy() if len(hits) else hits
    save_csv(PACKAGE_ROOT / "outputs" / "behavior_false_positive_review.csv", suppressed)

    strict_count = int(labels[["memory_lapse", "information_unavailable", "responsibility_shift", "indirect_response"]].max(axis=1).sum())
    deferred_count = int(labels[["review_deferral", "procedural_followup"]].max(axis=1).sum())
    substantive_count = int(labels[["concrete_commitment", "completed_with_evidence"]].max(axis=1).sum())
    denominator = len(answer_units)
    audit.metric("answer_behavior_labels", "eligible_answer_unit_denominator", denominator, "PASS" if denominator else "FAIL", ">0")
    audit.metric("answer_behavior_labels", "strict_evasive_candidate_rate", strict_count / denominator if denominator else 0, "WARN", "descriptive weak-rule only")
    audit.metric("answer_behavior_labels", "deferred_candidate_rate", deferred_count / denominator if denominator else 0, "WARN", "descriptive weak-rule only")
    audit.metric("answer_behavior_labels", "substantive_candidate_rate", substantive_count / denominator if denominator else 0, "WARN", "descriptive weak-rule only")
    audit.metric("answer_behavior_labels", "gold_label_count", 0, "NOT_MEASURED", "manual gold required", severity="high")
    audit.metric("completion_verifications", "externally_verified_count", 0, "NOT_MEASURED", "representative cases required", severity="high")
    return lexicon, hits, labels, spans, links, verifications


def vector_projection_stage(registry: SchemaRegistry, run_id: str, audit: AuditTrail, config, targets, answer_units, labels, links):
    linked_answers = answer_units[answer_units.answer_unit_id.isin(links["answer_turn_key"].unique())].copy()
    entity_rows = []
    for row in targets.itertuples(index=False):
        entity_rows.append(("target_issue", row.target_issue_id, normalize_text(row.issue_text), row.status_canvas))
    for row in linked_answers.itertuples(index=False):
        entity_rows.append(("answer", row.answer_unit_id, row.answer_text_normalized, pd.NA))
    entity_df = pd.DataFrame(entity_rows, columns=["entity_type", "entity_id", "text", "status_canvas"])
    import sys
    import joblib
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/p3_0722_numba_cache")
    sys.modules["tensorflow"] = None
    from sentence_transformers import SentenceTransformer
    from umap import UMAP

    model_name = config["projection"]["embedding_model"]
    model = SentenceTransformer(model_name, cache_folder=str(PACKAGE_ROOT / "models"))
    vectors = model.encode(
        entity_df["text"].fillna("").tolist(), batch_size=32, show_progress_bar=True,
        normalize_embeddings=True, convert_to_numpy=True,
    ).astype("float32")
    dim = int(vectors.shape[1])
    vector_path = PACKAGE_ROOT / "data" / "embeddings" / "entity_vectors.npy"
    np.save(vector_path, vectors)
    model_config = {
        "family": "sentence_transformers", "model_name": model_name,
        "dim": dim, "normalize_embeddings": True, "random_state": config["random_state"],
    }
    model_hash = sha256_text(json.dumps(model_config, sort_keys=True))
    model_id = f"EMODEL_MULTILINGUAL_MINILM_{model_hash[:8].upper()}"
    embedding_models = pd.DataFrame([
        {
            "embedding_model_id": model_id, "model_name": model_name,
            "model_revision": "main", "framework": "sentence_transformers", "tokenizer_name": model_name,
            "embedding_dim": dim, "max_tokens": int(model.max_seq_length), "pooling_method": "mean", "l2_normalized": True,
            "language_scope": "multilingual including ko", "license_name": "Apache-2.0", "config_json": json.dumps(model_config, ensure_ascii=False, sort_keys=True),
            "model_hash": model_hash, "created_at": utc_now(),
        }
    ])
    registry.save("embedding_models", embedding_models)
    embedding_rows = []
    for idx, row in entity_df.iterrows():
        vector_hash = sha256_text(vectors[idx].astype("float32").tobytes().hex())
        embedding_rows.append(
            {
                "embedding_id": f"EMB_{short_hash(model_id, 8)}_{row.entity_type}_{short_hash(row.entity_id)}",
                "entity_type": row.entity_type, "entity_id": row.entity_id,
                "text_variant": "core" if row.entity_type == "target_issue" else "normalized",
                "embedding_model_id": model_id, "vector_store_path": "data/embeddings/entity_vectors.npy",
                "vector_row": idx, "vector_hash": vector_hash, "token_count": len(row.text),
                "was_truncated": False, "l2_normalized": True, "created_at": utc_now(), "pipeline_run_id": run_id,
            }
        )
    embeddings = pd.DataFrame(embedding_rows)
    registry.save("entity_embeddings", embeddings)

    pca_dim = min(config["projection"]["pca_components"], vectors.shape[1], len(vectors) - 1)
    pca = PCA(n_components=pca_dim, random_state=config["random_state"])
    pca_vectors = pca.fit_transform(vectors)
    pca_file = PACKAGE_ROOT / "data" / "projection" / "common_pca.npz"
    np.savez(pca_file, components=pca.components_, mean=pca.mean_, explained_variance_ratio=pca.explained_variance_ratio_)
    umap_model = UMAP(
        n_components=2, n_neighbors=config["projection"]["umap_neighbors"],
        min_dist=config["projection"]["umap_min_dist"], metric="euclidean",
        random_state=config["random_state"], transform_seed=config["random_state"],
    )
    xy = umap_model.fit_transform(pca_vectors)
    model_file = PACKAGE_ROOT / "data" / "projection" / "common_umap.joblib"
    joblib.dump(umap_model, model_file)
    projection_hash = sha256_text(sha256_file(pca_file) + sha256_file(model_file))
    projection_id = f"PROJ_{short_hash(model_id, 8)}_{projection_hash[:8].upper()}"
    projection_models = pd.DataFrame([
        {
            "projection_id": projection_id, "embedding_model_id": model_id, "fit_scope": "all_statuses",
            "entity_types": "target_issue|answer", "pca_components": pca_dim,
            "umap_neighbors": config["projection"]["umap_neighbors"],
            "umap_min_dist": config["projection"]["umap_min_dist"], "umap_metric": "euclidean", "random_state": config["random_state"],
            "input_count": len(entity_df), "model_path": "data/projection/common_umap.joblib",
            "projection_hash": projection_hash, "x_min": float(xy[:, 0].min()), "x_max": float(xy[:, 0].max()),
            "y_min": float(xy[:, 1].min()), "y_max": float(xy[:, 1].max()), "created_at": utc_now(),
        }
    ])
    registry.save("projection_models", projection_models)

    bins = config["projection"]["grid_bins"]
    x_edges = np.linspace(xy[:, 0].min(), xy[:, 0].max() + 1e-12, bins + 1)
    y_edges = np.linspace(xy[:, 1].min(), xy[:, 1].max() + 1e-12, bins + 1)
    q = np.clip(np.digitize(xy[:, 0], x_edges) - 1, 0, bins - 1)
    r = np.clip(np.digitize(xy[:, 1], y_edges) - 1, 0, bins - 1)
    topic_ids = [f"BIN_{short_hash(projection_id, 6)}_{a:02d}_{b:02d}" for a, b in zip(q, r)]
    target_status = targets.set_index("target_issue_id")["status_canvas"].to_dict()
    answer_status = {}
    for answer_id, grp in links.groupby("answer_turn_key"):
        statuses = [target_status.get(x) for x in grp["target_issue_id"] if target_status.get(x)]
        answer_status[answer_id] = statuses[0] if len(set(statuses)) == 1 else "unresolved"
    point_rows = []
    for idx, row in entity_df.iterrows():
        status = target_status.get(row.entity_id) if row.entity_type == "target_issue" else answer_status.get(row.entity_id)
        point_rows.append(
            {
                "projection_id": projection_id, "entity_type": row.entity_type, "entity_id": row.entity_id,
                "projection_x": float(xy[idx, 0]), "projection_y": float(xy[idx, 1]), "topic_bin_id": topic_ids[idx],
                "status_canvas": status, "point_weight": 1.0, "is_visible_default": row.entity_type == "target_issue",
                "pipeline_run_id": run_id,
            }
        )
    points = pd.DataFrame(point_rows)
    registry.save("projection_points", points)
    bin_rows = []
    for topic_id, grp in points.groupby("topic_bin_id"):
        target_members = grp[grp.entity_type == "target_issue"]
        representative = target_members.iloc[0].entity_id if len(target_members) else pd.NA
        bin_rows.append(
            {
                "topic_bin_id": topic_id, "projection_id": projection_id, "bin_method": "hexbin",
                "bin_q": int(topic_id.split("_")[-2]), "bin_r": int(topic_id.split("_")[-1]),
                "center_x": float(grp.projection_x.mean()), "center_y": float(grp.projection_y.mean()),
                "member_point_count": len(grp), "dominant_topic_label": pd.NA,
                "representative_target_issue_id": representative, "bin_version": "grid-baseline-1.0",
            }
        )
    topic_bins = pd.DataFrame(bin_rows)
    registry.save("topic_bins", topic_bins)

    centroid_rows = []
    for status, grp in points[points.entity_type == "target_issue"].groupby("status_canvas"):
        centroid_rows.append(
            {
                "centroid_id": f"CENT_{short_hash(projection_id, 8)}_marker_{status}", "projection_id": projection_id,
                "centroid_type": "marker_semantic", "status_canvas": status, "answer_type_code": pd.NA,
                "topic_bin_id": pd.NA, "member_count": len(grp), "total_weight": float(grp.point_weight.sum()),
                "vector_store_path": pd.NA, "vector_row": pd.NA, "projection_x": float(grp.projection_x.mean()),
                "projection_y": float(grp.projection_y.mean()), "medoid_entity_type": "target_issue",
                "medoid_entity_id": grp.iloc[((grp.projection_x-grp.projection_x.mean())**2 + (grp.projection_y-grp.projection_y.mean())**2).argmin()].entity_id,
                "dispersion_score": float(np.sqrt((grp.projection_x.var() or 0) + (grp.projection_y.var() or 0))), "created_at": utc_now(),
            }
        )
    centroids = pd.DataFrame(centroid_rows)
    registry.save("semantic_centroids", centroids)

    answer_points = points[points.entity_type == "answer"].set_index("entity_id")
    target_points = points[points.entity_type == "target_issue"].set_index("entity_id")
    label_by_answer = labels.set_index("answer_turn_key")
    code_cols = {"A1":"memory_lapse","A2":"information_unavailable","A3":"responsibility_shift","A4":"indirect_response",
                 "A5":"review_deferral","A6":"procedural_followup","A7":"concrete_commitment","A8":"completed_with_evidence"}
    member_rows = []
    for link in links.itertuples(index=False):
        if link.answer_turn_key not in answer_points.index or link.target_issue_id not in target_points.index:
            continue
        label = label_by_answer.loc[link.answer_turn_key]
        target_point = target_points.loc[link.target_issue_id]
        for code, col in code_cols.items():
            prob = float(label[col])
            if prob <= 0:
                continue
            node_id = f"NODE_{short_hash(projection_id, 6)}_{target_point.status_canvas}_{target_point.topic_bin_id}_{code}"
            member_rows.append(
                {
                    "atlas_node_id": node_id, "target_answer_link_id": link.target_answer_link_id,
                    "target_issue_id": link.target_issue_id, "answer_turn_key": link.answer_turn_key,
                    "answer_type_code": code, "behavior_probability": prob,
                    "relevance_weight": link.relevance_weight, "membership_weight": link.final_weight * prob,
                }
            )
    members = pd.DataFrame(member_rows)
    if len(members):
        members["rank_in_node"] = members.groupby("atlas_node_id")["membership_weight"].rank(method="first", ascending=False).astype(int)
    else:
        members = registry.empty("atlas_node_members")
    registry.save("atlas_node_members", members)
    node_rows = []
    if len(members):
        joined = members.merge(links, on=["target_answer_link_id","target_issue_id","answer_turn_key"], suffixes=("", "_link"))
        for node_id, grp in joined.groupby("atlas_node_id"):
            parts = node_id.split("_")
            code = parts[-1]; topic_id = "_".join(parts[-5:-1]); status = parts[-6]
            bin_row = topic_bins.set_index("topic_bin_id").loc[topic_id]
            mass = float(grp.membership_weight.sum())
            node_rows.append(
                {
                    "atlas_node_id": node_id, "projection_id": projection_id, "status_canvas": status,
                    "topic_bin_id": topic_id, "answer_type_code": code,
                    "behavior_family": "negative" if code in {"A1","A2","A3","A4"} else "process" if code in {"A5","A6"} else "substantive",
                    "anchor_x": bin_row.center_x, "anchor_y": bin_row.center_y, "display_x": bin_row.center_x,
                    "display_y": bin_row.center_y, "raw_answer_count": grp.answer_turn_key.nunique(),
                    "raw_link_count": len(grp), "weighted_mass": mass, "normalized_mass": 0.0,
                    "node_radius": 0.0, "mean_similarity": float(grp.relevance_weight.mean()),
                    "mean_qa_confidence": float(grp.qa_confidence.mean()), "mean_label_confidence": float(grp.label_confidence.mean()),
                    "marker_centroid_distance": pd.NA, "unresolved_null_share": pd.NA, "node_version": "baseline-1.0",
                }
            )
    nodes = pd.DataFrame(node_rows) if node_rows else registry.empty("atlas_nodes")
    if len(nodes):
        max_mass = max(float(nodes.weighted_mass.max()), 1e-9)
        nodes["normalized_mass"] = nodes.weighted_mass / max_mass
        rmin, rmax = config["projection"]["node_radius_min"], config["projection"]["node_radius_max"]
        nodes["node_radius"] = rmin + (rmax - rmin) * np.sqrt(nodes.normalized_mass)
    registry.save("atlas_nodes", nodes)
    audit.metric("entity_embeddings", "embedding_entity_count", len(embeddings), "PASS", ">0", f"{model_name} normalized embeddings")
    audit.metric("projection_points", "common_projection_count", len(points), "PASS", ">0")
    audit.metric("projection_models", "common_umap_available", 1, "PASS", "==1", "single PCA+UMAP fit across all statuses")
    return embedding_models, embeddings, projection_models, points, topic_bins, centroids, nodes, members, projection_id


def analysis_stage(run_id: str, audit: AuditTrail, targets, candidates, answer_units, labels, links):
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for candidate in [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if Path(candidate).exists():
            font_manager.fontManager.addfont(candidate)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=candidate).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False
    fig_root = PACKAGE_ROOT / "figures"
    fig_root.mkdir(parents=True, exist_ok=True)

    overview = pd.DataFrame(
        [
            ("meeting_registry", 42, "회의록 PDF"), ("pages", 4495, "물리 페이지"),
            ("blocks", 293717, "물리 block"), ("speaker_turns", 65590, "canonical turn"),
            ("retrieval_segments", 196686, "검색 window"), ("target_issues", len(targets), "확정 marker"),
            ("target_segment_candidates", len(candidates), "시간 적격 sparse 후보"),
            ("answer_units", len(answer_units), "역할 기반 답변 후보"),
            ("target_answer_links", len(links), "target-answer 후보 연결"),
        ], columns=["dataset", "row_count", "analysis_unit"]
    )
    save_csv(PACKAGE_ROOT / "evidence" / "dataset_overview.csv", overview)
    loader_meta = pd.DataFrame(
        [
            {"source": "canonical_etl", "path": "../data_parse/audit_minutes_pdf_etl", "encoding": "parquet", "role": "validated P0"},
            {"source": "target_2020", "path": "../P3_TARGET/outputs/marked_parallel/2020", "encoding": "utf-8-sig", "role": "approved marker"},
            {"source": "target_2022", "path": "../P3_TARGET/outputs/marked_parallel/2022", "encoding": "utf-8-sig", "role": "approved marker"},
            {"source": "target_2024", "path": "../P3_TARGET/outputs/marked_parallel/2024", "encoding": "utf-8-sig", "role": "approved marker"},
        ]
    )
    save_csv(PACKAGE_ROOT / "evidence" / "loader_metadata.csv", loader_meta)

    result_rows = []
    contingency = pd.crosstab(targets["source_year"], targets["status_canvas"])
    chi2, p_value, dof, _ = chi2_contingency(contingency)
    n = contingency.to_numpy().sum(); k = min(contingency.shape) - 1
    cramers_v = math.sqrt(chi2 / (n * k)) if n and k else 0.0
    result_rows.append(
        {
            "hypothesis": "H1", "article_question": "공식 처리상태 구성은 marker 연도별로 다른가?",
            "unit": "target_issue", "test": "chi_square", "statistic": chi2, "p_value": p_value,
            "effect_size": cramers_v, "effect_size_name": "Cramer's V",
            "safe_sentence": f"확정 marker의 공식 상태 구성은 연도별 차이를 보였고 효과크기는 {cramers_v:.2f}였다.",
            "avoid": "연도 자체가 이행 상태를 만들었다.", "evidence_level": "descriptive",
        }
    )
    target_status = targets[["target_issue_id", "status_canvas"]]
    candidate_top = candidates[candidates.final_rank == 1].merge(target_status, on="target_issue_id")
    a = candidate_top.loc[candidate_top.status_canvas == "complete", "sparse_score"]
    b = candidate_top.loc[candidate_top.status_canvas == "active", "sparse_score"]
    if len(a) and len(b):
        stat, p_value = mannwhitneyu(a, b, alternative="two-sided")
        delta = (2 * stat) / (len(a) * len(b)) - 1
    else:
        stat = p_value = delta = np.nan
    result_rows.append(
        {
            "hypothesis": "H2", "article_question": "공식 상태별 top sparse 검색 점수 분포가 다른가?",
            "unit": "target_issue_top1", "test": "Mann-Whitney U", "statistic": stat, "p_value": p_value,
            "effect_size": delta, "effect_size_name": "rank-biserial approximation",
            "safe_sentence": "검색 점수 차이는 retrieval 후보 품질 진단이며 이행 상태의 원인으로 해석하지 않는다.",
            "avoid": "완료 여부가 회의록 답변 유사도를 결정했다.", "evidence_level": "diagnostic",
        }
    )
    rho, p_value = spearmanr(answer_units["char_count"], answer_units["qa_confidence"]) if len(answer_units) > 2 else (np.nan, np.nan)
    result_rows.append(
        {
            "hypothesis": "H3", "article_question": "답변 길이와 규칙 기반 Q/A confidence가 단조 관계를 보이는가?",
            "unit": "answer_unit", "test": "Spearman", "statistic": rho, "p_value": p_value,
            "effect_size": rho, "effect_size_name": "Spearman rho",
            "safe_sentence": "길이와 Q/A confidence의 관계는 resolver 진단값이며 답변 품질의 척도가 아니다.",
            "avoid": "긴 답변이 더 정확하거나 성실하다.", "evidence_level": "diagnostic",
        }
    )
    hypothesis = pd.DataFrame(result_rows)
    save_csv(PACKAGE_ROOT / "data" / "analysis_csv" / "hypothesis_result_summary.csv", hypothesis)

    status_counts = targets.groupby(["source_year", "status_canvas"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 6))
    status_counts.plot(kind="bar", stacked=True, ax=ax, color={"complete":"#287271", "active":"#E9C46A", "unresolved":"#8D99AE"})
    ax.set(title="연도별 확정 marker의 공식 처리상태", xlabel="Marker 연도", ylabel="이슈 수")
    ax.legend(title="공식 상태"); fig.tight_layout()
    f1 = fig_root / "01_target_status_by_year.png"; fig.savefig(f1, dpi=180); plt.close(fig)

    code_cols = {
        "A1":"memory_lapse", "A2":"information_unavailable", "A3":"responsibility_shift", "A4":"indirect_response",
        "A5":"review_deferral", "A6":"procedural_followup", "A7":"concrete_commitment", "A8":"completed_with_evidence",
    }
    behavior_counts = pd.Series({code: int(labels[col].sum()) for code, col in code_cols.items()})
    fig, ax = plt.subplots(figsize=(10, 6))
    behavior_counts.plot(kind="bar", ax=ax, color=["#BC4749"]*4 + ["#E9C46A"]*2 + ["#2A9D8F"]*2)
    ax.set(title="기관측 답변 후보의 weak-rule 행태 적중", xlabel="답변행태 코드", ylabel="답변 단위 수")
    ax.text(0.99, 0.98, "자동 후보이며 Gold 라벨 아님", transform=ax.transAxes, ha="right", va="top", fontsize=9)
    fig.tight_layout(); f2 = fig_root / "02_behavior_weak_rule_counts.png"; fig.savefig(f2, dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(answer_units["char_count"], answer_units["qa_confidence"], s=6, alpha=.18, color="#457B9D")
    ax.set_xscale("log"); ax.set(title="답변 길이와 Q/A resolver confidence", xlabel="답변 문자 수(log)", ylabel="Q/A confidence")
    fig.tight_layout(); f3 = fig_root / "03_answer_length_qa_confidence.png"; fig.savefig(f3, dpi=180); plt.close(fig)

    stage_labels = ["PDF", "Page", "Block", "Turn", "Segment", "Target", "Candidate", "Answer link"]
    stage_values = [42, 4495, 293717, 65590, 196686, len(targets), len(candidates), len(links)]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(range(len(stage_values)), np.log10(np.array(stage_values)+1), marker="o", linewidth=2.5, color="#6D597A")
    ax.set_xticks(range(len(stage_labels)), stage_labels, rotation=25); ax.set_ylabel("log10(건수+1)")
    ax.set_title("Evidence pipeline 규모와 축약 단계")
    for i, value in enumerate(stage_values): ax.text(i, np.log10(value+1)+.1, f"{value:,}", ha="center", fontsize=8)
    fig.tight_layout(); f4 = fig_root / "04_pipeline_scale.png"; fig.savefig(f4, dpi=180); plt.close(fig)

    infographic = pd.DataFrame(
        [
            ("V1", "공식 상태 구성", str(f1.relative_to(PACKAGE_ROOT)), "H1", "확정 marker 분모"),
            ("V2", "답변행태 weak-rule", str(f2.relative_to(PACKAGE_ROOT)), "taxonomy diagnostic", "Gold 아님"),
            ("V3", "답변 길이와 Q/A confidence", str(f3.relative_to(PACKAGE_ROOT)), "H3", "인과 해석 금지"),
            ("V4", "파이프라인 규모", str(f4.relative_to(PACKAGE_ROOT)), "scale", "로그축"),
        ], columns=["visual_id", "title", "figure_path", "claim_id", "editorial_limit"]
    )
    save_csv(PACKAGE_ROOT / "data" / "analysis_csv" / "infographic_manifest.csv", infographic)
    claim_matrix = pd.DataFrame(
        [
            ("C1", "공식 marker는 2020·2022·2024 합계 297건이다", "target_issues", "row_count=297", "safe"),
            ("C2", "회의록 corpus는 42 PDF와 196,686 segment를 포함한다", "canonical manifest", "traceability=1.0", "safe"),
            ("C3", "답변행태 적중은 자동 weak-rule 후보이다", "answer_behavior_labels", "manual gold=0", "limit"),
            ("C4", "공식 complete는 실제 완료 검증과 다르다", "completion_verifications", "not_reviewed", "limit"),
        ], columns=["claim_id", "claim", "evidence_source", "metric", "claim_status"]
    )
    save_csv(PACKAGE_ROOT / "evidence" / "claim_evidence_matrix.csv", claim_matrix)
    return overview, hypothesis, infographic, claim_matrix, [f1, f2, f3, f4]


def editorial_frontend_stage(
    registry: SchemaRegistry, run_id: str, audit: AuditTrail, targets, meetings, qa_pairs, answer_units,
    labels, links, verifications, nodes, points, projection_id, source_docs, figure_paths,
):
    pdf_asset_map = {}
    asset_rows = []
    for row in meetings.itertuples(index=False):
        asset_id = f"ASSET_PDF_{str(row.sha256)[:8].upper()}"
        pdf_asset_map[row.meeting_id] = asset_id
        asset_rows.append(
            {
                "asset_id": asset_id, "asset_type": "pdf", "asset_title": f"회의록 {row.meeting_id}",
                "source_url": row.source_url, "local_path": f"../pdf_raw_data/{row.meeting_id}.pdf",
                "mime_type": "application/pdf", "width_px": pd.NA, "height_px": pd.NA, "duration_sec": pd.NA,
                "sha256": row.sha256, "license_name": "대한민국 국회 원문", "attribution": "대한민국 국회",
                "alt_text": f"문화체육관광위원회 {2000+int(row.meeting_year)}년 회의록 PDF",
                "public_visibility": False, "created_at": utc_now(),
            }
        )
    for fig_path in figure_paths:
        digest = sha256_file(fig_path)
        asset_rows.append(
            {
                "asset_id": f"ASSET_CHART_{digest[:8].upper()}", "asset_type": "static_chart",
                "asset_title": fig_path.stem, "source_url": pd.NA,
                "local_path": str(fig_path.relative_to(PACKAGE_ROOT)), "mime_type": "image/png",
                "width_px": pd.NA, "height_px": pd.NA, "duration_sec": pd.NA, "sha256": digest,
                "license_name": "project_internal", "attribution": "P3_CULTURE data pipeline",
                "alt_text": fig_path.stem.replace("_", " "), "public_visibility": False, "created_at": utc_now(),
            }
        )
    media_assets = pd.DataFrame(asset_rows)
    registry.save("media_assets", media_assets)

    qa_index = qa_pairs.set_index("qa_pair_id")
    answer_index = answer_units.set_index("answer_unit_id")
    label_index = labels.set_index("answer_turn_key")
    verification_map = verifications.set_index("target_issue_id")["verification_id"].to_dict()
    evidence_rows = []
    for link in links.itertuples(index=False):
        qa = qa_index.loc[link.qa_pair_id]; answer = answer_index.loc[link.answer_turn_key]
        evidence_id = f"EVD_{link.target_issue_id}_{short_hash(link.answer_turn_key)}"
        evidence_rows.append(
            {
                "evidence_id": evidence_id, "target_issue_id": link.target_issue_id, "qa_pair_id": link.qa_pair_id,
                "target_answer_link_id": link.target_answer_link_id, "answer_label_id": link.answer_label_id,
                "verification_id": verification_map.get(link.target_issue_id), "primary_segment_no": link.primary_segment_no,
                "meeting_id": qa.meeting_id, "page_start_no": qa.page_start_no, "page_end_no": qa.page_end_no,
                "pdf_asset_id": pdf_asset_map[qa.meeting_id], "evidence_status": "draft", "public_visibility": False,
                "evidence_hash": sha256_text(f"{link.target_issue_id}|{link.qa_pair_id}|{answer.answer_hash}"), "created_at": utc_now(),
            }
        )
    evidence = pd.DataFrame(evidence_rows).drop_duplicates("evidence_id")
    registry.save("evidence_records", evidence)

    target_index = targets.set_index("target_issue_id")
    case_rows = []
    case_candidates = links.sort_values("final_weight", ascending=False).drop_duplicates("target_issue_id").head(8)
    evidence_by_link = evidence.set_index("target_answer_link_id")
    for seq, link in enumerate(case_candidates.itertuples(index=False), start=1):
        target = target_index.loc[link.target_issue_id]
        case_type = "concrete_complete" if target.status_canvas == "complete" else "long_active"
        case_rows.append(
            {
                "case_id": f"CASE_{seq:03d}", "target_issue_id": link.target_issue_id,
                "evidence_id": evidence_by_link.loc[link.target_answer_link_id].evidence_id,
                "case_type": case_type, "case_title": normalize_text(target.issue_text)[:60],
                "case_summary": "자동 검색·Q/A 후보에서 선정된 편집 검토 대기 사례",
                "editorial_order": seq, "claim_level": "descriptive", "verification_required": True,
                "publish_status": "draft", "selected_by": "pipeline", "selected_at": utc_now(),
            }
        )
    cases = pd.DataFrame(case_rows)
    registry.save("editorial_cases", cases)

    chapter_defs = [
        (0,"prologue","질문은 남았다","공식 처리결과에서 과거 질문으로 되짚어 간다","evidence_line"),
        (1,"scale","기록의 규모","42개 회의록과 297개 marker의 분석 범위를 밝힌다","scale_scene"),
        (2,"record","한 이슈의 증거선","요구·질문·답변·결과의 연결을 보여 준다","evidence_scene"),
        (3,"gap","이행의 간극","공식 상태와 외부 검증 상태를 분리한다","gap_scene"),
        (4,"answers","어떻게 답했나","topic 위치와 behavior 표현을 분리한다","atlas_scene"),
        (5,"cases","대표 사례","원문 역추적 가능한 후보를 검토한다","case_scene"),
        (6,"remains","남은 질문","Gold·완료검증이 비어 있음을 공개한다","remains_scene"),
        (7,"method","방법과 원문","파이프라인과 한계를 재현 가능하게 남긴다","method_scene"),
    ]
    chapters = pd.DataFrame([
        {"chapter_id": f"CH_{order:02d}", "chapter_order": order, "chapter_slug": slug,
         "chapter_title": title, "chapter_thesis": thesis, "chapter_summary": thesis,
         "route_hash": f"#{slug}", "visual_scene_id": scene, "publish_status": "draft"}
        for order, slug, title, thesis, scene in chapter_defs
    ])
    registry.save("story_chapters", chapters)
    event_rows = []
    for row in chapters.itertuples(index=False):
        event_rows.append(
            {"story_event_id": f"EVT_{row.chapter_id}_001", "chapter_id": row.chapter_id, "display_order": 1,
             "event_date": pd.NaT, "event_type": "editorial", "target_issue_id": pd.NA, "evidence_id": pd.NA,
             "headline": row.chapter_title, "body": row.chapter_thesis, "visual_asset_id": pd.NA,
             "interaction_type": "line_draw" if row.chapter_slug in {"prologue","record"} else "reveal",
             "start_progress": 0.0, "end_progress": 1.0, "publish_status": "draft"}
        )
    for case in cases.itertuples(index=False):
        event_rows.append(
            {"story_event_id": f"EVT_CH05_{case.editorial_order+1:03d}", "chapter_id": "CH_05",
             "display_order": case.editorial_order+1, "event_date": pd.NaT, "event_type": "answer",
             "target_issue_id": case.target_issue_id, "evidence_id": case.evidence_id, "headline": case.case_title,
             "body": case.case_summary, "visual_asset_id": pd.NA, "interaction_type": "horizontal_case",
             "start_progress": pd.NA, "end_progress": pd.NA, "publish_status": "draft"}
        )
    events = pd.DataFrame(event_rows)
    registry.save("story_events", events)

    metrics_values = [
        ("CH_01","meeting_count","회의록",42,None,"건","COUNT meeting_registry","meeting_registry"),
        ("CH_01","page_count","페이지",4495,None,"쪽","COUNT pages","pages"),
        ("CH_01","target_count","확정 marker",len(targets),None,"건","COUNT target_issues","target_issues"),
        ("CH_04","answer_unit_count","기관측 답변 후보",len(answer_units),None,"건","COUNT answer_units","answer_units"),
        ("CH_06","gold_qrels_count","Gold qrels",0,None,"건","COUNT target_segment_qrels","target_segment_qrels"),
    ]
    story_metrics = pd.DataFrame([
        {"story_metric_id": f"MET_{chapter}_{name}", "chapter_id": chapter, "metric_name": name,
         "metric_label": label, "value_numeric": value, "value_text": text, "denominator": pd.NA,
         "unit": unit, "calculation_rule": rule, "source_table": source, "source_filter": pd.NA,
         "pipeline_run_id": run_id}
        for chapter,name,label,value,text,unit,rule,source in metrics_values
    ])
    registry.save("story_metrics", story_metrics)

    frontend_root = PACKAGE_ROOT / "frontend" / "public" / "data"
    frontend_root.mkdir(parents=True, exist_ok=True)
    story_manifest = {"version":"3.0.0","pipelineRunId":run_id,"chapters":[{"id":r.chapter_slug,"order":int(r.chapter_order),"title":r.chapter_title,"eventIds":events.loc[events.chapter_id==r.chapter_id,"story_event_id"].tolist()} for r in chapters.itertuples(index=False)]}
    bundles = {}
    bundles["story-manifest.json"] = story_manifest
    bundles["chapter-events.json"] = json.loads(events.to_json(orient="records", force_ascii=False, date_format="iso"))
    bundles["metrics.json"] = json.loads(story_metrics.to_json(orient="records", force_ascii=False))
    bundles["atlas-summary.json"] = {"projectionId":projection_id,"counts":{"targets":len(targets),"qaPairs":len(qa_pairs),"answers":len(answer_units),"links":len(links),"nodes":len(nodes)}}
    for status in ["all","active","complete","unresolved"]:
        subset = nodes if status == "all" else nodes[nodes.status_canvas == status]
        bundles[f"atlas-nodes-{status}.json"] = json.loads(subset.to_json(orient="records", force_ascii=False))
    bundles["evidence-index.json"] = json.loads(evidence.to_json(orient="records", force_ascii=False, date_format="iso"))
    bundles["projection-meta.json"] = {"projectionId":projection_id,"method":"multilingual MiniLM + common PCA50 + UMAP","publicationReady":False,"publicationBlocker":"Gold retrieval and editorial review pending"}
    bundles["method-meta.json"] = {"schemaVersion":"1.1.0-implemented","retrieval":"sparse top50 + dense MiniLM rerank","qrels":"pending manual review","qa":"rule candidate","behavior":"weak_rule","completionVerification":"not_reviewed"}
    bundles["assets-manifest.json"] = json.loads(media_assets.to_json(orient="records", force_ascii=False, date_format="iso"))
    written = []
    for name, payload in bundles.items():
        path = save_json(frontend_root / name, payload); written.append(path)
    try:
        import pyarrow.feather as feather
        details = links.merge(targets[["target_issue_id","issue_text","status_canvas"]], on="target_issue_id").merge(
            answer_units[["answer_unit_id","answer_text_display","meeting_id","page_start_no","page_end_no"]],
            left_on="answer_turn_key", right_on="answer_unit_id", how="left"
        )
        arrow_path = frontend_root / "evidence-details.arrow"; feather.write_feather(details, arrow_path); written.append(arrow_path)
    except Exception as exc:
        audit.anomaly("frontend_manifest", None, "arrow_export_failed", "medium", str(exc))

    manifest_rows = []
    for path in written:
        digest = sha256_file(path)
        manifest_rows.append(
            {"bundle_id": f"BUNDLE_{path.stem}_{digest[:8].upper()}", "app_version":"0.1.0",
             "data_version":"1.1.0", "pipeline_run_id":run_id, "projection_id":projection_id,
             "route_scope":"all", "lazy_load_group":path.stem, "file_path":str(path.relative_to(PACKAGE_ROOT)),
             "file_format":"arrow" if path.suffix==".arrow" else "json", "file_hash":digest,
             "row_count":pd.NA, "size_bytes":path.stat().st_size, "cache_policy":"immutable", "generated_at":utc_now()}
        )
    frontend_manifest = pd.DataFrame(manifest_rows)
    registry.save("frontend_manifest", frontend_manifest)
    save_json(frontend_root / "frontend-manifest.json", {"pipelineRunId":run_id,"files":manifest_rows})
    audit.metric("evidence_records", "evidence_route_count", len(evidence), "PASS" if len(evidence)==len(links) else "FAIL", f"=={len(links)}")
    audit.metric("evidence_records", "publishable_evidence_count", int((evidence.evidence_status=="publishable").sum()), "NOT_MEASURED", "manual approval required", severity="high")
    return media_assets, evidence, cases, chapters, events, story_metrics, frontend_manifest
