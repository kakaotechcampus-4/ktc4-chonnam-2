# -*- coding: utf-8 -*-
"""원본 프레임 라벨의 plate.bbox 종횡비/높이 분포를 전수 측정한다.

메모리 상수 설계 — 파일당 레코드를 쌓지 않고 고정 크기 히스토그램에만 누적한다.
(라벨 50만 건 × 튜플을 리스트로 들고 있던 이전 버전이 메모리 압박으로 중단됐다.)

사용:
    python plate_bbox.py            # 전수
    python plate_bbox.py --every 10 # 10건당 1건 샘플링 (빠른 확인용)
"""
import os, re, sys, json, argparse

ROOT = r"D:\자동차 차종-연식-번호판 인식용 영상\원본이미지\extracted\merged"
OUT_DIR = r"D:\자동차 차종-연식-번호판 인식용 영상\plate_format_review\data"

# ── 히스토그램 사양 (전부 고정 크기) ───────────────────────────────
AR_BIN, AR_MAX = 0.05, 12.0           # 종횡비 0~12, 0.05 간격 → 240 bin
PX_BIN, PX_MAX = 1.0, 600.0           # 픽셀 0~600, 1px 간격 → 600 bin
AR_N = int(AR_MAX / AR_BIN)
PX_N = int(PX_MAX / PX_BIN)

# plate.bbox 를 JSON 파싱 없이 뽑는다 (50만 건 × json.loads 는 CPU 낭비)
RE_PLATE = re.compile(
    rb'"plate"\s*:\s*\{\s*"bbox"\s*:\s*\[\s*\[\s*'
    rb'(-?[\d.eE+-]+)\s*,\s*(-?[\d.eE+-]+)\s*\]\s*,\s*\[\s*'
    rb'(-?[\d.eE+-]+)\s*,\s*(-?[\d.eE+-]+)\s*\]')


class Hist:
    """분위수를 낼 수 있는 고정 크기 히스토그램."""
    __slots__ = ('bin', 'n_bins', 'counts', 'over', 'n', 'total')

    def __init__(self, binsize, n_bins):
        self.bin = binsize
        self.n_bins = n_bins
        self.counts = [0] * n_bins
        self.over = 0
        self.n = 0
        self.total = 0.0

    def add(self, v):
        self.n += 1
        self.total += v
        i = int(v / self.bin)
        if 0 <= i < self.n_bins:
            self.counts[i] += 1
        else:
            self.over += 1

    def pct(self, p):
        """p 분위수 (bin 내 선형보간). 값이 없으면 None."""
        if self.n == 0:
            return None
        target = p * self.n
        acc = 0
        for i, c in enumerate(self.counts):
            if c and acc + c >= target:
                frac = (target - acc) / c
                return round((i + frac) * self.bin, 3)
            acc += c
        return round(self.n_bins * self.bin, 3)

    def frac_below(self, v):
        if self.n == 0:
            return None
        i = int(v / self.bin)
        return round(sum(self.counts[:i]) / self.n, 4)

    def mean(self):
        return round(self.total / self.n, 3) if self.n else None

    def peaks(self, smooth=3, min_share=0.02):
        """이봉 여부 확인용 — 이동평균 후 국소최대 bin 을 돌려준다."""
        c = self.counts
        s = [sum(c[max(0, i - smooth):i + smooth + 1]) for i in range(len(c))]
        out = []
        for i in range(1, len(s) - 1):
            if s[i] > s[i - 1] and s[i] >= s[i + 1] and s[i] >= min_share * self.n:
                out.append({'center': round((i + 0.5) * self.bin, 2), 'share': round(s[i] / self.n, 4)})
        out.sort(key=lambda d: -d['share'])
        return out[:5]

    def dump(self):
        return {'n': self.n, 'mean': self.mean(), 'over_range': self.over,
                'p05': self.pct(.05), 'p10': self.pct(.10), 'p25': self.pct(.25),
                'p50': self.pct(.50), 'p75': self.pct(.75), 'p90': self.pct(.90),
                'p95': self.pct(.95)}


def iter_json(root):
    """os.walk 가 디렉터리마다 리스트를 만드는 것도 피한다 — scandir 재귀."""
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    elif e.name.endswith('.json'):
                        yield e.path
                except OSError:
                    continue


def vtype_of(path):
    rel = os.path.relpath(path, ROOT)
    i = rel.find(os.sep)
    return rel[:i] if i > 0 else '?'


