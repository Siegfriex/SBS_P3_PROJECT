# SEGMENT_VALIDATION_AUDIT

- run: 2026-07-21T08:27:23.406661+00:00 ~ 2026-07-21T08:28:55.207866+00:00
- git: `P3_MARKED_2020_2024` @ `b3ff9a01edaf8598eeecb5a5ecfd16bd4dc59bc8`
- source_mode: **rebuild_from_pdf**
- gate_decision: **READY_FOR_CANONICAL_SEGMENT_EXPORT**  (readiness_score=0.913, core_fail=0, warnings=0)

## 규모
- registry_rows=42  pdf_files=42
- block_rows=293717  turn_rows=65590  segment_rows=196686

## 핵심 발견
- PK/FK/page coverage: block_pk_dup=0, turn_pk_dup=0, block_fk_orphan=0, page_coverage_ratio=1.0
- turn 위계 전수 감사: containment_fail=0, n_blocks_mismatch=0 (원인: EMPTY-type block이 n_blocks/block_end_no 갱신에서 누락되는 버그 -- Phase 1에서 수정 완료, 0건)
- segment: expected=196686 observed=196686 (일치), assembly_fail=0, traceability_rate=1.000000
- target 호환성: 2020=110행, 2024=71행, 둘 다 corpus 연도 존재
- retrieval smoke test: 10개 target × top 10 (scikit-learn 미설치로 수동 numpy TF-IDF 대체 구현 사용)

## audit_metrics 요약
```text
                         metric_name  metric_value status
              registry_pdf_integrity       0.00000   PASS
                 block_pk_duplicates       0.00000   PASS
                  turn_pk_duplicates       0.00000   PASS
                    block_fk_orphans       0.00000   PASS
                 page_coverage_ratio       1.00000   PASS
                 block_unknown_ratio       0.00000   PASS
               turn_inheritance_fail       0.00000   PASS
               turn_containment_fail       0.00000   PASS
                 turn_adjacency_fail       0.00000   PASS
                 turn_atomicity_fail       0.00000   PASS
              turn_n_blocks_mismatch       0.00000   PASS
            multiple_speaker_headers       0.00000   PASS
         speaker_turn_without_header       0.00000   PASS
                   orphan_turn_ratio       0.00064   PASS
            empty_speaker_turn_ratio       0.00000   PASS
        segment_expected_vs_observed       0.00000   PASS
                  segment_fk_orphans       0.00000   PASS
               segment_assembly_fail       0.00000   PASS
           segment_traceability_rate       1.00000   PASS
           target_year_compatibility       1.00000   PASS
      retrieval_smoke_targets_tested      10.00000   PASS
canonical_pages_index_export_present       0.00000   INFO
                   sklearn_available       0.00000   INFO
```

## 다음 필요 조치
- scikit-learn not installed -- smoke test used a manual numpy TF-IDF substitute, not sklearn's TfidfVectorizer

**최종 판정: READY_FOR_CANONICAL_SEGMENT_EXPORT**