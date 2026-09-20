# -*- coding: utf-8 -*-
"""오독 유형별로 형식 규칙이 잡아내는 비율(검출력)을 측정한다."""
import json, re, os, random, collections
import rules
from rules import classify, norm, USE_ALL_CAR, is_two_line

HERE = os.path.dirname(os.path.abspath(__file__))
vals = json.load(open(os.path.join(HERE,'values.json'), encoding='utf-8'))
random.seed(11)

def ok(s):
    fid, rc = classify(s)
    return fid is not None and rc is None

# 정답 중 규칙 통과분만 대상으로
base = [(s, n, classify(s)[0]) for s, n in vals.items() if ok(s)]

def split(s):
    """(prefix_region, head_digits, use, serial) 로 쪼갠다. 안되면 None"""
    m = re.fullmatch(r'(영?)([가-힣]{0,6}?)(\d{1,3})([가-힣])(\d{4})', s)
    if m: return m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    return None

MUT = {}

def mut(name):
    def deco(f): MUT[name] = f; return f
    return deco

@mut('①윗줄전체누락(한글+일련번호만)')
def m1(s, p):
    if not p: return None
    return p[3] + p[4]

@mut('②지역명만누락')
def m2(s, p):
    if not p or not p[1]: return None
    return p[0] + p[2] + p[3] + p[4]

@mut('③앞자리 숫자 1자 누락')
def m3(s, p):
    if not p or len(p[2]) < 2: return None
    i = random.randrange(len(p[2]))
    return p[0] + p[1] + p[2][:i] + p[2][i+1:] + p[3] + p[4]

@mut('④용도기호(한글) 누락')
def m4(s, p):
    if not p: return None
    return p[0] + p[1] + p[2] + p[4]

@mut('⑤일련번호 1자 누락')
def m5(s, p):
    if not p: return None
    i = random.randrange(4)
    return p[0] + p[1] + p[2] + p[3] + p[4][:i] + p[4][i+1:]

@mut('⑥일련번호 1자 오독(숫자→숫자)')
def m6(s, p):
    if not p: return None
    i = random.randrange(4)
    c = random.choice([d for d in '0123456789' if d != p[4][i]])
    return p[0] + p[1] + p[2] + p[3] + p[4][:i] + c + p[4][i+1:]

@mut('⑦앞자리 1자 오독(숫자→숫자)')
def m7(s, p):
    if not p: return None
    i = random.randrange(len(p[2]))
    c = random.choice([d for d in '0123456789' if d != p[2][i]])
    return p[0] + p[1] + p[2][:i] + c + p[2][i+1:] + p[3] + p[4]

@mut('⑧용도기호 오독(한글→유효한글)')
def m8(s, p):
    if not p: return None
    c = random.choice([h for h in sorted(USE_ALL_CAR) if h != p[3]])
    return p[0] + p[1] + p[2] + c + p[4]

@mut('⑨숫자 1자 덧붙음(환각)')
def m9(s, p):
    if not p: return None
    return p[0] + p[1] + p[2] + p[3] + p[4] + random.choice('0123456789')

@mut('⑩숫자 자리에 한글 혼입')
def m10(s, p):
    if not p: return None
    i = random.randrange(4)
    return p[0] + p[1] + p[2] + p[3] + p[4][:i] + random.choice('가나다라마') + p[4][i+1:]

res = {}
for name, f in MUT.items():
    tot = det = na = 0
    tot2 = det2 = 0     # 2줄 위험군 한정
    ex_miss = []
    for s, n, fid in base:
        p = split(s)
        out = f(s, p)
        if out is None or out == s: na += n; continue
        caught = not ok(out)
        tot += n; det += n * caught
        if is_two_line(fid):
            tot2 += n; det2 += n * caught
        if not caught and len(ex_miss) < 5: ex_miss.append('%s→%s' % (s, out))
    res[name] = {'n': tot, 'detected': det, 'rate': round(100*det/tot, 2) if tot else None,
                 'n_2line': tot2, 'rate_2line': round(100*det2/tot2, 2) if tot2 else None,
                 'miss_ex': ex_miss}

print('%-34s %8s %8s %8s   %s' % ('오독 유형', '적용건수', '검출건수', '검출율', '미검출 예'))
for k in MUT:
    r = res[k]
    print('%-34s %8d %8d %7.2f%%   %s' % (k, r['n'], r['detected'], r['rate'], '  '.join(r['miss_ex'][:2])))
json.dump(res, open(os.path.join(HERE,'corrupt.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)

# 2줄 위험군 규모
tl = sum(n for s, n, fid in base if is_two_line(fid))
print('\n2줄 발급 가능 형식(지역형·이륜·건설기계) 라벨 수: %d / %d (%.2f%%)' % (tl, sum(n for _,n,_ in base), 100*tl/sum(n for _,n,_ in base)))
