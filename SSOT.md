# 국정감사 회의록 PDF ETL·검색 전처리 SSOT v1.0

- 문서 상태: 확정안(LOCKED)
- 적용 범위: 문화체육관광위원회 국정감사 회의록 Excel registry 및 연결 PDF
- 기준 노트북: `09_audit_minutes_pdf_etl.ipynb`
- 파서 버전: `1.0.0`
- 기본 산출 단위: meeting → index → page → block → speaker turn → retrieval segment

## 0. 목적

Excel registry의 각 행에 포함된 PDF URL을 자동 수집하고, 원본 PDF를 보존한 뒤, 페이지·블록·발언자 turn·TF-IDF 검색 segment로 구조화한다. 모든 결과는 원문 위치로 역추적 가능해야 하며, 이후 병렬 브랜치의 topic seed와 TF-IDF/character n-gram/embedding으로 매핑할 수 있어야 한다.

이 노트북의 직접 범위는 `PDF 수집 → 텍스트 구조화 → TF-IDF-ready segment export`까지다. 임계값 학습, topic matching, OpenAI embedding, LLM labeling은 후속 분석 단계이며 본 산출물을 입력으로 사용한다.

## 1. 잠금된 설계 원칙

1. Excel은 입력 파일이 아니라 Control Table로 사용한다.
2. 다운로드와 파싱은 분리한다. URL에서 메모리 파싱만 하고 원본 PDF를 버리는 방식은 금지한다.
3. PDF는 일반 TXT가 아니라 좌표를 보존한 block 단위로 추출한다.
4. 정규식은 경계를 탐지하고, 발언 결합은 State Machine이 수행한다.
5. 물리 블록, 의미 발언, 검색 segment를 서로 다른 DataFrame으로 관리한다.
6. 모든 텍스트는 raw와 normalized를 함께 보존한다.
7. OCR은 페이지별 품질 검사 후 조건부로 실행한다.
8. 원본과 저점수 텍스트는 삭제하지 않는다. 후속 후보층에서만 제외한다.
9. 모든 ID는 문자열이며 원본으로 역추적 가능해야 한다.
10. 다른 IPYNB의 셀·함수·상태를 불러오지 않는다. 모든 설정·함수·실행·export는 단일 노트북 안에서 정의한다.

## 2. 노트북 파일명 및 번호 규칙

본 작업은 데이터 수집·정제·구조화가 중심이므로 0~9 범주를 사용한다.

- 확정 파일명: `09_audit_minutes_pdf_etl.ipynb`
- `10_data_collecting.ipynb`는 10~19 통계분석 규칙과 충돌하므로 사용하지 않는다.

프로젝트 번호 규칙:

- `00~09`: 환경설정·데이터 수집·데이터 핸들링
- `10~19`: 통계분석
- `20~29`: 머신러닝
- `30~39`: 딥러닝
- `40~89`: 시각화·응용 분석
- `90~99`: 임시 테스트

## 3. 전체 파이프라인

```text
Excel registry
→ Control Table 정규화
→ PDF download plan
→ HTTP 요청 및 PDF 검증
→ raw PDF 저장
→ SHA-256·페이지 수·수집 로그 기록
→ 페이지별 native text 품질 검사
→ 조건부 OCR
→ PyMuPDF block 추출(sort=True)
→ 반복 header/footer 및 목차 탐지
→ block type 분류
→ State Machine speaker turn 생성
→ 3종 retrieval segment 생성
→ Quality Gate
→ Parquet·SQLite·SSOT export
```

## 4. Control Table 계약: `registry_df`

### 4.1 필수 식별 컬럼

| 컬럼 | dtype | 규칙 | 예시 |
|---|---|---|---|
| `meeting_id` | string, PK | 원본 그대로 보존. 정수 변환 금지 | `N053487`, `024858` |
| `meeting_number` | string/category | `제22대` → 숫자부만 | `22` |
| `meeting_count` | string/category | `제429회` → 숫자부만 | `429` |
| `meeting_year` | string/category | 회의일자의 연도 마지막 2자리 | `25` |
| `meeting_date` | string/category | 회의일자의 MMDD | `1029` |

