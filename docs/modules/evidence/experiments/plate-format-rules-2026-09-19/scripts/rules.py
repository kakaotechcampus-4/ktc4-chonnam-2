# -*- coding: utf-8 -*-
"""한국 자동차 번호판 형식 규칙 엔진 + 정답 JSON 대조 측정.

값의 출처 (2026-09-19 개정)
  - 차종별 분류기호 범위 · 용도별 한글 기호 · 관할관청 기호 · 이륜차 용도기호
    → PR #88 `docs/modules/evidence/research/대한민국 자동차 등록번호판 형식 및 분류기호 조사.md`
      (국토교통부고시 제2025-121호 기준 공식 조사)
  - 구형 지역형 1자리 · 건설기계 · 군용
    → AI Hub 정답지 관측 (공식 조사 범위 밖)

판정 semantics 는 ADR-EVIDENCE-006 을 따른다 — 이 모듈은 hard VALID/INVALID gate 가 아니다.
  classify()  : 알려진 번호판 형식으로 **구조가 설명되는가** (설명 안 되면 reason_code)
  notes()     : 구조는 설명되지만 고시와 **어긋나는 조합** (soft, 값을 버리지 않음)
두 결과 모두 evidence 에서는 `needs_review=true` 로 귀결되고, 값 자체는 보존한다.
"""
import json, re, random, collections, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 용도별 한글 기호 — 고시 제5조제1항 (PR #88 §4) ──────────────────
USE_PRIVATE = list('가나다라마') + list('거너더러머버서어저') + list('고노도로모보소오조') + list('구누두루무부수우주')
USE_BIZ     = list('바사아자배')      # 자동차운수사업용 일반용 — 「배」가 여기 포함된다(고시 기준)
USE_RENT    = list('허하호')          # 대여사업용
USE_PARCEL  = list('배')              # 택배용 통칭. 고시상으로는 USE_BIZ 의 일부다
USE_ALL_CAR = set(USE_PRIVATE + USE_BIZ + USE_RENT)     # 40자 (32 + 5 + 3)

# ── 관할관청 기호 — 고시 제6조 (PR #88 §5) ─────────────────────────
SIDO = ['서울','부산','대구','인천','광주','대전','울산','세종','경기','강원','충북','충남','전북','전남','경북','경남','제주']
SIDO_SET = set(SIDO)

# ── 이륜자동차 용도기호 — 제2025-121호 개정문 별표13·14·15 (PR #88 §8) ──
USE_MOTO = set(list('가나다라마바사아자차카타파하') + list('거너더러머버서어저처커터퍼허'))   # 28자

# ── 공식 조사 범위 밖 (AI Hub 관측 기반) ───────────────────────────
USE_MIL = set(list('국합육해공'))     # 군용 번호판

# ── 차종별 분류기호 범위 — 고시 제5조제1항 (PR #88 §3) ─────────────
#    3자리(8자리 필름부착방식)                2자리(7자리 페인트방식·일반사업용 등)
BAND3 = [(100, 699, '승용'), (700, 799, '승합'), (800, 979, '화물'),
         (980, 997, '특수'), (998, 999, '긴급')]
BAND2 = [(1, 69, '승용'), (70, 79, '승합'), (80, 97, '화물'), (98, 99, '특수')]


def band(head, table):
    for lo, hi, name in table:
        if lo <= head <= hi:
            return name
    return None


def norm(s):
    """평가 전 정규화 — 공백/하이픈/점 제거."""
    return re.sub(r'[\s\-\.·]', '', s)


def classify(raw):
    """(format_id, reason_code) 반환. reason_code=None 이면 「형식으로 설명됨」."""
    s = norm(raw)
    # 1) 건설기계 영업용 (영 + 시도 + 기종2 + 한글 + 4) — 공식 조사 범위 밖
    m = re.fullmatch(r'영([가-힣]{2})(\d{2})([가-힣])(\d{4})', s)
    if m:
        if m.group(1) not in SIDO_SET: return 'CONSTR_BIZ', 'plate.format.region_unknown'
        if not (1 <= int(m.group(2)) <= 27): return 'CONSTR_BIZ', 'plate.format.head_out_of_range'
        if not (1 <= int(m.group(4)) <= 9999): return 'CONSTR_BIZ', 'plate.format.serial_out_of_range'
        return 'CONSTR_BIZ', None
    # 2) 지역형 자동차 (시도 + 2자리 + 한글 + 4)
    m = re.fullmatch(r'([가-힣]{2})(\d{2})([가-힣])(\d{4})', s)
    if m:
        reg, head, use, ser = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        if reg not in SIDO_SET: return 'REGION', 'plate.format.region_unknown'
        if use not in USE_ALL_CAR: return 'REGION', 'plate.format.use_code_unknown'
        if not (1 <= head <= 99): return 'REGION', 'plate.format.head_out_of_range'
        if not (1 <= ser <= 9999): return 'REGION', 'plate.format.serial_out_of_range'
        fid = ('REGION_PARCEL' if use == '배' else
               'REGION_BIZ' if use in USE_BIZ else
               'REGION_RENT' if use in USE_RENT else 'REGION_PRIVATE')
        return fid, None
    # 3) 구형 지역형 1자리 (1973.4~1995.12) — 공식 조사 범위 밖, 정답지 관측
    m = re.fullmatch(r'([가-힣]{2})(\d)([가-힣])(\d{4})', s)
    if m:
        if m.group(1) not in SIDO_SET: return 'REGION_LEGACY1', 'plate.format.region_unknown'
        if m.group(3) not in USE_ALL_CAR: return 'REGION_LEGACY1', 'plate.format.use_code_unknown'
        if not (1 <= int(m.group(4)) <= 9999): return 'REGION_LEGACY1', 'plate.format.serial_out_of_range'
        return 'REGION_LEGACY1', None
    # 4) 이륜차 (시도 + 시군구1~4 + 한글 + 4)
    m = re.fullmatch(r'([가-힣]{2})([가-힣]{1,4})([가-힣])(\d{4})', s)
    if m:
        if m.group(1) not in SIDO_SET: return 'MOTO', 'plate.format.region_unknown'
        if m.group(3) not in USE_MOTO: return 'MOTO', 'plate.format.use_code_unknown'
        if not (1 <= int(m.group(4)) <= 9999): return 'MOTO', 'plate.format.serial_out_of_range'
        return 'MOTO', None
    # 5) 전국형 3자리 (8자리 필름부착방식 · 2019.9~, 승합·화물·특수는 2021 개편)
    m = re.fullmatch(r'(\d{3})([가-힣])(\d{4})', s)
    if m:
        head, use, ser = int(m.group(1)), m.group(2), int(m.group(3))
        if use not in USE_ALL_CAR: return 'NAT3', 'plate.format.use_code_unknown'
        if band(head, BAND3) is None: return 'NAT3', 'plate.format.head_out_of_range'
        if not (1 <= ser <= 9999): return 'NAT3', 'plate.format.serial_out_of_range'
        fid = ('NAT3_BIZ' if use in USE_BIZ else
               'NAT3_RENT' if use in USE_RENT else 'NAT3_PRIVATE')
        return fid, None
    # 6) 군용 (2자리 + 국/합/육/해/공 + 4자리) — 공식 조사 범위 밖
    m = re.fullmatch(r'(\d{2})([가-힣])(\d{4})', s)
    if m and m.group(2) in USE_MIL:
        return 'MIL', None
    # 7) 전국형 2자리 (7자리 페인트방식 · 2004.1~)
    m = re.fullmatch(r'(\d{2})([가-힣])(\d{4})', s)
    if m:
        head, use, ser = int(m.group(1)), m.group(2), int(m.group(3))
        if use not in USE_ALL_CAR: return 'NAT2', 'plate.format.use_code_unknown'
        if not (1 <= head <= 99): return 'NAT2', 'plate.format.head_out_of_range'
        if not (1 <= ser <= 9999): return 'NAT2', 'plate.format.serial_out_of_range'
        fid = ('NAT2_PARCEL' if use == '배' else
               'NAT2_BIZ' if use in USE_BIZ else
               'NAT2_RENT' if use in USE_RENT else 'NAT2_PRIVATE')
        return fid, None
    # 8) 외교 (고시 제5조제1항 · 관측 0건)
    if re.fullmatch(r'(외교|영사|준외|준영|국기|대표|협정)\d{3}\d{3}', s): return 'DIPLO', None
    # 미일치 — 어느 조각이 없는지 진단
    has_head = bool(re.match(r'^[가-힣]{0,6}\d{1,3}', s))
    has_use  = bool(re.search(r'\d[가-힣]\d', s))
    has_ser  = bool(re.search(r'\d{4}$', s))
    if not has_head or not has_use or not has_ser:
        return None, 'plate.format.incomplete'
    return None, 'plate.format.unknown_shape'


def notes(raw):
    """구조는 설명되지만 고시와 어긋나는 조합. reason code 목록을 돌려준다.

    ADR-EVIDENCE-006 기준으로 이것들은 거부가 아니라 needs_review 신호다.
    """
    s = norm(raw)
    fid, rc = classify(s)
    out = []
    if rc is not None:
        return out
    m3 = re.fullmatch(r'(\d{3})([가-힣])(\d{4})', s)
    if m3:
        head, use = int(m3.group(1)), m3.group(2)
        b = band(head, BAND3)
        if use in USE_BIZ:
            # 고시 제5조제1항: 일반사업용은 2자리 분류기호다. 3자리 사업용은 등재돼 있지 않다
            out.append('plate.consistency.biz_with_3digit_band')
        if use in USE_RENT and b not in ('승용', '승합'):
            # 대여사업용은 승용 100-699 · 승합 700-799 에만 배정된다
            out.append('plate.consistency.rent_band_mismatch')
        if b == '긴급':
            out.append('plate.consistency.emergency_band')
    mc = re.fullmatch(r'영([가-힣]{2})(\d{2})([가-힣])(\d{4})', s)
    if mc and int(mc.group(4)) < 5001:
        # 건설기계 영업용 일련번호 구간(5001~9999) — 공식 조사 범위 밖, 관측 기반
        out.append('plate.consistency.constr_serial_band_mismatch')
    if fid in ('REGION_LEGACY1',):
        out.append('plate.consistency.legacy_scheme')
    if fid in ('CONSTR_BIZ', 'MIL'):
        out.append('plate.consistency.outside_notice_scope')
    return out


def is_two_line(fid):
    """해당 형식이 2줄 판으로 발급될 수 있는가 (윗줄 손실 위험군)."""
    return fid in ('REGION_PRIVATE', 'REGION_BIZ', 'REGION_RENT', 'REGION_PARCEL',
                   'REGION_LEGACY1', 'MOTO', 'CONSTR_BIZ')


if __name__ == '__main__':
    vals = json.load(open(os.path.join(HERE, 'values.json'), encoding='utf-8'))
    total = sum(vals.values())
    fmt = collections.Counter(); fmt_u = collections.Counter()
    rej = collections.Counter(); rej_ex = collections.defaultdict(list)
    note = collections.Counter(); note_ex = collections.defaultdict(list)
    normalized = 0
    for s, n in vals.items():
        if norm(s) != s: normalized += n
        fid, rc = classify(s)
        key = fid or 'UNMATCHED'
        if rc is None:
            fmt[key] += n; fmt_u[key] += 1
            for c in notes(s):
                note[c] += n
                if len(note_ex[c]) < 8: note_ex[c].append(s)
        else:
            rej[rc] += n
            if len(rej_ex[rc]) < 12: rej_ex[rc].append(s)
    print('총 라벨', total, '고유', len(vals))
    print('--- 형식으로 설명됨 ---')
    for k, n in fmt.most_common():
        print('  %-16s %7d (%5.2f%%)  고유 %6d' % (k, n, 100*n/total, fmt_u[k]))
    print('  합계 %d (%.3f%%)' % (sum(fmt.values()), 100*sum(fmt.values())/total))
    print('--- 설명 안 됨 (reason_code) ---')
    for k, n in rej.most_common():
        print('  %-34s %5d (%.4f%%)  예: %s' % (k, n, 100*n/total, ' '.join(rej_ex[k][:6])))
    print('--- 고시와 어긋나는 조합 (soft note) ---')
    for k, n in note.most_common():
        print('  %-44s %5d (%.4f%%)  예: %s' % (k, n, 100*n/total, ' '.join(note_ex[k][:5])))
    print('  정규화로 흡수된 건(공백/하이픈):', normalized)
    json.dump({'fmt': dict(fmt), 'fmt_u': dict(fmt_u), 'rej': dict(rej),
               'rej_ex': {k: v for k, v in rej_ex.items()},
               'note': dict(note), 'note_ex': {k: v for k, v in note_ex.items()},
               'total': total, 'unique': len(vals), 'normalized': normalized},
              open(os.path.join(HERE, 'rule_eval.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
