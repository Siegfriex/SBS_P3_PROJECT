# CRAWL_REPORT — PDF_CRAWL_AND_DOWNLOAD

- 실행 시각(UTC): 2026-07-21T05:25:45.779447+00:00 ~ 2026-07-21T05:27:18.323946+00:00
- git branch / commit: `P3_DATA_RAW` / `236ad55872afe97df3c9308f9fbd3535f5d287be`
- 계약 반영 상태: `CRAWLER_EXECUTION_CONTRACT_ACTIVE`
- 실행 결과 상태: **`COMPLETE`**
- Crawl Gate: **`CRAWL_GATE_PASS`**

## 입력
- Excel: `data_origin/국정감사회의록_문화체육 2020~.xlsx` (sheet=`Sheet1`, sha256=`a4e7bb5ae119556e...`)
- 총 행 수: 42

## Registry Critical Gate
- 상태: **PASSED**
| check | status | detail |
|---|---|---|
| MISSING_MEETING_ID | 0 |  |
| DUPLICATE_MEETING_ID_PATH_COLLISION | 0 |  |
| MISSING_SOURCE_URL | 0 |  |
| NON_HTTP_SCHEME_URL | 0 |  |
| UNSAFE_MEETING_ID_FILENAME | 0 |  |
| EXPECTED_PDF_PATH_COLLISION | 0 |  |
| DUPLICATE_SOURCE_URL_ACROSS_MEETING_IDS | 0 | row-level pending, not a hard gate failure |

## 기존 PDF Circuit Breaker
- triggered: False

## 다운로드 결과
- total: 42
- downloaded: 42
- reused_existing: 0
- failed: 0
- invalid_url: 0
- invalid_content: 0
- pending: 0

## 원천 도메인 (source_url 사후 집계)
- record.assembly.go.kr

## 수집 결과 품질검사
| check | status | detail |
|---|---|---|
| TOTAL_ROWS | INFO | 42 |
| DOWNLOADED_COUNT | INFO | 42 |
| STATUS_PENDING_COUNT | INFO | 0 |
| STATUS_FAILED_COUNT | INFO | 0 |
| STATUS_INVALID_URL_COUNT | INFO | 0 |
| STATUS_INVALID_CONTENT_COUNT | INFO | 0 |
| DOWNLOADED_MISSING_LOCAL_PATH | PASS | 0 |
| DOWNLOADED_BAD_PAGE_COUNT | PASS | 0 |
| DOWNLOADED_MISSING_SHA256 | PASS | 0 |
| DUPLICATE_SHA256_ACROSS_MEETINGS | PASS | 0 |
| LOCAL_PDF_PATH_EXISTS_ON_DISK | PASS | 0 |
| UNRESOLVED_PENDING_WITH_ERROR | INFO | 0 |
| PARSE_STATUS_UNTOUCHED | PASS | 0 |

## 의존성
- python_version: 3.12.3
- platform: Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.39
- pandas: 3.0.3
- pyarrow: 25.0.0
- requests: 2.31.0
- pymupdf: 1.28.0
- nbformat: 5.10.4
- git_branch: P3_DATA_RAW
- git_commit: 236ad55872afe97df3c9308f9fbd3535f5d287be

## 이 단계 산출물
- control_registry: `data_parse/pdf_crawler/control_registry.parquet`
- download_log: `data_parse/pdf_crawler/download_log.parquet`
- crawl_quality: `data_parse/pdf_crawler/crawl_quality.parquet`
- log_file: `data_parse/pdf_crawler/logs/pdf_crawler.log`
- data_dict: `data_dict/02_pdf_crawler_data_dictionary.md`

## 이 단계가 의미하지 않는 것
PDF 본문 텍스트 추출 성공, OCR 성공, 페이지/블록 분할, 발언자 판별, speaker turn 생성, TF-IDF 검색 — 어느 것도 이 단계의 성공 기준에 포함되지 않는다.