결측은 빈 문자열이 아니라 null(`pd.NA`)로 저장한다. `meeting_id`, `meeting_number`, `meeting_count`, `meeting_year`, `meeting_date`는 숫자로 캐스팅하지 않는다.

### 4.2 원본·기관 메타데이터

| 컬럼 | dtype | 설명 |
|---|---|---|
| `meeting_type` | string/category | 원본 회의종류 |
| `committee_code` | string/category | 원본 위원회코드 |
| `committee_name` | string/category | 원본 위원회명 |
| `source_url` | string | Excel의 다운로드 URL |
| `source_row_no` | Int64 | 원본 Excel 행 번호 |

### 4.3 다운로드 상태 컬럼

| 컬럼 | dtype | 설명 |
|---|---|---|
| `download_status` | category | `pending`, `downloaded`, `failed`, `invalid_url`, `invalid_content` |
| `http_status` | Int64 | 최종 HTTP status |
| `final_url` | string nullable | redirect 이후 최종 URL |
| `local_pdf_path` | string nullable | 저장 PDF 경로 |
| `file_size` | Int64 nullable | bytes |
| `sha256` | string nullable | PDF binary hash |
| `page_count` | Int64 nullable | PDF 페이지 수 |

### 4.4 파싱 상태 컬럼

| 컬럼 | dtype | 설명 |
|---|---|---|
| `parse_status` | category | `pending`, `parsed`, `parsed_with_ocr`, `partial`, `failed` |
| `parser_name` | category | 기본 `PyMuPDF` |
| `parser_version` | string | 파이프라인 파서 버전 |
| `extracted_char_count` | Int64 nullable | 선택된 전체 본문 문자 수 |
| `ocr_page_count` | Int64 | OCR 사용 페이지 수 |
| `error_message` | string nullable | 최종 오류 요약 |

## 5. ID 및 관계 키 규칙

| 엔터티 | 키 형식 | 예시 |
|---|---|---|
| meeting | 원본 `meeting_id` | `N053487` |
| index | `{meeting_id}_I{index_order:03d}` | `N053487_I004` |
| page | `{meeting_id}_{pdf_page_seq:04d}` | `N053487_0043` |
| block | `{page_no}_{block_seq:04d}` | `N053487_0043_0007` |
| turn | `{meeting_id}_T{turn_seq:05d}` | `N053487_T00128` |
| segment | `{meeting_id}_{segment_type}_{anchor_turn_seq:05d}` | `N053487_SEG_TURN_00128` |

- `page_no`는 PDF 내부의 물리 페이지 식별자다. 인쇄된 페이지 번호는 `printed_page_no`에 별도 저장한다.
- `index_no`는 목차가 탐지된 경우에만 생성하며, 없는 PDF·블록은 null이다.
- `block_no`가 index를 인코딩하지는 않는다. `block_df.index_no` 외래키로 대응한다.

## 6. 계층별 DataFrame 계약

### 6.1 `index_df`: PDF 목차·항목 맵

Grain: PDF 목차 항목 1개.

필수 컬럼:

- `index_no` PK
- `meeting_id` FK
- `index_order` Int64
- `index_label_raw` string nullable
- `index_title_raw` string
- `index_title_normalized` string
- `toc_page_no` string nullable
- `body_page_start_no` string nullable
- `body_page_end_no` string nullable
- `mapping_method` category: `explicit_page`, `heading_match`, `range_inference`, `unmapped`
- `mapping_confidence` Float64

목차가 없으면 `index_df`는 0행으로 저장하되 스키마는 유지한다.

### 6.2 `page_df`: 페이지 단위

Grain: PDF 물리 페이지 1개.

필수 컬럼:

