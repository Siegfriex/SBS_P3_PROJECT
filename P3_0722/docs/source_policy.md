# Source Policy

- 회의록 PDF와 처리결과 marker 원문은 수정하지 않는다.
- 프론트 번들에는 절대 로컬 경로를 노출하지 않는다.
- 공식 `complete`는 보고서의 상태이며 실제 완료로 자동 승인하지 않는다.
- 2025 회의록은 parser/taxonomy stress test에는 사용할 수 있으나 2020·2022·2024 retrieval corpus에는 포함하지 않는다.
- evidence는 qrels, Q/A, behavior, completion review가 끝날 때까지 `draft`, `public_visibility=false`로 둔다.
