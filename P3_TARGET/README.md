# P3_TARGET — Marked Audit Results 2020 / 2022 / 2024

문화체육관광위원회 국정감사 처리결과 보고서의 PDF Highlight annotation을 행 선택 프록시로 사용해, 마킹된 요구사항과 대응 조치를 구조화한 병렬 준비 브랜치입니다.

이 디렉터리와 브랜치의 작업 범위는 `P3_TARGET/`으로 제한합니다. 현재 2020년, 2022년, 2024년을 처리하며 2021년과 2023년은 범위에서 제외합니다.

## 실행 노트북

- `03_2020_marked_audit_result.ipynb`
- `03_2022_marked_audit_result.ipynb`
- `03_2024_marked_audit_result.ipynb`

각 노트북은 annotation audit, 목차·본문 행 파싱, `issue_no` 매핑, 본문 anchor 분리, 상태 분류, 조건부 OCR, 2차 논제 검토, export 및 재로딩 검증을 독립적으로 수행합니다. 세 노트북 모두 전체 실행을 완료했으며 코드 셀 14개에 실행 번호와 결과가 저장돼 있습니다.

## 입력 PDF

| 연도 | 선택 입력 | SHA-256 | 페이지 | Highlight |
|---|---|---|---:|---:|
| 2020 | `target_mark_pdf/2020년도_국정감사결과_형광펜_통합본.pdf` | `39b22045f62625a1dea321a714e041b119632f640f208da55c2cbb5ea8088d86` | 165 | 283 |
| 2022 | `target_mark_pdf/2022_국정감사결과_요구사항1-259_260-끝_병합.pdf` | `9390284efe2f80a8b544cfe2da900805ed02941db8a1a7a37a5dec960fb0b4cb` | 159 | 246 |
| 2024 | `target_mark_pdf/2024년도 국정감사결과 시정 및 처리 요구사항에 대한 처리결과 보고서 (1).pdf` | `711e69f611728cea69d9eb71808c1fb1d71522335b336a73f7df334d9ab7b0e6` | 172 | 167 |

2020년 노트북은 같은 연도의 PDF 2개를 차례로 audit한 뒤 Highlight가 더 완전한 통합본을 canonical 입력으로 선택합니다.

## 최종 CSV

- `outputs/marked_parallel/2020/2020_marked_issue_mapping.csv`
- `outputs/marked_parallel/2022/2022_marked_issue_mapping.csv`
- `outputs/marked_parallel/2024/2024_marked_issue_mapping.csv`

CSV 컬럼은 다음 8개로 고정합니다.

```text
meeting_id
meeting_year
issue_no
issue_text
action_text
future_plan_text
status
source_page
```

`action_text`, `future_plan_text`, `status`의 미식별값은 빈 값이 아니라 literal string `null`로 기록합니다.

## 품질 결과

| 연도 | 선택 논제 | 매핑 | 2차 검토 통과 | complete | active | uncomplete | null | 최종 상태 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2020 | 110 | 110 | 110 | 56 | 54 | 0 | 0 | COMPLETE |
| 2022 | 116 | 116 | 116 | 77 | 39 | 0 | 0 | COMPLETE |
| 2024 | 71 | 71 | 71 | 37 | 34 | 0 | 0 | COMPLETE |

- 모든 issue-selector Highlight annotation은 목차 또는 본문 `issue_no`로 연결됐습니다. 2022년 표지 Highlight 1건은 `front_matter` non-selector로 별도 기록합니다.
- 모든 선택 논제의 `issue_text`가 추출됐고 `issue_id`는 중복이 없습니다.
- 조건부 OCR은 2020년 4건, 2022년 3건, 2024년 1건 시도했으며 OCR로 대체된 행은 없습니다.
- 상세 품질 결과는 `reports/2020_MARKED_MAPPING_QUALITY.md`, `reports/2022_MARKED_MAPPING_QUALITY.md`, `reports/2024_MARKED_MAPPING_QUALITY.md`에 있습니다.

## Registry 및 SSOT 관계

Registry에서 유일한 `meeting_id`를 확정할 수 없어 임의 매핑하지 않았습니다.

- 2020: `UNMAPPED_REPORT_2020`, `meeting_year=20`
- 2022: `UNMAPPED_REPORT_2022`, `meeting_year=22`
- 2024: `UNMAPPED_REPORT_2024`, `meeting_year=24`

`P3_CULTURE/SSOT.md`와 `P3_PROJECT/`는 읽기 전용으로 점검했습니다. 기존 SSOT는 회의록 ETL 계약이며, `P3_PROJECT`의 기준 노트북은 현재 setup-only / not-executed 상태입니다. 이 브랜치의 결과는 그 원본을 변경하지 않는 `P3_TARGET` 병렬 marked-result 데이터셋입니다.

## 재실행

`P3_CULTURE`에서 실행합니다.

```bash
python3 -m jupyter nbconvert --to notebook --execute P3_TARGET/03_2020_marked_audit_result.ipynb --inplace --ExecutePreprocessor.timeout=1800
python3 -m jupyter nbconvert --to notebook --execute P3_TARGET/03_2022_marked_audit_result.ipynb --inplace --ExecutePreprocessor.timeout=1800
python3 -m jupyter nbconvert --to notebook --execute P3_TARGET/03_2024_marked_audit_result.ipynb --inplace --ExecutePreprocessor.timeout=1800
```

브랜치: `P3_MARKED_2020_2024`