- `page_no` PK
- `meeting_id` FK
- `pdf_page_seq` Int64, 1-based
- `printed_page_no` string nullable
- `index_no` FK nullable
- `native_raw_text` string
- `ocr_raw_text` string nullable
- `raw_text` string: 최종 선택 원문
- `normalized_text` string
- `native_char_count` Int64
- `selected_char_count` Int64
- `hangul_ratio` Float64
- `replacement_char_ratio` Float64
- `image_area_ratio` Float64
- `text_layer_present` boolean
- `ocr_required` boolean
- `ocr_used` boolean
- `extraction_method` category: `native`, `ocr`, `native_plus_ocr`
- `quality_score` Float64
- `error_message` string nullable

### 6.3 `block_df`: 물리 텍스트 블록

Grain: `page × block`.

필수 컬럼:

- `block_no` PK
- `page_no` FK
- `meeting_id` FK
- `index_no` FK nullable
- `block_seq` Int64
- `x0`, `y0`, `x1`, `y1` Float64
- `source_block_kind` category: `TEXT`, `IMAGE`
- `block_text` string: parser/OCR가 반환한 원문, 수정 금지
- `normalized_text` string
- `block_type` category
- `classification_rule` string nullable
- `classification_confidence` Float64
- `turn_no` FK nullable
- `is_orphan` boolean

### 6.4 `turn_df`: 의미 발언 단위

Grain: 한 발언자의 연속 발언 또는 독립 절차 문장 1개.

필수 컬럼:

- `turn_no` PK
- `meeting_id` FK
- `index_no` FK nullable
- `turn_seq` Int64
- `turn_type` category: `speaker`, `procedural`, `orphan`
- `speaker_raw` string nullable
- `speaker_name` string nullable
- `speaker_role` string/category nullable
- `speaker_org` string/category nullable
- `speaker_parse_confidence` Float64
- `agenda_text` string nullable
- `time_marker` string nullable
- `page_start_no`, `page_end_no` FK
- `block_start_no`, `block_end_no` FK
- `raw_text` string
- `normalized_text` string
- `char_count` Int64
- `sentence_count` Int64
- `is_orphan` boolean
- `parse_confidence` Float64

### 6.5 `segment_df`: TF-IDF 검색 단위

Grain: anchor turn 기준 검색 window 1개.

필수 컬럼:

- `segment_no` PK
- `meeting_id` FK
- `index_no` FK nullable
- `segment_type` category: `SEG_TURN`, `SEG_PREV_CURR`, `SEG_CURR_NEXT`
- `anchor_turn_no` FK
- `turn_start_no`, `turn_end_no` FK
- `prev_turn_no` FK nullable
- `next_turn_no` FK nullable
- `page_start_no`, `page_end_no` FK
- `speaker_names` string nullable
- `speaker_roles` string nullable
- `raw_text` string
- `normalized_text` string
- `char_count` Int64
- `sentence_count` Int64
- `segment_hash` string
- `tfidf_ready` boolean

### 6.6 `quality_df`: 품질 감사

Grain: `run × meeting × metric`.

필수 컬럼:

- `pipeline_run_id`
- `meeting_id`
- `metric_name`
- `metric_value`
- `threshold`
- `status`: `PASS`, `WARN`, `FAIL`
- `detail`

## 7. PyMuPDF 추출 계약

기본 추출기는 PyMuPDF다.

```python
page.get_text("blocks", sort=True)
```

필수 규칙:

1. 페이지 순서와 block 좌표를 보존한다.
2. `sort=True`의 읽기 순서를 기본값으로 사용한다.
3. raw block tuple은 `block_df` 레코드로 변환한다.
4. 이미지 block 여부는 `source_block_kind`에 기록한다.
5. parser가 반환한 `block_text`는 수정하지 않는다.
6. header/footer 제거와 whitespace 교정은 `normalized_text`에서만 수행한다.

## 8. 목차 및 `index_no` 매핑

