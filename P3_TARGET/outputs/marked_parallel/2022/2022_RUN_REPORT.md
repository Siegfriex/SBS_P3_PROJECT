# Marked Audit Result Index Run Report

## 1. 실행 개요
- PROJECT_ROOT: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET`
- Notebook: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/03_2022_marked_audit_result.ipynb`
- Canonical PDF: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/target_mark_pdf/2022_국정감사결과_요구사항1-259_260-끝_병합.pdf`
- PDF SHA-256: `9390284efe2f80a8b544cfe2da900805ed02941db8a1a7a37a5dec960fb0b4cb`
- Page count: 159
- Registry: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/data_parse/pdf_crawler/control_registry.parquet`
- meeting_id: `UNMAPPED_REPORT_2022`
- Registry mapping: unmapped

## 2. PDF/Annotation
- 공급 PDF 감사: 1건
- Highlight annotation: 246
- 표지 non-selector annotation: 1
- 목차 annotation: 101
- 본문 annotation: 144
- annotation unresolved: 0

## 3. Mapping 및 OCR
- 선택 issue: 116
- Mapping 성공: 116
- Mapping unresolved: 0
- Native parsed: 116
- OCR 시도: 3
- OCR 성공: 0
- OCR failure: 0
- 2차 전수검토: 116/116 PASS
- 2차 검토 flagged: []

## 4. 상태 분류
- complete: 77
- active: 39
- uncomplete: 0
- null: 0

