# -*- coding: utf-8 -*-
"""이 실험의 JSON 산출물을 만든다.

입력: values.json (AI Hub 라벨 전수 스캔 결과 — 레포에 넣지 않는다, README 참조)
출력: <OUT>/*.json
"""
import json, os, re, sys, collections
from rules import (classify, notes, USE_PRIVATE, USE_BIZ, USE_RENT, USE_MOTO,
                   USE_MIL, SIDO, BAND2, BAND3, norm)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'data')
os.makedirs(OUT, exist_ok=True)
vals = json.load(open(os.path.join(HERE, 'values.json'), encoding='utf-8'))
TOTAL = sum(vals.values())

S = 9999
NSIDO = len(SIDO)
NSGG = 229
GOSI = 'gosi-2025-121'          # PR #88 공식 조사
OBSV = 'aihub-observed'         # 고시 범위 밖 · 관측 기반


def dump(name, obj):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('  %-28s %d bytes' % (name, os.path.getsize(os.path.join(OUT, name))))


# ══ 관측 집계 ═════════════════════════════════════════════════════
obs = collections.Counter(); obs_u = collections.Counter()
rej = collections.Counter(); rej_ex = collections.defaultdict(list)
note_c = collections.Counter(); note_ex = collections.defaultdict(list)
use_cnt = collections.Counter(); sido_cnt = collections.Counter()
head2 = set(); head3 = set()
moto_use = collections.Counter(); moto_sgg = collections.Counter()
shapes = collections.Counter(); shape_ex = {}

for s, n in vals.items():
    fid, rc = classify(s)
    if rc is None and fid:
        obs[fid] += n; obs_u[fid] += 1
        for c in notes(s):
            note_c[c] += n
            if len(note_ex[c]) < 8: note_ex[c].append(s)
    else:
        rej[rc] += n
        if len(rej_ex[rc]) < 10: rej_ex[rc].append(s)
    t = norm(s)
    m = re.search(r'([가-힣])(?=\d{4}$)', t)
    if m: use_cnt[m.group(1)] += n
    m = re.match(r'^영?(' + '|'.join(SIDO) + r')', t)
    if m: sido_cnt[m.group(1)] += n
    m = re.fullmatch(r'(\d{2})[가-힣]\d{4}', t)
    if m: head2.add(int(m.group(1)))
    m = re.fullmatch(r'(\d{3})[가-힣]\d{4}', t)
    if m and rc is None: head3.add(int(m.group(1)))
    if fid == 'MOTO' and rc is None:
        m = re.fullmatch(r'(' + '|'.join(SIDO) + r')([가-힣]{1,4})([가-힣])\d{4}', t)
        if m: moto_sgg[m.group(1) + ' ' + m.group(2)] += n; moto_use[m.group(3)] += n
    sh = ''.join(('D' if ch.isdigit() else 'H' if '가' <= ch <= '힣'
                  else '_' if ch == ' ' else '?') for ch in s)
    sh = re.sub(r'(.)\1*', lambda mo: mo.group(1) + str(len(mo.group(0))), sh)
    shapes[sh] += n
    shape_ex.setdefault(sh, []).append(s)

# ══ 1. 형식 카탈로그 ══════════════════════════════════════════════
def F(**kw): return kw

