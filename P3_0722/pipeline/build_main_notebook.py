#!/usr/bin/env python3
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB_PATH = ROOT / "main.ipynb"

nb = nbf.v4.new_notebook()
nb.metadata.kernelspec = {"display_name": "Python 3 (DSJA)", "language": "python", "name": "dsja_sbs_venv"}
nb.metadata.language_info = {"name": "python", "version": "3.13"}

cells = []
cells.append(nbf.v4.new_markdown_cell("""# 문체위 국정감사 6년 — Evidence Pipeline

이 노트북은 `P3_0722` 파이프라인의 독자·편집자용 최종 점검본이다. 42개 회의록 PDF와 확정 marker 297건을 연결한 자동 후보를 보여 주되, Gold qrels·수동 Q/A 검수·외부 완료검증 전에는 공개 사실로 단정하지 않는다.

핵심 질문은 **“국정감사에서 요구된 문제는 어떤 답변을 거쳐 어떤 처리결과로 남았는가?”**이다."""))
cells.append(nbf.v4.new_code_cell("""from pathlib import Path
import json
import pandas as pd
from IPython.display import display, Image, Markdown

ROOT = Path.cwd()
if not (ROOT / 'outputs' / 'pipeline_manifest.json').exists():
    raise FileNotFoundError('P3_0722 폴더에서 실행해야 합니다.')
manifest = json.loads((ROOT / 'outputs' / 'pipeline_manifest.json').read_text(encoding='utf-8'))
print('run:', manifest['pipeline_run_id'])
print('status:', manifest['status'])"""))
cells.append(nbf.v4.new_markdown_cell("## 1. 데이터 범위와 provenance"))
cells.append(nbf.v4.new_code_cell("""overview = pd.read_csv(ROOT / 'evidence' / 'dataset_overview.csv', encoding='utf-8-sig')
display(overview)
display(Image(filename=str(ROOT / 'figures' / '04_pipeline_scale.png')))"""))
cells.append(nbf.v4.new_markdown_cell("## 2. Gate — 자동 파이프라인 완료와 공개 준비는 다르다"))
cells.append(nbf.v4.new_code_cell("""gate_df = pd.DataFrame(manifest['gates'].items(), columns=['gate', 'status'])
display(gate_df)
display(Markdown('**현재 판정:** 자동 후보·번들 생성은 완료했지만 수동 qrels/Q&A/행태/완료 검증이 남아 있습니다.'))"""))
cells.append(nbf.v4.new_markdown_cell("## 3. 확정 marker 2020·2022·2024"))
cells.append(nbf.v4.new_code_cell("""targets = pd.read_parquet(ROOT / 'data' / 'target' / 'target_issues.parquet')
display(targets.groupby(['source_year','status_canvas']).size().rename('count').reset_index())
display(Image(filename=str(ROOT / 'figures' / '01_target_status_by_year.png')))"""))
cells.append(nbf.v4.new_markdown_cell("## 4. 답변 단위와 행태 후보"))
cells.append(nbf.v4.new_code_cell("""answers = pd.read_parquet(ROOT / 'data' / 'qa' / 'answer_units.parquet')
labels = pd.read_parquet(ROOT / 'data' / 'qa' / 'answer_behavior_labels.parquet')
print('answer_units:', len(answers))
print('traceability:', (answers['traceability_status'] == 'PASS').mean())
display(Image(filename=str(ROOT / 'figures' / '02_behavior_weak_rule_counts.png')))
display(Markdown('A1~A8은 첫 매칭에서 중단하지 않는 multi-hit 후보이며, Gold 라벨이 아닙니다.'))"""))
cells.append(nbf.v4.new_markdown_cell("## 5. 한 evidence chain 역추적"))
cells.append(nbf.v4.new_code_cell("""links = pd.read_parquet(ROOT / 'data' / 'qa' / 'target_answer_links.parquet')
qa = pd.read_parquet(ROOT / 'data' / 'qa' / 'qa_pairs.parquet')
evidence = pd.read_parquet(ROOT / 'data' / 'editorial' / 'evidence_records.parquet')
sample = (evidence.head(1)
          .merge(targets[['target_issue_id','issue_text','status_canvas']], on='target_issue_id')
          .merge(qa[['qa_pair_id','question_text','answer_text']], on='qa_pair_id'))
display(sample.T)
display(Markdown('`target → link → Q/A → answer → turn → block → page → PDF`를 ID로 복원할 수 있습니다.'))"""))
cells.append(nbf.v4.new_markdown_cell("## 6. 가설·진단 결과와 안전 문장"))
cells.append(nbf.v4.new_code_cell("""hypothesis = pd.read_csv(ROOT / 'data' / 'analysis_csv' / 'hypothesis_result_summary.csv', encoding='utf-8-sig')
display(hypothesis[['hypothesis','article_question','test','effect_size_name','effect_size','safe_sentence','avoid']])
display(Image(filename=str(ROOT / 'figures' / '03_answer_length_qa_confidence.png')))"""))
cells.append(nbf.v4.new_markdown_cell("""## 7. 편집 한계와 다음 검수

- `data/qrels/qrels_review_queue.csv`: 400건을 relevance 0/1/2로 검수해야 한다.
- `outputs/answer_review_sample.csv`: Q/A precision과 A1~A8 weak-rule precision을 측정해야 한다.
- `completion_verifications`: 현재 전부 `not_reviewed`다.
- 2025 회의록은 2020·2022·2024 target retrieval에서 제외했다.
- 다국어 MiniLM + 공통 PCA50/UMAP은 실행했지만, Gold qrels 전에는 투영의 편집적 대표성을 승인하지 않는다.

따라서 현재 데이터로 쓸 수 있는 문장은 **구조·규모·자동 후보에 대한 기술적·서술적 문장**이며, “회피율”, “실제 완료율”, “기관별 책임”을 확정적으로 말하면 안 된다."""))

nb.cells = cells
nbf.write(nb, NB_PATH)
print(NB_PATH)
