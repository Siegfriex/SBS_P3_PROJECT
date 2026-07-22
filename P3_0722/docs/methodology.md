# Methodology

## Evidence chain

`marker → retrieval candidate → Q/A pair → answer unit → turn → block → page → PDF`를 ID와 bridge table로 연결한다.

## 입력

- 42개 회의록 PDF와 검증된 canonical ETL 동결본
- 확정된 2020·2022·2024 marker CSV 297건
- PRD v3.0과 Schema Registry v1.0

## 시간 적격성

target year와 같은 audit cycle의 회의록만 벡터화·검색한다. 전체 corpus 점수 계산 후 미래 결과를 숨기는 방식은 사용하지 않는다.

## 검색

char TF-IDF 3–5 gram 65%, word TF-IDF 1–2 gram 35%를 사용한다. query는 issue text에 action text vector 0.25를 더한다. 연도별 top 50은 qrels 검수 후보이지 정답이 아니다.

## Q/A 및 답변행태

Q/A는 위원 turn 뒤의 명시적 기관·증인 허용 role을 이용한 규칙 후보이다. 답변행태 A1~A8은 multi-hit weak rule이며 수동 검수 전 기사 통계로 확정하지 않는다.

## 투영

다국어 MiniLM 문장 임베딩을 L2 정규화한 뒤 전체 상태를 함께 PCA 50차원으로 축약하고 공통 UMAP을 한 번만 fit한다. Dense 점수는 시간 적격 sparse top-50 pool을 재정렬하며, full-corpus dense recall은 Gold qrels 이후 별도로 평가한다.