CATALOG = [
 F(format_id='NAT2_PRIVATE', category='승용·승합·화물·특수 / 비사업용',
   scheme='전국형 2자리 · 7자리 페인트방식 (2004.1~)', lines='1 또는 2',
   plate_color='분홍빛 흰색/보라빛 검정(페인트) · 흰색/검정(필름)', region_mark=None,
   head='2자리 01~99 (승용 01~69 · 승합 70~79 · 화물 80~97 · 특수 98~99)',
   use_codes=USE_PRIVATE, serial='0001~9999',
   regex=r'^\d{2}[' + ''.join(USE_PRIVATE) + r']\d{4}$', example='12가3456',
   combinations=99*32*S, source=GOSI, two_line_risk=False,
   note='정답지 최빈 형식. 2자리 분류기호는 고시 제5조제1항 단서와 관측이 일치'),
 F(format_id='NAT2_BIZ', category='자동차운수사업용 일반용',
   scheme='전국형 2자리 (일반사업용은 2자리 유지)', lines='1 또는 2',
   plate_color='황색 바탕 / 검정 문자', region_mark=None, head='2자리 01~99',
   use_codes=USE_BIZ, serial='0001~9999', regex=r'^\d{2}[바사아자배]\d{4}$',
   example='70바1234', combinations=99*5*S, source=GOSI, two_line_risk=False,
   note='2004 전국번호판은 비사업용 대상이라 사업용은 관할기호형이 압도적'),
 F(format_id='NAT2_PARCEL', category='택배용 화물 (고시상 운수사업용 일반용의 일부)',
   scheme='전국형 2자리', lines='1 또는 2', plate_color='황색 바탕 / 검정 문자',
   region_mark=None, head='2자리 01~99', use_codes=['배'], serial='0001~9999',
   regex=r'^\d{2}배\d{4}$', example='80배1234', combinations=99*1*S,
   source=GOSI, two_line_risk=False,
   note='고시는 「배」를 운수사업용 5자에 함께 둔다. 정답지에서는 관할기호형으로만 관측'),
 F(format_id='NAT2_RENT', category='대여사업용(렌터카)', scheme='전국형 2자리',
   lines='1 또는 2', plate_color='비사업용과 동일', region_mark=None, head='2자리 01~99',
   use_codes=USE_RENT, serial='0001~9999', regex=r'^\d{2}[허하호]\d{4}$',
   example='12허3456', combinations=99*3*S, source=GOSI, two_line_risk=False, note=None),
 F(format_id='NAT3_PRIVATE', category='승용·승합·화물·특수 / 비사업용',
   scheme='전국형 3자리 · 8자리 필름부착방식 (승용 2019.9~ · 승합/화물/특수 2021 개편)',
   lines='1', plate_color='흰색 바탕 / 검정 문자(+홀로그램)', region_mark=None,
   head='3자리 — 승용 100~699 · 승합 700~799 · 화물 800~979 · 특수 980~997',
   use_codes=USE_PRIVATE, serial='0001~9999',
   regex=r'^(?:[1-6]\d{2}|7\d{2}|8\d{2}|9[0-8]\d)[' + ''.join(USE_PRIVATE) + r']\d{4}$',
   example='123가4567', combinations=898*32*S, source=GOSI, two_line_risk=False,
   note='정답지 관측은 100~399뿐(2020년 촬영분). 700~997은 규정에만 있고 데이터로 검증 불가'),
 F(format_id='NAT3_RENT', category='대여사업용(렌터카)', scheme='전국형 3자리', lines='1',
   plate_color='비사업용과 동일', region_mark=None,
   head='3자리 — 승용 100~699 · 승합 700~799', use_codes=USE_RENT, serial='0001~9999',
   regex=r'^[1-7]\d{2}[허하호]\d{4}$', example='123허4567', combinations=700*3*S,
   source=GOSI, two_line_risk=False,
   note='대여사업용은 승용·승합 구간에만 배정. 800 이상과 결합하면 consistency note'),
 F(format_id='NAT3_EMERGENCY', category='긴급자동차(경찰차·소방차)', scheme='전국형 3자리',
   lines='1', plate_color='차종별', region_mark=None, head='3자리 998~999',
   use_codes=USE_PRIVATE, serial='0001~9999',
   regex=r'^99[89][' + ''.join(USE_PRIVATE) + r']\d{4}$', example='998가1234',
   combinations=2*32*S, source=GOSI, two_line_risk=False,
   note='고시 제5조제1항에 있으나 정답지 관측 0건. 빼면 정상 번호판을 막는다'),
 F(format_id='NAT3_BIZ', category='(고시 미등재) 3자리 + 운수사업용 기호', scheme=None,
   lines='1', plate_color=None, region_mark=None, head='3자리', use_codes=USE_BIZ,
   serial='0001~9999', regex=r'^\d{3}[바사아자배]\d{4}$', example='107바7009',
   combinations=None, source='observed-only', two_line_risk=False,
   note='고시 제5조제1항에 3자리 사업용 구간이 없다. 관측 8건 · 표본 2건 육안 확인했으나 '
        '라벨 오기인지 결론 못 냄 → 거부하지 않고 consistency note'),
 F(format_id='REGION_PRIVATE', category='승용·승합·화물·특수 / 비사업용',
   scheme='관할기호형 2자리 (1996.1~2003.12)', lines='2 (윗줄=관할기호+2자리)',
   plate_color='녹색 계열(구형)', region_mark='관할관청 기호 2글자', head='2자리 01~99',
   use_codes=USE_PRIVATE, serial='0001~9999',
   regex='^(' + '|'.join(SIDO) + r')\d{2}[' + ''.join(USE_PRIVATE) + r']\d{4}$',
   example='경기32가8078', combinations=NSIDO*99*32*S, source=GOSI, two_line_risk=True,
   note='세종은 2012년 신설이라 이 체계 발급분에는 없다(조합수는 표기 가능 상한)'),
 F(format_id='REGION_BIZ', category='자동차운수사업용 일반용', scheme='관할기호형 2자리 (현행 유지)',
   lines='2', plate_color='황색 바탕 / 검정 문자', region_mark='관할관청 기호 2글자',
   head='2자리 01~99', use_codes=['바', '사', '아', '자'], serial='0001~9999',
   regex='^(' + '|'.join(SIDO) + r')\d{2}[바사아자]\d{4}$', example='경기37바1050',
   combinations=NSIDO*99*4*S, source=GOSI, two_line_risk=True,
   note='정답지 2위(28.5%). 2004 전국번호판이 비사업용만 대상이었다는 근거와 관측이 일치'),
 F(format_id='REGION_PARCEL', category='택배용 화물', scheme='관할기호형 2자리', lines='2',
   plate_color='황색 바탕 / 검정 문자', region_mark='관할관청 기호 2글자', head='2자리 01~99',
   use_codes=['배'], serial='0001~9999',
   regex='^(' + '|'.join(SIDO) + r')\d{2}배\d{4}$', example='경기83배1983',
   combinations=NSIDO*99*1*S, source=GOSI, two_line_risk=True, note=None),
 F(format_id='REGION_RENT', category='대여사업용(렌터카)', scheme='관할기호형 2자리', lines='2',
   plate_color='비사업용과 동일', region_mark='관할관청 기호 2글자', head='2자리 01~99',
   use_codes=USE_RENT, serial='0001~9999',
   regex='^(' + '|'.join(SIDO) + r')\d{2}[허하호]\d{4}$', example='서울12허3456',
   combinations=NSIDO*99*3*S, source=GOSI, two_line_risk=True, note=None),
 F(format_id='REGION_LEGACY1', category='구형 관할기호형 1자리',
   scheme='관할기호형 1자리 (1973.4~1995.12)', lines='2 (윗줄=관할기호+1자리)',
   plate_color='녹색 계열(구형)', region_mark='관할관청 기호 2글자', head='1자리 1~9',
   use_codes=sorted(set(USE_PRIVATE) | set(USE_BIZ) | set(USE_RENT)), serial='0001~9999',
   regex='^(' + '|'.join(SIDO) + r')\d[가-힣]\d{4}$', example='경기2무1344',
   combinations=NSIDO*9*40*S, source=OBSV, two_line_risk=True,
   note='현행 고시 범위 밖. 정답지 9건을 이미지로 확인해 실재 확인. '
        '허용하면 관할기호형의 「앞자리 1자 누락」 검출율이 0.21%로 떨어진다'),
 F(format_id='MOTO', category='이륜자동차(사용신고) — 구형 표기',
   scheme='시·군·구 표기형 (제2025-121호 개정 이전)', lines='2',
   plate_color='흰색 바탕 / 청색 문자', region_mark='관할기호 2글자 + 시·군·구 1~4글자',
   head=None, use_codes=sorted(USE_MOTO), serial='0001~9999',
   regex='^(' + '|'.join(SIDO) + r')[가-힣]{1,4}[가-힣]\d{4}$', example='경기부천사3177',
   combinations=NSGG*28*S, source=GOSI + '+' + OBSV, two_line_risk=True,
   note='용도기호 28자는 고시 근거, 표기 구조는 관측 근거. 정답지 관측 한글은 14자(고시 28자의 앞 절반)뿐이라 '
        '관측만으로 화이트리스트를 만들면 절반을 거부한다. 시·군·구 목록(약 229개)도 외부에서 넣어야 한다'),
 F(format_id='MOTO_2025', category='이륜자동차 — 제2025-121호 체계',
   scheme='차종기호 1자리 + 용도기호 2자리', lines='2', plate_color='개정문 별도 확인 필요',
   region_mark='제6조 개정으로 표시 방식 조정', head='차종기호 1~9',
   use_codes=['비사업용 기호 1자 + 숫자 1~9'], serial='0001~9999',
   regex=None, example=None, combinations=None, source=GOSI, two_line_risk=True,
   note='정답지 관측 0건 — 2020년 촬영 데이터라 담길 수 없다. 규칙에 넣되 데이터 검증 불가. '
        '정규식은 개정문 별표 확인 후 확정'),
 F(format_id='CONSTR_BIZ', category='건설기계 / 영업용',
   scheme='건설기계 등록번호표 (건설기계관리법 소관)', lines='2', plate_color='주황색 계열',
   region_mark='「영」 + 관할기호 2글자',
   head='기종번호 2자리 01~27 (06 덤프트럭 · 14 콘크리트믹서트럭 · 15 콘크리트펌프)',
   use_codes=['한글 1자'], serial='5001~9999 (영업용 구간)',
   regex='^영(' + '|'.join(SIDO) + r')(0[1-9]|1\d|2[0-7])[가-힣]\d{4}$',
   example='영경기14모8138', combinations=NSIDO*27*14*4999, source=OBSV, two_line_risk=True,
   note='공식 조사(자동차 등록번호판 고시) 범위 밖 — 근거 법령이 다르다. 정답지 58건 전부 일련번호 ≥5001. '
        '「영」은 번호 일부가 아니라 용도 표기인데 라벨러가 함께 적었다'),
 F(format_id='CONSTR_PRIVATE', category='건설기계 / 자가용·관용', scheme='건설기계 등록번호표',
   lines='2', plate_color='주황색 계열', region_mark='관할기호 2글자',
   head='기종번호 2자리 01~27', use_codes=['한글 1자'], serial='1001~4999',
   regex='^(' + '|'.join(SIDO) + r')(0[1-9]|1\d|2[0-7])[가-힣]\d{4}$', example='서울06가1234',
   combinations=NSIDO*27*14*3999, source=OBSV, two_line_risk=True,
   note='관할기호형 자동차 번호판과 문자열이 완전히 겹친다 — 문자열만으로 구분 불가(색상 필요). 정답지 관측 0건'),
 F(format_id='MIL', category='군용', scheme='군용 등록번호판 (별도 법령)', lines='1',
   plate_color='흰색 계열', region_mark=None, head='2자리 01~99',
   use_codes=sorted(USE_MIL), serial='0001~9999', regex=r'^\d{2}[국합육해공]\d{4}$',
   example='16육2331', combinations=99*5*S, source=OBSV, two_line_risk=False,
   note='공식 조사 범위 밖. 정답지 16건 관측. 용도기호가 자동차 40자 밖이라 등재하지 않으면 거부된다'),
 F(format_id='DIPLO', category='외교용·영사용 등', scheme='외교 번호판', lines='1',
   plate_color='감청색 바탕 / 흰색 문자', region_mark=None, head='공관코드 3자리',
   use_codes=['외교', '영사', '준외', '준영', '국기', '대표', '협정'], serial='3자리',
   regex=r'^(외교|영사|준외|준영|국기|대표|협정)\d{3}\d{3}$', example='외교123456',
   combinations=7*999*999, source=GOSI, two_line_risk=False,
   note='정답지 관측 0건. ADR-EVIDENCE-006 §4-7에 따라 거부하지 말고 undetermined/review 경로'),
 F(format_id='TEMP', category='임시운행허가번호판', scheme='임시번호판', lines='1',
   plate_color='흰색 바탕 / 검정 문자 + 적색 사선', region_mark='기관명', head='2~3자리',
   use_codes=['임시'], serial='4자리', regex=None, example='서울06임1234',
   combinations=None, source=GOSI, two_line_risk=False,
   note='고시가 번호판 종류로 규정. 서식 고정 안 됨 → 정규식 검사 제외, review 경로'),
 F(format_id='EV', category='전기자동차번호판', scheme='문자 배열은 위 형식과 동일 · 색상만 다름',
   lines='형식에 따름', plate_color='파란색 바탕 / 검정 문자', region_mark='형식에 따름',
   head='형식에 따름', use_codes=['형식에 따름'], serial='형식에 따름',
   regex=None, example='123가4567 (파란 바탕)', combinations=None, source=GOSI,
   two_line_risk=False,
   note='고시가 번호판 종류로 따로 규정하지만 문자열 규칙은 같다. 2021 개편에서 별표18 전기차는 '
        '2자리 분류기호를 유지 — 색상 신호가 없으면 3자리/2자리 구분에 반영할 수 없다'),
]
for r in CATALOG:
    n = obs.get(r['format_id'], 0)
    r['observed_count'] = n
    r['observed_unique'] = obs_u.get(r['format_id'], 0)
    r['observed_ratio_pct'] = round(100 * n / TOTAL, 4)
    r['data_verified'] = bool(n)

