# Marked Mapping Quality

## 1. Input
- Canonical PDF: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/target_mark_pdf/2020년도_국정감사결과_형광펜_통합본.pdf`
- SHA-256: `39b22045f62625a1dea321a714e041b119632f640f208da55c2cbb5ea8088d86`
- Pages: 165
- Requested year: 2024
- Detected title-page year: 2020
- Sequential PDF audits: 2

## 2. Annotation and row mapping
- Highlight annotations: 283
- TOC annotation mapping: 115 mapped / 0 unresolved
- Body annotation mapping: 168 mapped / 0 unresolved
- Selected issues: 110
- Issue mapping: 110 mapped / 0 unresolved
- Marker sources: {"toc_and_body": 88, "toc_only": 20, "body_only": 2}
- Native numbering audit: {"missing_issue_nos": [281], "duplicate_issue_nos": [280]}

## 3. Parsing quality
- Native rows: 110
- OCR attempted: 5
- OCR recovered: 0
- OCR failures: 0
- Null counts: {"issue_text_empty": 0, "action_text_null_literal": 4, "future_plan_text_null_literal": 43, "status_null_literal": 1}

## 4. Status
- complete: 55
- active: 54
- uncomplete: 0
- null: 1

## 5. Checks
- canonical_columns_exact: PASS
- review_columns_exact: PASS
- issue_id_unique: PASS
- issue_no_unique: PASS
- all_selected_issues_mapped: PASS
- all_toc_annotations_mapped: PASS
- all_body_annotations_mapped: PASS
- all_issue_text_present: PASS
- status_allowed: PASS
- parse_source_allowed: PASS
- source_page_in_range: PASS
- parquet_exists: PASS
- csv_exists: PASS
- parquet_rows_match: PASS
- csv_rows_match: PASS
- parquet_columns_exact: PASS
- csv_columns_exact: PASS
- parquet_issue_id_unique: PASS
- csv_literal_null_contract: PASS

## 6. Warnings
- inputs/pdf was empty; used target_mark_pdf controlled fallback
- Multiple supplied PDFs audited sequentially; marked integrated superset selected
- Requested report year 2024, but title page detected 2020
- No unique meeting_id matched
- Native body numbering defect: {'missing_issue_nos': [281], 'duplicate_issue_nos': [280]}

## 7. Final status
- **PARTIAL**
