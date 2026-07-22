# P3_CULTURE P3_0722

PRD v3.0을 기준으로 회의록 PDF, 확정 marker, Q/A 후보, answer unit, 답변행태, evidence chain, Atlas baseline, 편집·프론트 번들을 연결하는 실행 코드베이스다.

## 실행

```bash
cd /home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_0722
USE_TF=0 TRANSFORMERS_NO_TF=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 NUMBA_CACHE_DIR=/tmp/p3_0722_numba_cache MPLCONFIGDIR=/tmp/p3_0722_mplconfig ../../.venv/bin/python pipeline/run_pipeline.py
../../.venv/bin/python pipeline/build_main_notebook.py
MPLCONFIGDIR=/tmp/p3_0722_mplconfig ../../.venv/bin/jupyter nbconvert --to notebook --execute main.ipynb --inplace --ExecutePreprocessor.timeout=600 --ExecutePreprocessor.kernel_name=dsja_sbs_venv
```

## 구조

- `config/`: 고정 파라미터
- `pipeline/`: 전체 데이터 파이프라인과 notebook builder
- `data/`: schema 계층별 parquet 및 프론트 번들
- `evidence/`: dataset/claim evidence 계약
- `figures/`: 기사·감사용 정적 시각화
- `outputs/`: manifest, review queue, 최종 보고서
- `docs/`: 방법론·taxonomy·source policy·decision log
- `tests/`: 핵심 gate 회귀 테스트

## 현재 해석 상태

전체 자동 파이프라인은 끝까지 실행되지만 공개준비 판정은 `PIPELINE_CONDITIONAL_REVIEW_REQUIRED`다. Gold qrels, Q/A precision/recall, A1~A8 Gold, 완료 외부검증이 남아 있기 때문이다.