## 5. 생성 파일
- Parquet: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/outputs/marked_parallel/2022/2022_marked_issue_mapping.parquet`
- CSV: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/outputs/marked_parallel/2022/2022_marked_issue_mapping.csv`
- Manifest: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/outputs/marked_parallel/2022/2022_pipeline_manifest.json`
- Quality Report: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/reports/2022_MARKED_MAPPING_QUALITY.md`
- Notebook: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/03_2022_marked_audit_result.ipynb`
- Log: `/home/sieg/projects-wsl/SBS_dataScience/DSJA/P3_CULTURE/P3_TARGET/outputs/marked_parallel/2022/logs/2022_marked_audit_result.log`

## 6. 최종 샘플
| meeting_id | meeting_year | issue_no | issue_text | action_text | future_plan_text | status | source_page |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UNMAPPED_REPORT_2022 | 22 | 5 | 한국문화관광연구원단기현안 과제수행관련규정명확화필요 | 조치완료 연구사업추진지침개정(‘23년1월) ㅇ - 지침내단기현안연구(현안과제) 유형및수행절차명시 (기본연구수행절차준용) | ㅇ지침준수여부점검등관리·감독철저 | complete | 27 |
| UNMAPPED_REPORT_2022 | 22 | 13 | 소관위원회의인적구성다양화 및운영내실화필요 | 조치완료 ㅇ문체부소관위원회장애인위원확대계획수립및보고(‘22.11.) - 향후신규위원선임소요발생시소관분야의전문성을갖춘 장애인위원1명이상위촉계획수립 부내위원회담당대상장애인위원확대계획전파(’22.11.) ㅇ | ㅇ위원회별장애인위원위촉확대및현황파악지속추진 | complete | 28 |
| UNMAPPED_REPORT_2022 | 22 | 24 | 세종학당사업수행방식을보조금 에서출연금으로전환하는등 법적근거마련을위한「국어 기본법」개정을위해문체부가 적극적으로협조할것 | 조치중 관련국어기본법개정안국회발의 ㅇ - 임오경의원대표발의(’22.11.22) · (주요내용) 세종학당재단에대한법적출연근거마련, 세종학당 재단의국유재산․물품무상대부및사용에관한법적근거마련 | 관련법개정에대해사업운영의효율성및예산운용의 ㅇ 투명성을종합적으로검토해신중하게추진 | active | 31 |
| UNMAPPED_REPORT_2022 | 22 | 28 | 국립세계문자박물관에서현재 까지수집한소장품및관련 용역에대한전수조사실시 하여보고할것 | 조치완료 ㅇ소장품수집관련전수조사계획수립(’22.11.2.) - 소장품전수조사, 전시계획과의정합성평가, 수집규정 정비, 향후구매계획포함 ㅇ소장품전수조사(총228건, ’22.10.31.~11.4.) ㅇ소장품전수조사결과의원실별도보고완료(’22.12.13.) ㅇ자료수집및관리규정제정완료(’23.6월) | null | complete | 32 |
| UNMAPPED_REPORT_2022 | 22 | 52 | BF(배리어프리) 인증실태를 제대로파악하고, 박물관·미술관의 배리어프리확산을위한방안을 마련하여적극적으로추진할것 | 조치완료 국·공립박물관및미술관장애인편의시설실태전수조사 ㅇ 및개선방향연구, 현황파악및개선을위한정책세미나 개최(22.12.20.) 실태조사결과토대로기관별개선사항통보(‘23.2.3.), 국· ㅇ 공립박물관및미술관장애인편의시설담당자대상교육 개최(23.2.28.) | null | complete | 38 |
| UNMAPPED_REPORT_2022 | 22 | 59 | 한국콘텐츠진흥원 허위자료 제출, 인사, 급여등문제가 있어철저한조사를통해적법한 조치를취할것 | 조치중 요청자료(`12년∼`22년승진자명단/등급/연차등)의오류를확인, ㅇ 엄중사과하고수정제출(`22.9.28), 재방문설명(`22.9.30) 재발방지를위해국회제출자료에대한중복점검강화, 직원 ㅇ 교육강화, 담당부서장엄중경고(`22.10월) 인건비및운영비는국고사업통장으로별도관리하고 ㅇ 인건비는집행잔액정산시반납완료 `19년∼`21년해당계좌집행기록자료제출(∼`22.10.20.) ㅇ | 인사관리시스템의승진자동순위산출, 통계화기능등 ㅇ 고도화지속추진(`22.10월∼) - 현재’23년정보화사업위탁용역업체선정완료(3월) 하였으며, 요구사항분석및시스템기획을거쳐연내개선완료예정 ERP(전사적자원관리시스템) 급여계산시스템지속 ㅇ 보강(임금피크제비율, 성과급비율등)(계속) - 현재’23년정보화사업위탁용역업체선정완료(3월) 하였으며, 요구사항분석및시스템기획을거쳐연내개선완료예정 | active | 40 |
| UNMAPPED_REPORT_2022 | 22 | 64 | 영화발전기금고갈위기상황으로, 글로벌OTT 사업자도국내영화 산업발전차원에서기금부과필요 | 조치중 영화발전기금재원확대를위한사전검토등추진 ㅇ ‘영화’의법적정의재검토*, 온라인영화유통거래확보** - 등제도적설계선행추진 * ‘영화’ 정의재검토등을포함한‘영화및비디오물의진흥에관한법률 개정’ 연구(’22.9월∼‘23.5월) ** 온라인상영관통합전산망구축·운영및사업자참여확대노력(’22년〜) | 온라인영화유통거래정보확보등인프라선행구축및운영 ㅇ 안정화지속 - 다만, OTT 부과금징수는산업성장초기단계인점을감안, 신중한접근필요 | active | 42 |
| UNMAPPED_REPORT_2022 | 22 | 74 | 네이버제트 등 메타버스를 선도하는기업등이자체등급 분류사업자가되는방안등에 대해콘텐츠를관장하는주무 부처로서다른부처와협의할것 | 조치완료 ㅇ‘메타버스와게임물구분등을위한가이드라인’ 마련추진(‘22.9∼) - 관계부처TF(문체부·과기부)를구성해현재까지실무 회의다수개최(‘22.9∼) | 가이드라인마련을위해현재과기부등관계부처와지속협의 ㅇ | complete | 44 |
| UNMAPPED_REPORT_2022 | 22 | 81 | 2020년선정된인천시음악 창작소의정상운영에대한 우려및당시공모선정과 정의적정성에대해조사할것 | 조치완료 ㅇ인천음창소공모선정과정의적정성조사완료(‘22.12월) * ‘20년지역기반형음악창작소조성공모에캠프마켓을‘녹지문화공간 및음악클러스터조성‘으로신청하여인천시가최고점수를받아선정 되었고, 오염토로인한건물변경, 국방부건물사용승인지연등으로시 설물조성까지장기간소요(’22.9월준공) 되었는바, 이점을심사당시 심사위원이인지하기는곤란하였다고판단됨. | 캠프마켓마스터플랜연구용역(~’24.2월) 및인천시음악 ㅇ 창작소건물보존검토중 | complete | 46 |
| UNMAPPED_REPORT_2022 | 22 | 82 | 온라인암표신고게시판의 실효성이없어, 이를보완할 온라인암표매매실태및 피해규모파악, 온라인암표 근절 캠페인 시행, 온라인 암표거래단속을위한법 개정등에대해조사할것 | 조치중 한국콘텐츠진흥원과협의하여매크로의심사례를실효성 ㅇ 있게선별할수있도록온라인암표신고게시판개선(’23년~) 온라인암표근절홍보대사위촉및캠페인시행(’23년) ㅇ 매크로프로그램을이용한부정판매금지및처벌을내 ㅇ 용으로하는「공연법」개정(’24.3.22. 시행) 중고거래사이트, 공연기획사등암표관련대책마련을위한 ㅇ 이해관계자및경찰청등관계부처의견수렴중(‘23년~) | ㅇ향후티켓예매처· 경찰청등관계기관협의를통해실효성 있는암표근절대책마련예정 | active | 47 |

## 7. 경고
- No unique meeting_id matched

## 8. 최종 상태
- **COMPLETE**