1. PDF 초기부에서 `목차`, `차례`, dotted leader, 행 끝 페이지 번호 패턴을 탐지한다.
2. 목차 항목별 synthetic `index_no`를 생성한다.
3. 명시된 페이지 번호가 있으면 `explicit_page`로 매핑한다.
4. 본문 heading과 목차 제목의 정규화 문자열 유사도가 높으면 `heading_match`로 보완한다.
5. 다음 항목 시작 전까지의 page range를 해당 `index_no`로 전파한다.
6. 목차 또는 본문 heading이 불명확하면 null로 두며 강제 배정하지 않는다.

## 9. `block_type` 고정 범주와 판정 우선순위

### 9.1 확정 범주

1. `EMPTY`
2. `PAGE_HEADER`
3. `PAGE_FOOTER`
4. `TIME_MARKER`
5. `AGENDA_HEADER`
6. `INDEX_ENTRY`
7. `SPEAKER_HEADER`
8. `PROCEDURAL_TEXT`
9. `BODY_TEXT`
10. `UNKNOWN`

`INDEX_ENTRY`는 `index_no` 생성을 위해 추가한다. `UNKNOWN`은 규칙 실패를 숨기지 않고 품질 감사하기 위해 추가한다.

### 9.2 판정 우선순위

```text
EMPTY
→ PAGE_HEADER / PAGE_FOOTER
→ TIME_MARKER
→ AGENDA_HEADER
→ INDEX_ENTRY
→ SPEAKER_HEADER
→ PROCEDURAL_TEXT
→ BODY_TEXT
→ UNKNOWN
```

### 9.3 핵심 판정 방식

- `PAGE_HEADER`, `PAGE_FOOTER`: 정규식 단독이 아니라 y 좌표와 페이지 반복 빈도를 결합한다.
- `SPEAKER_HEADER`: `○`, `◯` marker, 역할어, 인명·기관명 패턴을 다중 정규식으로 탐지한다.
- `TIME_MARKER`: 시각 및 감사개시·중지·계속·종료 표현을 탐지한다.
- `AGENDA_HEADER`: 의사일정·감사대상·상정·보고사항 등 표준 제목 패턴을 탐지한다.
- `PROCEDURAL_TEXT`: 감사개시, 감사중지, 감사계속, 감사종료, 산회, 자료제출 요구 등의 절차 문장을 탐지한다.
- `BODY_TEXT`: 비어 있지 않고 앞선 범주가 아니며 active turn에 결합 가능한 텍스트다.
- `UNKNOWN`: 비어 있지 않으나 어떠한 구조 규칙으로도 배치할 수 없는 텍스트다.

정규식은 `PATTERN_REGISTRY` 딕셔너리 하나에서 버전 관리한다. 정규식은 2020·2023·2025년 표본 PDF로 파일럿 검증 후 고정한다.

## 10. State Machine 확정 규칙

상태:

- `NO_ACTIVE_TURN`
- `ACTIVE_SPEAKER_TURN`
- `ACTIVE_PROCEDURAL_TURN`

규칙:

1. `SPEAKER_HEADER`가 나오면 기존 turn을 flush하고 새 speaker turn을 연다.
2. header에 본문이 붙어 있으면 inline body를 새 turn에 포함한다.
3. 다음 `SPEAKER_HEADER` 전까지의 `BODY_TEXT`를 active turn에 누적한다.
4. 페이지가 바뀌어도 새 speaker header가 없으면 기존 turn을 유지한다.
5. `AGENDA_HEADER`가 나오면 기존 turn을 flush하고 이후 turn에 `agenda_text`를 전파한다.
6. `TIME_MARKER`는 독립 텍스트로 버리지 않고 다음 turn의 `time_marker`로 저장한다.
7. `PROCEDURAL_TEXT`는 기존 turn을 flush한 뒤 별도 procedural turn으로 저장한다.
8. `PAGE_HEADER`, `PAGE_FOOTER`, `EMPTY`는 turn 원문에 포함하지 않는다.
9. `UNKNOWN`이 active turn 안에 있고 연속성이 높으면 `low_confidence`로 append한다.
10. active turn이 없는 `BODY_TEXT` 또는 `UNKNOWN`은 orphan turn으로 저장한다.
11. 마지막 block 처리 후 active turn을 반드시 flush한다.