print('산출:')
dump('plate-format-catalog.json', {
    'schema': 'plate-format-catalog/v1',
    'as_of': '2026-09-19',
    'notice': '국토교통부고시 제2025-121호 (시행 2025-03-15) 기준. 제2025-676호(2026-11-28 시행)는 미반영',
    'sources': {GOSI: 'PR #88 docs/modules/evidence/research/대한민국 자동차 등록번호판 형식 및 분류기호 조사.md',
                OBSV: 'AI Hub 자동차 차종·연식·번호판 인식용 영상 — 번호판 OCR 라벨 90,000건 관측',
                'observed-only': '관측되나 고시 근거를 찾지 못함'},
    'dataset': {'labels': TOTAL, 'unique_values': len(vals),
                'captured': '2020-09 (파일명 기준)'},
    'totals': {'formats': len(CATALOG),
               'combinations': sum(r['combinations'] or 0 for r in CATALOG),
               'observed': sum(obs.values()), 'unobserved_formats':
               [r['format_id'] for r in CATALOG if not r['observed_count']]},
    'formats': CATALOG,
})

# ══ 2. 용도기호 사전 ══════════════════════════════════════════════
dump('use-codes.json', {
    'schema': 'plate-use-codes/v1',
    'groups': [
        {'group': '비사업용 자가용·관용', 'source': GOSI, 'ref': '고시 제5조제1항',
         'codes': [{'code': c, 'observed': use_cnt.get(c, 0)} for c in USE_PRIVATE]},
        {'group': '자동차운수사업용 일반용', 'source': GOSI, 'ref': '고시 제5조제1항',
         'codes': [{'code': c, 'observed': use_cnt.get(c, 0)} for c in USE_BIZ]},
        {'group': '대여사업용', 'source': GOSI, 'ref': '고시 제5조제1항',
         'codes': [{'code': c, 'observed': use_cnt.get(c, 0)} for c in USE_RENT]},
        {'group': '이륜자동차 (별표13·14·15)', 'source': GOSI, 'ref': '제2025-121호 개정문',
         'codes': [{'code': c, 'observed': moto_use.get(c, 0)} for c in sorted(USE_MOTO)]},
        {'group': '군용', 'source': OBSV, 'ref': None,
         'codes': [{'code': c, 'observed': use_cnt.get(c, 0)} for c in sorted(USE_MIL)]},
    ],
    'observed_not_in_any_list': {c: n for c, n in sorted(use_cnt.items(), key=lambda x: -x[1])
                                 if c not in (set(USE_PRIVATE) | set(USE_BIZ) | set(USE_RENT)
                                              | USE_MOTO | USE_MIL)},
    'car_whitelist_size': len(set(USE_PRIVATE) | set(USE_BIZ) | set(USE_RENT)),
})

