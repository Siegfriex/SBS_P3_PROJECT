# P3_CULTURE P3_0722 최종 파이프라인 실행 보고서

- run: `RUN_20260722T052913Z_D9E75E`
- status: **PIPELINE_CONDITIONAL_REVIEW_REQUIRED**
- canonical source: `1.0.1_20260721T084913Z`

## 실제 생성 규모

- meetings: 42
- pages: 4,495
- blocks: 293,717
- speaker_turns: 65,590
- retrieval_segments: 196,686
- target_issues: 297
- retrieval_candidates: 14,850
- qa_pairs: 25,832
- answer_units: 25,931
- answer_sentences: 38,622
- behavior_hits: 943
- behavior_spans: 923
- target_answer_links: 1,476
- projection_points: 1,509
- atlas_nodes: 45
- evidence_records: 1,476

## Gate

- P0_CANONICAL_ETL: **PASS**
- P1_TARGET_SCHEMA: **PASS**
- P2_TEMPORAL_ELIGIBILITY: **PASS**
- P3_SPARSE_RETRIEVAL: **PASS_BASELINE**
- P4_QRELS: **REVIEW_REQUIRED**
- P5_QA_PAIR: **CONDITIONAL_RULE_CANDIDATES**
- P6_ANSWER_TAXONOMY: **CONDITIONAL_WEAK_RULE**
- P7_DENSE_HYBRID: **PASS_CANDIDATE_POOL_RERANK**
- P8_PROJECTION_NODES: **PASS_COMMON_MULTILINGUAL_UMAP**
- P9_EDITORIAL: **DRAFT_REVIEW_REQUIRED**
- P10_FRONTEND_BUNDLE: **GENERATED_NOT_PUBLIC**

## 해석 제한

- 검색·Q/A·답변행태는 자동 후보 생성까지 완료했다. Gold 또는 승인 데이터로 간주하지 않는다.
- 공식 `complete`는 외부 검증 완료를 뜻하지 않는다.
- 2025 회의록은 2020·2022·2024 target 검색 corpus에 들어가지 않았다.
- 공개 가능한 evidence는 수동 qrels/Q&A/행태/완료 검증 뒤 승인해야 한다.

## 다음 필수 작업

1. `data/qrels/qrels_review_queue.csv` 400건을 0/1/2로 검수한다.
2. `outputs/answer_review_sample.csv`로 Q/A precision과 A1~A8 precision을 측정한다.
3. 대표 사례 완료 여부를 외부 공식 자료로 검증한다.
4. dense 검색을 전체 eligible corpus ANN 후보군으로 확장하고 qrels 기반 recall gain을 평가한다.