## 11. 텍스트 정규화 계약

### 11.1 raw 보존

- `block_text`, `raw_text`, `native_raw_text`, `ocr_raw_text`는 provenance 데이터다.
- raw 컬럼은 후처리 함수가 덮어쓰지 않는다.

### 11.2 normalized 처리 허용 범위

- Unicode 정규화
- 연속 공백 정규화
- 줄바꿈 정규화
- 반복 page header/footer 제거
- 단독 페이지 번호 제거
- PDF 줄바꿈으로 분리된 발언자명·어절의 제한적 결합
- parser로 발생한 인접 완전중복 문장 제거

### 11.3 제거 금지

- 인명
- 기관명
- 숫자
- 날짜
- 부정어
- 물음표·느낌표 등 질의 표지
- `검토하겠다`
- `모르겠다`
- `기억나지 않는다`
- `자료를 제출하겠다`
- 같은 발언자가 의미상 반복한 실제 발화

형태소 기반 불용어 제거와 stemming은 ETL 단계에서 수행하지 않는다.

## 12. OCR 페이지 판정 레이어

모든 페이지는 native parser 실행 후 OCR 필요 여부를 판정한다.

다음 중 하나라도 참이면 OCR 후보로 지정한다.

- `selected native char_count < 30`
- native text가 공백 또는 null
- `text_layer_present == False`
- 페이지가 이미지 객체 중심이고 `image_area_ratio >= 0.85`
- `replacement_char_ratio >= 0.02`
- 한국어 문서로 기대되는데 문자 품질 점수가 임계값 미만

OCR 실행 규칙:

1. 페이지를 300 DPI 이상으로 렌더링한다.
2. 한국어+영어 OCR을 실행한다.
3. native와 OCR 텍스트 품질을 각각 계산한다.
4. 품질이 높은 결과를 `raw_text`로 선택한다.
5. native와 OCR을 단순 연결하지 않는다.
6. 두 결과를 병합할 경우 좌표 중복 제거가 확인된 경우에만 `native_plus_ocr`를 사용한다.
7. OCR 실패 후에도 빈 페이지를 조용히 통과시키지 않고 `quality_df`에 FAIL로 기록한다.

권장 엔진 우선순위:

- 1순위: PaddleOCR 한국어 모델
- 2순위: Tesseract `kor+eng`

## 13. 3단계 segmentation

### Level 1: Physical Segment

- 단위: `page × block`
- 저장: `block_df`
- 목적: parser 오류·좌표·header/footer 검산

### Level 2: Semantic Segment

- 단위: 한 발언자의 연속 발언
- 저장: `turn_df`
- 목적: 질문자·답변자·절차 발언 분리

### Level 3: Retrieval Segment

세 종류를 동시에 생성한다.

1. `SEG_TURN`: 현재 turn만
2. `SEG_PREV_CURR`: 이전 turn + 현재 turn
3. `SEG_CURR_NEXT`: 현재 turn + 다음 turn

모든 segment는 `anchor_turn_no`를 가져야 하며, 원본 turn 범위를 `turn_start_no`·`turn_end_no`로 복원할 수 있어야 한다.

## 14. 문장 단위 분류 및 기계학습의 위치

### 14.1 1차 확정 방식

공시 회의록은 표현과 레이아웃이 표준화되어 있으므로, 최초 파서는 다음 조합으로 확정한다.

```text
layout-aware block parsing
+ regular expression
+ State Machine
```

마침표만을 이용한 sentence split은 최초 구조 파서로 사용하지 않는다. PDF 줄바꿈과 한국어 종결 표현 때문에 문장 경계와 발언자 경계가 일치하지 않기 때문이다.

### 14.2 문장 분리는 turn 생성 후 수행

`turn_df`가 완성된 뒤 한국어 문장 분리기 또는 구두점 기반 보정으로 `sentence_count`와 내부 sentence span을 생성한다. 이 sentence span은 TF-IDF 진단·LLM labeling용으로만 사용하고, 구조적 원본 키는 turn을 유지한다.

