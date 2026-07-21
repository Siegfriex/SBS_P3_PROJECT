# 02_pdf_crawler Data Dictionary

Stage: `PDF_CRAWL_AND_DOWNLOAD` — PDF 원본 수집/검증 단계의 산출물만 다룬다. 텍스트 추출/OCR/블록/발언자/TF-IDF/embedding 컬럼은 없다.

## control_registry.parquet

Grain: Excel Registry 1행 = 회의 1건.

| 컬럼 | dtype | 설명 |
|---|---|---|
| meeting_id | string (PK) | 원본 회의ID, 정수 변환 금지 |
| meeting_number | string nullable | 원본 `대수`에서 숫자부만 추출 (예: `제22대` → `22`) |
| meeting_count | string nullable | 원본 `회기`에서 숫자부만 추출 (예: `제429회` → `429`) |
| meeting_year | string nullable | 회의일자 연도 마지막 2자리 (YY) |
| meeting_date | string nullable | 회의일자의 MMDD |
| meeting_type | string nullable | 원본 `회의종류` |
| committee_code | string nullable | 원본 `위원회코드` |
| committee_name | string nullable | 원본 `위원회명` |
| source_url | string | Excel의 다운로드 URL. HTTP 요청 대상은 이 컬럼만 사용 |
| source_row_no | Int64 | 원본 Excel 행 번호(헤더 제외, 1-based) |
| source_* | string nullable | 위에 매핑되지 않은 원본 컬럼 보존 (예: `source_차수`) |
| download_status | string | `pending`, `downloaded`, `failed`, `invalid_url`, `invalid_content` |
| http_status | Int64 nullable | 최종 HTTP status code |
| final_url | string nullable | redirect 이후 최종 URL |
| local_pdf_path | string nullable | repo-relative 저장 경로 (`pdf_raw_data/{meeting_id}.pdf`) |
| file_size | Int64 nullable | 저장된 PDF 바이트 크기 |
| sha256 | string nullable | PDF 바이너리 SHA-256 |
| page_count | Int64 nullable | `fitz.open().page_count` |
| reused_existing_file | boolean | 기존 유효 PDF를 재사용했는지 여부 |
| error_message | string nullable | 실패/보류 사유 코드 |
| critical_gate_failed | boolean | Registry Critical Gate 실패 행 여부(감사용) |
| parse_status | string | 이 단계에서는 항상 `pending` 고정 |
| parser_name | string nullable | 이 단계에서는 항상 null (파싱 미실행) |
| parser_version | string nullable | 이 단계에서는 항상 null |
| extracted_char_count | Int64 nullable | 이 단계에서는 항상 null |
| ocr_page_count | Int64 nullable | 이 단계에서는 항상 null |

## download_log.parquet

Grain: HTTP 시도(attempt) 1회.

| 컬럼 | dtype | 설명 |
|---|---|---|
| meeting_id | string FK | control_registry.meeting_id |
| attempt_no | Int64 | 1부터 시작하는 시도 순번 |
| timestamp | string (ISO8601 UTC) | 요청 시각 |
| url_requested | string | 실제 요청 URL |
| http_status | Int64 nullable | 응답 status (네트워크 예외 시 null) |
| final_url | string nullable | redirect 최종 URL |
| bytes_received | Int64 | 스트리밍으로 받은 바이트 수 |
| action | string | `validate`/`retry`/`retry_after`/`retry_backoff`/`invalid_url`/`failed` |
| error_message | string nullable | 오류/사유 코드 |
| elapsed_seconds | Float64 | 요청 소요 시간 |
| retry_after_seconds | Float64 nullable | 429 `Retry-After` 값 |

## crawl_quality.parquet

Grain: 품질검사 항목 1개. 컬럼: `check`(str), `status`(INFO/PASS/FAIL/WARN), `detail`(str).

## 생성 규칙 노트

- 모든 결측은 빈 문자열이 아니라 null(`pd.NA`)로 저장한다.
- `meeting_id`/`meeting_number`/`meeting_count`/`meeting_year`/`meeting_date`는 숫자 캐스팅 금지(SSOT.md §4.1).
- 이 문서는 `02_pdf_crawler.ipynb` 실행 시 자동 생성되며 수동 편집분은 다음 실행에서 덮어써진다.