# ══ 3. 고시 ↔ 관측 대조 ═══════════════════════════════════════════
obs_moto = sorted(c for c in USE_MOTO if moto_use.get(c))
miss_sido = [s for s in SIDO if not sido_cnt.get(s)]
region_biz = obs['REGION_BIZ'] + obs['REGION_PARCEL']
region_other = obs['REGION_PRIVATE'] + obs['REGION_RENT'] + obs['REGION_LEGACY1']


def C(item, gosi, observed, verdict, impact):
    return {'item': item, 'gosi': gosi, 'observed': observed, 'verdict': verdict, 'impact': impact}


dump('gosi-vs-observed.json', {
    'schema': 'gosi-vs-observed/v1',
    'legend': {'MATCH': '고시와 관측이 일치', 'PARTIAL': '관측이 고시의 부분집합',
               'MISMATCH': '관측이 고시 범위를 못 덮음 — 규칙을 관측으로 만들면 안 됨',
               'UNVERIFIED': '고시에만 있고 관측 0건', 'GAP': '관측에만 있고 공식 조사 범위 밖'},
    'items': [
     C('용도기호 · 비사업용', '32자 (가~마/거~저/고~조/구~주)',
       '32자 전부 관측 (%d건)' % sum(use_cnt.get(c, 0) for c in USE_PRIVATE), 'MATCH',
       '화이트리스트를 그대로 확정할 수 있다'),
     C('용도기호 · 운수사업용', '5자 (바·사·아·자·배)',
       '5자 전부 관측 (%d건)' % sum(use_cnt.get(c, 0) for c in USE_BIZ), 'MATCH',
       '초안은 「배」를 택배용으로 따로 뒀으나 고시는 운수사업용 5자에 포함 — 집합은 동일, 분류만 달랐다'),
     C('용도기호 · 대여사업용', '3자 (허·하·호)',
       '3자 전부 관측 (%d건)' % sum(use_cnt.get(c, 0) for c in USE_RENT), 'MATCH', None),
     C('용도기호 · 자동차 합계', '40자 (32+5+3)', '유효 40자 + 미등재 3종(지·시·히)', 'MATCH',
       '독립적으로 얻은 두 목록이 완전히 겹친다. 미등재 3종은 라벨 오기로 확인'),
     C('관할관청 기호', '17개 광역 단위',
       '%d개 관측 (미관측: %s)' % (NSIDO - len(miss_sido), ' '.join(miss_sido)), 'PARTIAL',
       '데이터는 수도권 촬영분. 관측만으로 목록을 만들면 %s 차량을 거부한다' % ' '.join(miss_sido)),
     C('차종 분류기호 · 2자리', '01~69 승용 / 70~79 승합 / 80~97 화물 / 98~99 특수',
       '01~99 전 구간 관측 (%d종)' % len(head2), 'MATCH', '2자리 체계는 데이터로 전부 검증된다'),
     C('차종 분류기호 · 3자리', '100~699 승용 / 700~799 승합 / 800~979 화물 / 980~997 특수',
       '%d~%d 만 관측 (%d종)' % (min(head3), max(head3), len(head3)), 'MISMATCH',
       '데이터가 2020년 촬영이라 2021년 승합·화물·특수 3자리 개편이 없다. '
       '관측만으로 규칙을 만들면 700~997을 전부 거부한다'),
     C('긴급자동차', '998~999', '관측 0건', 'UNVERIFIED', '규정에만 있음. 규칙에 넣되 데이터 확인 불가'),
     C('이륜자동차 용도기호', '28자 (가~하 14 + 거~허 14)',
       '%d자 관측 (%s)' % (len(obs_moto), ''.join(obs_moto)), 'PARTIAL',
       '관측은 고시 28자의 앞 절반. 관측 기반 화이트리스트는 나머지 14자를 거부한다'),
     C('이륜자동차 체계', '제2025-121호 — 차종기호 1자리 + 용도기호 2자리',
       '구형 표기 %d건만 관측' % obs['MOTO'], 'MISMATCH', '신구 두 체계를 모두 등재해야 한다'),
     C('이륜 시·군·구 목록', '고시 제6조 · 전국 약 229개', '%d개만 관측' % len(moto_sgg), 'PARTIAL',
       '행정구역 목록을 외부에서 넣어야 한다'),
     C('2004 전국번호판 = 비사업용 대상', '운수사업용은 전국번호판 교부 대상이 아님(보도자료)',
       '관할기호형 중 사업용·택배 %d건 / 그 외 %d건 = %.2f%%' %
       (region_biz, region_other, 100 * region_biz / (region_biz + region_other)), 'MATCH',
       '제도 설계가 데이터 분포에 그대로 보인다 — 조사가 맞다는 강한 상호검증'),
     C('색상 · 운수사업용', '황색 바탕 / 검정 문자', '이미지 확인으로 일치 (PR #80 황색 2줄 사례 포함)',
       'MATCH', 'observation.value 에 색상이 없어 규칙이 쓸 수 없다'),
     C('전기자동차번호판', '파란색 바탕 / 별표18은 2자리 분류기호 유지', '색상 라벨 없음 — 관측 불가',
       'UNVERIFIED', '문자열만으로는 전기차 2자리와 일반 2자리를 구분할 수 없다'),
     C('외교용', '외교·영사·준외·준영·국기·대표·협정 + 3자리-3자리', '관측 0건', 'UNVERIFIED',
       'ADR-EVIDENCE-006 §4-7대로 review 경로'),
     C('임시운행허가번호판', '흰 바탕 + 적색 사선 / 서식 고정 안 됨', '관측 0건', 'UNVERIFIED',
       '정규식 검사 대상에서 제외'),
     C('건설기계 등록번호표', '공식 조사 범위 밖 (건설기계관리법 소관)',
       '%d건 관측 — 기종 06·14·15, 일련번호 전부 5001 이상' % obs['CONSTR_BIZ'], 'GAP',
       '자동차 고시만 보면 설명할 수 없다. 관할기호형 자동차와 문자열로 구분 불가'),
     C('군용 번호판', '공식 조사 범위 밖', '%d건 관측 (용도기호 「육」)' % obs['MIL'], 'GAP',
       '자동차 40자 밖이라 등재하지 않으면 정상 번호판이 거부된다'),
     C('구형 1자리 관할기호판', '현행 고시 범위 밖 (1973~1995 폐지 체계)',
       '%d건 관측 — 이미지로 실재 확인' % obs['REGION_LEGACY1'], 'GAP',
       '허용하면 관할기호형의 「앞자리 1자 누락」 검출율이 0.21%로 떨어진다'),
    ]})