### 14.3 규칙 파서 성능이 낮을 때의 대체안

다음 조건 중 하나를 넘으면 block/line classifier를 추가한다.

- `UNKNOWN + orphan` 비율 5% 초과
- speaker header recall 95% 미만
- 연도별 포맷 차이로 규칙 수가 과도하게 증가

권장 모델:

```text
character n-gram TF-IDF
+ word TF-IDF
+ bbox/y-position
+ regex flags
→ Logistic Regression 또는 LinearSVC
→ block_type classification
```

순수 문장 텍스트만 분류하지 않고 위치·반복·marker 특징을 함께 사용한다.

## 15. TF-IDF 및 LLM-assisted labeling 연계 원칙

본 ETL 노트북은 `segment_df`까지 생성한다. 후속 검색 단계에서는 다음을 권장한다.

1. word TF-IDF와 character n-gram TF-IDF를 병렬 계산한다.
2. 병렬 브랜치의 topic seed와 모든 retrieval segment를 동일 feature space에서 변환한다.
3. TF-IDF는 높은 재현율을 가진 후보 생성기로 사용한다.
4. 낮은 점수 segment는 raw layer에서 삭제하지 않는다.
5. TF-IDF 후보에 embedding 또는 reranker를 적용한다.
6. LLM-assisted labeling은 전체 원문보다 `UNKNOWN/orphan` 또는 TF-IDF 후보군에 제한한다.
7. LLM 출력은 JSON schema, label, confidence, evidence span을 가져야 한다.
8. LLM label은 weak label로 저장하며 원문·ID를 변경하지 않는다.
9. 충분한 weak/manual label이 누적되면 별도 분류모델 학습 데이터로 전환한다.

## 16. 단일 IPYNB 내부 셀 구성

### `00. 환경 및 경로 고정`

- 라이브러리 import
- `INPUT_XLSX`
- `OUTPUT_ROOT`
- `RAW_PDF_DIR`
- `PARQUET_DIR`
- `DB_DIR`
- `DOCS_DIR`
- `PARSER_VERSION`
- `RUN_MODE`: `pilot`, `full`
- timeout, retry, concurrency, OCR 설정
- enum·regex·schema 상수

### `01. Excel Registry Load`

- 컬럼명 정규화
- `회의ID` 문자열 고정
- 대수·회기·연도·MMDD 파생
- URL 결측·중복 검사
- Control Table 생성

### `02. Download Plan`

- 기존 PDF·hash 확인
- `pending`, `downloaded`, `failed`, `invalid_url`, `invalid_content` 계획 생성
- 재실행 시 완료 파일 skip

### `03. PDF Download`

- HTTP redirect 허용
- HTTP status 기록
- PDF magic bytes `%PDF-` 검사
- raw PDF 저장
- SHA-256·file size 기록
- 실패 로그 기록

### `04. PDF 구조 파일럿`

- 2020·중간연도·최신연도 표본
- 페이지 수·문자 수
- text layer
- block 구조
- header/footer 반복 패턴
- 목차 패턴
- OCR 필요성

### `05. 전체 PDF Block Extraction`

- page audit
- native block 추출
- 조건부 OCR
- `page_df`, 초기 `block_df`

### `06. Header/Footer 및 Index Detection`

- 상·하단 좌표+반복빈도 탐지
- `index_df` 생성
- page/block에 `index_no` 전파

### `07. Block Classification`

- 고정 우선순위 적용
- `block_type`, rule, confidence 기록

### `08. Speaker Turn State Machine`

- block stream 결합
- speaker parsing
- procedural/orphan turn 저장
- `turn_df` 생성

### `09. Retrieval Segment Builder`

- `SEG_TURN`
- `SEG_PREV_CURR`
- `SEG_CURR_NEXT`
- hash, TF-IDF-ready 검사
- `segment_df` 생성

### `10. Quality Audit 및 Export`