def build(ar_all, h_all, w_all, per, seen, read, noplate, bad, every, partial):
    return {
        'root': ROOT,
        'partial': partial,
        'sampling_every': every,
        'n_json_seen': seen,
        'n_plate_bbox': read,
        'n_no_plate_bbox': noplate,
        'n_unreadable': bad,
        'bin': {'aspect_ratio': AR_BIN, 'pixel': PX_BIN},
        'aspect_ratio': ar_all.dump(),
        'plate_px_height': h_all.dump(),
        'plate_px_width': w_all.dump(),
        'aspect_ratio_peaks': ar_all.peaks(),
        'share_ar_below_3.0': ar_all.frac_below(3.0),
        'share_ar_below_3.5': ar_all.frac_below(3.5),
        'share_px_height_below_20': h_all.frac_below(20),
        'share_px_height_below_40': h_all.frac_below(40),
        'aspect_ratio_hist': {round(i * AR_BIN, 2): c for i, c in enumerate(ar_all.counts) if c},
        'by_vtype': {
            vt: {'n': a.n, 'ar_p10': a.pct(.10), 'ar_p50': a.pct(.50), 'ar_p90': a.pct(.90),
                 'ar_below_3.0': a.frac_below(3.0), 'h_p10': hh.pct(.10), 'h_p50': hh.pct(.50)}
            for vt, (a, hh) in sorted(per.items(), key=lambda kv: -kv[1][0].n)
        },
    }


def save(out):
    """중간 저장. 중단돼도 읽은 만큼은 남도록 임시파일→교체로 원자적으로 쓴다."""
    os.makedirs(OUT_DIR, exist_ok=True)
    dst = os.path.join(OUT_DIR, 'plate_bbox.json')
    tmp = dst + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, dst)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--every', type=int, default=1, help='N건당 1건만 읽는다 (기본 1=전수)')
    ap.add_argument('--progress', type=int, default=25000)
    ap.add_argument('--checkpoint', type=int, default=25000,
                    help='N건마다 중간 결과를 저장한다 (0=끄기)')
    args = ap.parse_args()

    ar_all = Hist(AR_BIN, AR_N)
    h_all = Hist(PX_BIN, PX_N)
    w_all = Hist(PX_BIN, PX_N)
    per = {}                      # vtype -> (Hist ar, Hist h)  · 차종 11종뿐

    seen = read = noplate = bad = 0
    for p in iter_json(ROOT):
        seen += 1
        if args.every > 1 and seen % args.every:
            continue
        try:
            with open(p, 'rb') as f:
                blob = f.read()
        except OSError:
            bad += 1
            continue
        m = RE_PLATE.search(blob)
        if not m:
            # 키 순서가 다른 경우에만 정식 파싱으로 되짚는다
            try:
                j = json.loads(blob.decode('utf-8'))
                b = (j.get('plate') or {}).get('bbox')
                if not b:
                    noplate += 1
                    continue
                (x1, y1), (x2, y2) = b
            except Exception:
                bad += 1
                continue
        else:
            x1, y1, x2, y2 = (float(v) for v in m.groups())
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        if w <= 0 or h <= 0:
            noplate += 1
            continue
        read += 1
        ar = w / h
        ar_all.add(ar); h_all.add(h); w_all.add(w)
        vt = vtype_of(p)
        e = per.get(vt)
        if e is None:
            e = per[vt] = (Hist(AR_BIN, AR_N), Hist(PX_BIN, PX_N))
        e[0].add(ar); e[1].add(h)

        if args.progress and read % args.progress == 0:
            print('  ... %d/%d 읽음' % (read, seen), file=sys.stderr, flush=True)
        if args.checkpoint and read % args.checkpoint == 0:
            save(build(ar_all, h_all, w_all, per, seen, read, noplate, bad, args.every, True))

    out = build(ar_all, h_all, w_all, per, seen, read, noplate, bad, args.every, False)
    dst = save(out)

    print('JSON %d건 중 plate.bbox %d건 (없음 %d · 불가 %d)' % (seen, read, noplate, bad))
    print('종횡비  p10=%s  p50=%s  p90=%s   (3.0 미만 비율 %s)' %
          (out['aspect_ratio']['p10'], out['aspect_ratio']['p50'],
           out['aspect_ratio']['p90'], out['share_ar_below_3.0']))
    print('번호판 높이(px)  p10=%s  p50=%s  p90=%s' %
          (out['plate_px_height']['p10'], out['plate_px_height']['p50'], out['plate_px_height']['p90']))
    print('종횡비 봉우리:', out['aspect_ratio_peaks'])
    print('->', dst)


if __name__ == '__main__':
    main()