# ══ 4. 전수 대조 결과 ═════════════════════════════════════════════
dump('rule-eval.json', {
    'schema': 'plate-rule-eval/v1',
    'dataset': {'labels': TOTAL, 'unique_values': len(vals),
                'train': 80000, 'valid': 10000},
    'passed': sum(obs.values()),
    'passed_ratio_pct': round(100 * sum(obs.values()) / TOTAL, 4),
    'by_format': dict(obs.most_common()),
    'by_format_unique': dict(obs_u),
    'unexplained': {'total': sum(rej.values()), 'by_reason': dict(rej),
                    'examples': dict(rej_ex),
                    'finding': '5건 전부 이미지 확인 결과 정답지 라벨 오기. '
                               '형식 규칙이 정상 번호판을 막은 사례 0건'},
    'consistency_notes': {'total': sum(note_c.values()), 'by_code': dict(note_c),
                          'examples': dict(note_ex)},
    'value_shapes': [{'shape': k, 'count': v, 'unique': len(shape_ex[k]),
                      'examples': sorted(shape_ex[k])[:4]}
                     for k, v in shapes.most_common()],
    'two_line_risk_population': {
        'count': sum(n for f, n in obs.items()
                     if f in ('REGION_PRIVATE', 'REGION_BIZ', 'REGION_RENT', 'REGION_PARCEL',
                              'REGION_LEGACY1', 'MOTO', 'CONSTR_BIZ')),
        'ratio_pct': round(100 * sum(n for f, n in obs.items()
                                     if f in ('REGION_PRIVATE', 'REGION_BIZ', 'REGION_RENT',
                                              'REGION_PARCEL', 'REGION_LEGACY1', 'MOTO',
                                              'CONSTR_BIZ')) / sum(obs.values()), 2),
        'basis': '형식으로부터 추정 — 정답지에 줄 수 라벨이 없다'},
})
print('완료:', OUT)