- 품질 지표 계산
- Quality Gate 판정
- Parquet export
- SQLite export
- manifest export
- SSOT 문서 자동 생성/갱신

## 17. Quality Gate

| 지표 | PASS 기준 | 처리 |
|---|---:|---|
| registry `meeting_id` 중복 | 0건 | 중복 시 실행 중단 |
| URL 결측 | 0건 | 결측 행 FAIL |
| PDF magic bytes 오류 | 0건 | 재시도 후 FAIL |
| page record coverage | `page_df` 행 수 = page_count 합 | 불일치 FAIL |
| OCR 후 빈 페이지 | 0건 | FAIL |
| speaker header precision | ≥ 0.98 표본검사 | 미달 시 regex 수정 |
| speaker header recall | ≥ 0.95 표본검사 | 미달 시 classifier 검토 |
| `UNKNOWN + orphan` 비율 | ≤ 5% | 초과 WARN/FAIL |
| body 없는 speaker turn | ≤ 2% | 초과 WARN |
| parser 중복 텍스트 | ≤ 1% | 초과 정규화 규칙 수정 |
| segment 역추적 가능률 | 100% | 누락 시 FAIL |

모든 threshold는 `pipeline_manifest.json`에 기록한다.

## 18. 출력 폴더와 파일 목록

출력 루트:

```text
outputs/09_audit_minutes_pdf_etl/
```

확정 파일 목록은 다음으로 제한한다.

```text
outputs/09_audit_minutes_pdf_etl/
├─ raw_pdf/
│  └─ {meeting_id}.pdf
├─ control_registry.parquet
├─ index_map.parquet
├─ pages.parquet
├─ blocks.parquet
├─ speaker_turns.parquet
├─ retrieval_segments.parquet
├─ quality_audit.parquet
├─ audit_minutes.sqlite
├─ pipeline_manifest.json
└─ SSOT_audit_minutes_pdf_etl_v1.0.md
```

- CSV는 canonical output으로 생성하지 않는다.
- DataFrame은 노트북 런타임 객체다.
- Parquet가 분석용 SSOT다.
- SQLite는 관계형 탐색·인덱싱용 mirror다.
- raw PDF는 증거 원본이다.

SQLite 테이블:

- `meeting_registry`
- `index_map`
- `pages`
- `blocks`
- `speaker_turns`
- `retrieval_segments`
- `quality_audit`
- `pipeline_manifest`

## 19. 실행 금지사항

- `meeting_id`를 숫자로 변환
- URL에서 텍스트만 추출하고 PDF 미보존
- PDF 전체를 바로 하나의 TXT로 합치기
- 좌표·페이지 정보를 버리기
- raw text 덮어쓰기
- header/footer를 원본에서 삭제
- 마침표만으로 발언 경계 결정
- TF-IDF 이전에 인명·기관명·숫자·부정어 제거
- OCR을 전체 페이지에 무조건 실행
- low-score 원문 물리 삭제
- 다른 IPYNB에서 함수·셀·전역상태 import
- 품질 실패를 빈 DataFrame으로 조용히 통과

## 20. 완료 조건

다음 조건을 모두 충족해야 v1 파이프라인을 완료로 판정한다.

1. Excel 모든 행이 `registry_df`에서 고유하게 관리된다.
2. 각 성공 URL은 hash가 있는 raw PDF로 저장된다.
3. PDF 모든 페이지가 `page_df`에 존재한다.
4. 모든 text/image block이 `block_df`에 존재한다.
5. 모든 block은 고정 `block_type` 또는 `UNKNOWN`을 가진다.
6. 모든 유효 발언은 `turn_df`에서 page·block 원본으로 역추적된다.
7. 각 anchor turn에 3종 retrieval segment가 생성된다.
8. OCR 페이지와 원인이 기록된다.
9. Quality Gate 결과가 `quality_audit.parquet`에 남는다.
10. Parquet, SQLite, manifest, SSOT 문서가 동일 parser version과 run ID를 공유한다.