from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .common import compact_text, normalize_text, short_hash


COMMITTEE_ROLES = ["위원장직무대리", "위원장대리", "부위원장", "위원장", "간사", "위원"]
OFFICIAL_ROLES = [
    "사무총장", "상임감사", "상임이사", "대표이사", "이사장", "위원장", "부위원장",
    "본부장", "담당관", "센터장", "사무국장", "정책관", "연구소장", "극장장",
    "차관", "장관", "청장", "원장", "사장", "회장", "소장", "단장", "국장", "실장",
    "관장", "총장", "처장", "부장", "과장", "감사", "이사", "대표", "감독", "증인", "참고인",
]
OFFICIAL_ROLES = sorted(set(OFFICIAL_ROLES), key=len, reverse=True)
OFFICIAL_ALT = "|".join(re.escape(x) for x in OFFICIAL_ROLES)
NAME_CHARS = r"가-힣一-龥"


def speaker_head_from_block(raw_text: Any) -> str:
    # val2 preserves the speaker marker but, for many PDFs, speaker_raw/block_text
    # also contains the beginning of the utterance.  Extract only the anchored
    # header prefix; never split a turn again on ○/◯.
    raw = re.sub(r"^\s*[○◯]\s*", "", str(raw_text or ""))
    text = normalize_text(raw.splitlines()[0] if raw.splitlines() else raw)
    if not text:
        return ""

    member = re.match(rf"^(?P<name>[{NAME_CHARS}]{{2,4}}?)\s*위원(?:님)?", text)
    if member:
        return f"{member.group('name')}위원"

    chair = re.match(
        rf"^(?P<role>위원장직무대리|위원장대리|부위원장|위원장|간사)\s*(?P<name>[{NAME_CHARS}]{{2,4}})",
        text,
    )
    if chair:
        # Most names are three syllables. Compact legacy PDFs do not retain a
        # boundary after the name, so cap the ambiguous fallback at 3.
        name = chair.group("name")
        if not re.match(rf"^{re.escape(chair.group(0))}(?:\s|[\"“”'(),.!?…])", text):
            name = name[:3]
        return f"{chair.group('role')}{name}"

    procedural = re.match(r"^출석\s*(전문위원|위원회직원|입법조사관)", text)
    if procedural:
        return f"출석{procedural.group(1)}"

    # Prefer an explicit whitespace/punctuation boundary after a 2-4 character
    # name. For space-collapsed legacy pages, use the conventional 3-character
    # Korean name fallback while retaining the entire organization prefix.
    spaced = re.match(
        rf"^(?P<org>.*?)(?P<role>{OFFICIAL_ALT})\s*(?P<name>[{NAME_CHARS}]{{2,4}})(?=\s|[\"“”'(),.!?…]|$)",
        text,
    )
    if spaced:
        return f"{spaced.group('org')}{spaced.group('role')}{spaced.group('name')}"
    compact = re.match(
        rf"^(?P<org>.*?)(?P<role>{OFFICIAL_ALT})\s*(?P<name>[{NAME_CHARS}]{{3}})",
        text,
    )
    if compact:
        return f"{compact.group('org')}{compact.group('role')}{compact.group('name')}"
    return text[:80]


def parse_speaker(head: Any) -> dict[str, Any]:
    text = compact_text(head)
    result = {
        "speaker_raw": normalize_text(head),
        "speaker_name": pd.NA,
        "speaker_role_raw": pd.NA,
        "speaker_role_normalized": pd.NA,
        "speaker_org": pd.NA,
        "speaker_side": "unknown",
        "speaker_class": "unknown",
        "is_question_eligible": False,
        "is_answer_eligible": False,
        "parse_rule": "UNRESOLVED",
        "parse_confidence": 0.2,
        "manual_override": False,
    }
    if not text:
        return result

    m = re.match(rf"^(위원장직무대리|위원장대리|부위원장|위원장|간사)([{NAME_CHARS}]{{2,4}})$", text)
    if m:
        role, name = m.groups()
        result.update(
            speaker_name=name,
            speaker_role_raw=role,
            speaker_role_normalized=role,
            speaker_side="procedural" if "위원장" in role else "committee",
            speaker_class="committee_chair" if "위원장" in role else "committee_member",
            is_question_eligible=role == "간사",
            parse_rule="COMMITTEE_ROLE_PREFIX",
            parse_confidence=0.96,
        )
        return result

    m = re.match(rf"^([{NAME_CHARS}]{{2,4}})위원(?:님)?$", text)
    if m:
        result.update(
            speaker_name=m.group(1),
            speaker_role_raw="위원",
            speaker_role_normalized="위원",
            speaker_side="committee",
            speaker_class="committee_member",
            is_question_eligible=True,
            parse_rule="COMMITTEE_MEMBER_SUFFIX",
            parse_confidence=0.98,
        )
        return result

    if re.match(r"^출석(?:전문위원|위원회직원|입법조사관)$", text):
        result.update(
            speaker_role_raw="전문위원",
            speaker_role_normalized="전문위원",
            speaker_side="procedural",
            speaker_class="secretariat",
            parse_rule="SECRETARIAT_PREFIX",
            parse_confidence=0.95,
        )
        return result

    m = re.match(rf"^(.*?)(?P<role>{OFFICIAL_ALT})(?P<name>[{NAME_CHARS}]{{2,4}})$", text)
    if m:
        org = m.group(1)
        role = m.group("role")
        name = m.group("name")
        speaker_class = "agency_official"
        if role == "장관":
            speaker_class = "minister"
        elif role == "차관":
            speaker_class = "vice_minister"
        elif role in {"청장", "원장", "사장", "이사장", "총장", "관장", "위원장", "회장", "소장", "연구소장", "극장장"}:
            speaker_class = "agency_head"
        elif role == "증인":
            speaker_class = "witness"
        elif role == "참고인":
            speaker_class = "reference_witness"
        result.update(
            speaker_name=name,
            speaker_role_raw=role,
            speaker_role_normalized=role,
            speaker_org=org or pd.NA,
            speaker_side="institution",
            speaker_class=speaker_class,
            is_answer_eligible=True,
            parse_rule="OFFICIAL_ROLE_PREFIX",
            parse_confidence=0.9,
        )
        return result

    return result


