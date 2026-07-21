# SBS P3 Project

국정감사 회의록에서 문화체육 분야 질의·답변 구간을 회수하고, 후속 분석에서 회피 패턴을 탐지하기 위한 데이터 전처리 프로젝트입니다.

## Branch Scope

현재 브랜치 `P3_DATA_RAW`는 원본 데이터와 초기 탐색 환경을 정리하는 브랜치입니다.

- 원본 파일은 `data_origin/`에 보존합니다.
- 파싱 결과와 중간 산출물은 `data_parse/`에 분리합니다.
- 분석 기준, 가설, 파이프라인 설계 문서는 `plan/`에 둡니다.
- 원본을 직접 수정하지 않고 노트북 또는 스크립트에서 재현 가능한 변환 절차를 남깁니다.

## Project Layout

```text
.
├── 01_eda.ipynb                         # 원본 엑셀 구조 확인용 스타터 노트북
├── data_origin/                         # 원본 데이터 보관
├── data_parse/                          # 파싱/전처리 산출물
├── data_dict/                           # 컬럼 정의, 코드북, 메타데이터
├── pdf_raw_data/                        # 원본 PDF가 확보될 경우 보관
├── pic/                                 # 시각화 및 보고용 이미지 산출물
├── plan/                                # 분석 설계와 처리 계획
└── requirements.txt                     # 최소 실행 의존성
```

## Current Raw Data

- `data_origin/국정감사회의록_문화체육 2020~.xlsx`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m ipykernel install --user --name sbs-p3-project --display-name "Python (SBS P3)"
```

## First Check

```bash
jupyter lab 01_eda.ipynb
```

`01_eda.ipynb`는 원본 파일 존재 여부, 시트 목록, 컬럼, 샘플 행을 먼저 확인하도록 구성되어 있습니다.
