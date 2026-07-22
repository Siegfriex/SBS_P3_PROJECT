# 국정감사 문화체육관광위원회 회의록 PDF ETL SSOT

- SSOT 버전: 1.0 (parser_version/pipeline_version=1.0.1)
- 실행 상태: EXECUTED (pipeline_run_id=1.0.1_20260721T084913Z)
- 기준 노트북: `09_audit_minutes_pdf_etl.ipynb`
- 기준 경로: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE`

## 1. 확정 규모
- registry=42, pages=4495, blocks=293717, turns=65590, segments=196686

## 2. 확정 계약
- block_no PK: `{meeting_id}_{page_no:04d}_{block_seq:04d}`
- turn_no PK: `{meeting_id}_T{turn_seq:05d}`
- segment_no PK: `{meeting_id}_{SEG_TYPE}_{anchor_turn_seq:05d}`
- EMPTY/PAGE_HEADER/PAGE_FOOTER는 turn raw_text/normalized_text/char_count에 기여하지 않는다(§06 검증, 0건).
- 이 코퍼스는 TOC/index 패턴이 없어 `index_map.parquet`은 스키마만 유지된 0행이다.

## 3. Quality Gate
- core_fail_count: 0
- hierarchy_metrics: {'inheritance_fail': 0, 'containment_fail': 0, 'adjacency_fail': 0, 'atomicity_fail': 0, 'n_blocks_mismatch': 0, 'char_count_mismatch': 0, 'page_range_mismatch': 0, 'multiple_speaker_headers': 0, 'speaker_turn_without_header': 0}
- segment traceability_rate: 1.0

## 4. 로드맵에서 제외된 항목
- SVO, Open-IE, skip-gram, NTN, event CNN 관련 설계·구현은 향후 production/실험 로드맵에서 완전히 제외됐다.

## 5. 다음 단계
- Phase 3: 긴 turn/공백 소실 대응은 canonical raw/normalized_text를 건드리지 않고 별도 `retrieval_search_chunks.parquet`(검색 전용)로 분리한다.
- Phase 4: `20_target_segment_sparse_retrieval.ipynb`에서 sparse retrieval production을 시작한다.