BEHAVIOR_LEXICON = [
    ("A1", "기억 부재 진술", [r"기억(?:이)?\s*(?:나지|안\s*납|없)", r"기억하지\s*못", r"잘\s*모르겠"]),
    ("A2", "정보 미보유·확인 필요", [r"확인(?:해|하)\s*보", r"파악하지\s*못", r"자료가\s*없", r"알지\s*못", r"답변(?:이)?\s*어렵"]),
    ("A3", "타기관·타주체 귀속", [r"소관(?:이)?\s*아니", r"저희\s*권한(?:이)?\s*아니", r"다른\s*기관\s*소관", r"관계\s*부처\s*소관"]),
    ("A4", "질문 비직접 대응", [r"공감합니다", r"취지는\s*이해", r"유념하겠습니다"]),
    ("A5", "검토·협의 유보", [r"검토하겠습니다", r"검토해\s*보겠습니다", r"협의하겠습니다", r"논의하겠습니다", r"방안을\s*마련하겠습니다"]),
    ("A6", "조사·자료 제출 절차", [r"조사하겠습니다", r"자료를?\s*제출", r"서면으로\s*답변", r"보고드리겠습니다", r"확인\s*후\s*답변"]),
    ("A7", "구체 조치 약속", [r"개선하겠습니다", r"개정하겠습니다", r"추진하겠습니다", r"계획을\s*수립", r"대책을\s*마련", r"\d{1,2}월까지"]),
    ("A8", "완료·근거 제시", [r"조치(?:를)?\s*완료", r"시행하였", r"제출하였", r"개정하였", r"완료했습니다", r"\d+(?:\.\d+)?%", r"\d+(?:,\d{3})*건"]),
]

NEGATION_RE = re.compile(r"(?:아닙니다|아니다|않습니다|않다|그런\s*뜻이\s*아니|말씀드린\s*것은\s*아니)")
QUOTE_RE = re.compile(r"(?:위원님께서|질문에서|말씀하신).{0,30}(?:라고|느냐고|냐고)")


def behavior_lexicon_rows() -> list[dict[str, Any]]:
    rows = []
    for code, label, patterns in BEHAVIOR_LEXICON:
        for seq, pattern in enumerate(patterns, start=1):
            rows.append(
                {
                    "lexicon_pattern_id": f"LEX_{code}_{seq:03d}",
                    "behavior_code": code,
                    "behavior_label_ko": label,
                    "pattern_regex": pattern,
                    "pattern_normalized": pattern,
                    "pattern_compact": re.sub(r"\\s\*", "", pattern),
                    "pattern_version": "1.0.0",
                    "is_active": True,
                    "include_rule": "institution answer unit only",
                    "exclude_rule": "question, negation, quotation, interrogative context",
                }
            )
    return rows


def behavior_hits(answer_id: str, text: str, *, answer_eligible: bool = True) -> list[dict[str, Any]]:
    if not answer_eligible:
        return []
    normalized = normalize_text(text)
    rows = []
    for code, _label, patterns in BEHAVIOR_LEXICON:
        for seq, pattern in enumerate(patterns, start=1):
            for match in re.finditer(pattern, normalized):
                left = max(0, match.start() - 40)
                right = min(len(normalized), match.end() + 40)
                context = normalized[left:right]
                suppressed = False
                reason = pd.NA
                if code in {"A1", "A2", "A3", "A4", "A5", "A6"} and NEGATION_RE.search(context):
                    suppressed, reason = True, "negation_context"
                elif QUOTE_RE.search(context):
                    suppressed, reason = True, "quoted_or_restated_question"
                elif "?" in normalized[max(0, match.start() - 20): min(len(normalized), match.end() + 20)]:
                    suppressed, reason = True, "interrogative_context"
                hit_id = f"BHIT_{short_hash(answer_id + code + str(match.start()) + pattern, 12)}"
                rows.append(
                    {
                        "behavior_hit_id": hit_id,
                        "answer_unit_id": answer_id,
                        "behavior_code": code,
                        "lexicon_pattern_id": f"LEX_{code}_{seq:03d}",
                        "char_start": match.start(),
                        "char_end": match.end(),
                        "span_text": match.group(0),
                        "context_text": context,
                        "match_variant": "normalized_regex",
                        "hit_confidence": 0.85 if not suppressed else 0.3,
                        "is_suppressed": suppressed,
                        "suppression_reason": reason,
                    }
                )
    return rows
