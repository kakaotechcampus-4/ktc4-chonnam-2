"""AI Hub 71555(교통법규 위반 상황) Validation 라벨 읽기 — 트랙 ① 실험 설계용.

**압축을 풀지 않는다.** 원천 51GB·라벨 258MB를 `zipfile`로 직접 읽는다. 푸는 순간
디스크가 감당하지 못하고, 어차피 필요한 것은 라벨 JSON과 표본 몇 장뿐이다.

이 스크립트가 재는 것은 **대상차량(트랙 ①)** 이다. 이 데이터셋에는 번호판 bbox가 없으므로
(`datasets-inventory-2026-09-18.md` §추가확인) 번호판 검출 실험에는 쓰지 않는다.

    python scripts/aihub71555_labels.py probe            # 스키마부터 확인한다
    python scripts/aihub71555_labels.py stats
    python scripts/aihub71555_labels.py sample --n 200 --seed 20260919

`probe`를 먼저 돌린다. 아래 파서는 인벤토리에 적힌 스키마를 전제하는데 그 기록은 표본
6,000건에서 나온 것이라, 전수에서도 같은 모양인지 확인하지 않고 통계를 내면 조용히 틀린
수치가 나온다.
"""
from __future__ import annotations

import argparse
import collections
import json
import posixpath
import random
import statistics
import sys
import zipfile
from pathlib import Path

# 데이터 위치 — 원천과 라벨이 나란히 있다고 본다.
ROOT = Path(r"D:\228.교통법규 위반 상황 데이터\01-1.정식개방데이터\Validation")
SRC_ZIP = ROOT / "01.원천데이터" / "VS.zip"
LABEL_ZIP = ROOT / "02.라벨링데이터" / "VL.zip"


def open_zip(path: Path) -> zipfile.ZipFile:
    if not path.exists():
        sys.exit(f"없다: {path}\n  (라벨을 아직 안 받았다면 VL.zip을 02.라벨링데이터/ 아래 둔다)")
    return zipfile.ZipFile(path)


def label_names(zl: zipfile.ZipFile) -> list[str]:
    """라벨 경로 목록. zip 전 엔트리에 UTF-8 플래그가 켜져 있어 한글이 그대로 나온다."""
    return [n for n in zl.namelist() if n.lower().endswith(".json")]


def load(zl: zipfile.ZipFile, name: str) -> dict:
    return json.loads(zl.read(name).decode("utf-8-sig"))


def annotations_of(label: dict) -> list:
    return label.get("Annotation", {}).get("annotations", [])


def bbox_of(ann: dict):
    """`Bbox Cordinate`(원본 철자)를 (x, y, w, h)로. 없으면 None.

    값은 `[x1, y1, x2, y2]` xyxy다. 계약이 xywh 하나로 고정돼 있어 여기서 바꾼다
    (`contract-plate-overlay-readout.md` §4 — 변환은 경계에서 끝낸다).
    `Polyline`·`Polygon` 주석에는 이 키가 없고, 그건 차선·횡단보도라 대상이 아니다.
    """
    box = ann.get("Bbox Cordinate")
    if not (isinstance(box, list) and len(box) == 4):
        return None
    x1, y1, x2, y2 = box
    return (x1, y1, x2 - x1, y2 - y1)


def clip_of(decoded_path: str) -> str:
    """클립 폴더명. `_01`~`_25`가 한 클립이라 프레임끼리 독립이 아니다."""
    parts = [p for p in posixpath.normpath(decoded_path).split("/") if p]
    return parts[2] if len(parts) > 2 else "(없음)"


def case_of(decoded_path: str) -> tuple[str, str]:
    """경로에서 (대분류, 세부유형)을 뽑는다.

    라벨 필드(`Meta.Traffic Case`)보다 폴더 구조가 안정적이라 이쪽을 1차로 쓴다 —
    `dataset_summary.json`의 분포도 폴더 기준으로 계산됐다.
    """
    parts = [p for p in posixpath.normpath(decoded_path).split("/") if p]
    major = parts[0] if parts else "(없음)"
    minor = parts[1] if len(parts) > 1 else "(없음)"
    return major, minor


# ── 명령 ──

def cmd_probe(args) -> None:
    """통계를 내기 전에 스키마를 눈으로 확인한다."""
    zl = open_zip(LABEL_ZIP)
    names = label_names(zl)
    print(f"라벨 JSON {len(names):,}건\n")

    for decoded in names[: args.n]:
        label = load(zl, decoded)
        print("=" * 70)
        print(decoded)
        print(f"  최상위 키: {list(label)}")
        for key in ("Meta", "condition", "Annotation"):
            block = label.get(key)
            if isinstance(block, dict):
                print(f"  {key}: {list(block)}")
        anns = annotations_of(label)
        print(f"  annotations: {len(anns)}건")
        for ann in anns[:3]:
            kind = ann.get("Annotation Type")
            print(f"     {ann.get('Object Name')!r} type={kind!r} bbox={bbox_of(ann)}")
            print(f"        키: {list(ann)}")

    print("\n" + "=" * 70)
    print("위 출력이 인벤토리 기록과 맞는지 확인하고 stats 로 넘어간다.")
    print("어긋나면 이 파일의 annotations_of / bbox_of 를 먼저 고친다.")


def cmd_stats(args) -> None:
    zl = open_zip(LABEL_ZIP)
    names = label_names(zl)
    if args.limit:
        names = names[: args.limit]

    per_case = collections.Counter()
    per_object = collections.Counter()
    per_cond = collections.defaultdict(collections.Counter)
    heights, widths = [], []
    no_ann = unreadable = degenerate = 0

    for i, decoded in enumerate(names, 1):
        if i % 20000 == 0:
            print(f"  … {i:,}/{len(names):,}", file=sys.stderr)
        try:
            label = load(zl, decoded)
        except Exception:
            unreadable += 1
            continue

        major, minor = case_of(decoded)
        per_case[(major, minor)] += 1

        cond = label.get("condition") if isinstance(label.get("condition"), dict) else {}
        for field in ("Weather", "DayNights", "roadType"):
            per_cond[field][cond.get(field, "(없음)")] += 1

        anns = annotations_of(label)
        if not anns:
            no_ann += 1
        for ann in anns:
            name = ann.get("Object Name")
            if name:
                per_object[name] += 1
            box = bbox_of(ann)
            # 위반 차량 크기 분포만 본다 — 트랙 ① 표본 추출의 난이도 축이다.
            # 25건은 점으로 찍힌 불량 박스(w나 h가 0)라 분포에서 뺀다.
            if box and name and "위반 차량" in name:
                if box[2] > 0 and box[3] > 0:
                    widths.append(box[2])
                    heights.append(box[3])
                else:
                    degenerate += 1

    print(f"\n라벨 {len(names):,}건 · 읽기 실패 {unreadable} · annotations 없음 {no_ann}\n")

    print("── 위반 유형 (폴더 기준)")
    for (major, minor), n in sorted(per_case.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>7,}  {major} / {minor}")

    print("\n── Object Name")
    for name, n in per_object.most_common():
        print(f"  {n:>7,}  {name}")

    for field, counter in per_cond.items():
        print(f"\n── {field}")
        for value, n in counter.most_common(8):
            print(f"  {n:>7,}  {value}")

    if heights:
        qs = statistics.quantiles(heights, n=10)
        print(f"\n── 위반 차량 bbox 높이 ({len(heights):,}건)")
        print(f"  p10 {qs[0]:.0f}  중앙 {statistics.median(heights):.0f}  p90 {qs[-1]:.0f}"
              f"  최소 {min(heights):.0f}  최대 {max(heights):.0f}")
        print(f"  너비 중앙 {statistics.median(widths):.0f}  ·  불량(점) 박스 {degenerate}건 제외")
        print("  ※ 번호판은 차량 높이의 8% 안팎으로 추정된다 — 판독용이 아니라 검출·추적용 데이터다")


def cmd_sample(args) -> None:
    """(대분류, 세부유형, 주야간)으로 층화 추출하고 manifest를 남긴다."""
    zl = open_zip(LABEL_ZIP)
    names = label_names(zl)

    buckets = collections.defaultdict(list)
    for decoded in names:
        major, minor = case_of(decoded)
        try:
            cond = load(zl, decoded).get("condition") or {}
        except Exception:
            continue
        buckets[(major, minor, cond.get("DayNights", "(없음)"))].append(decoded)

    rng = random.Random(args.seed)
    picked = []
    # 층마다 균등하게 뽑는다 — 안전모미착용이 1,522장뿐이라 비례추출하면 거의 사라진다.
    per_bucket = max(1, args.n // max(1, len(buckets)))
    for key in sorted(buckets):
        pool = sorted(buckets[key])
        rng.shuffle(pool)
        for decoded in pool[:per_bucket]:
            picked.append({"label_entry": decoded, "clip": clip_of(decoded),
                           "major": key[0], "minor": key[1], "daynight": key[2],
                           "image_entry": decoded[:-5] + ".jpg"})

    out = Path(args.out)
    out.write_text(json.dumps({
        "dataset": "AI Hub 71555 교통법규 위반 상황 · Validation",
        "source_zip": str(SRC_ZIP), "label_zip": str(LABEL_ZIP),
        "seed": args.seed, "requested": args.n,
        "bucket_count": len(buckets), "per_bucket": per_bucket,
        "picked": len(picked), "distinct_clips": len({i["clip"] for i in picked}),
        "items": picked,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"층 {len(buckets)}개 · 층당 {per_bucket}장 · 총 {len(picked)}장 → {out}")
    by_major = collections.Counter(item["major"] for item in picked)
    for major, n in by_major.most_common():
        print(f"  {n:>4}  {major}")

    # 한 클립이 25프레임이라 같은 층에서 같은 클립이 여러 번 뽑힌다. 프레임 수가 곧
    # 독립 표본 수가 아니므로, 층별 서로 다른 클립 수를 같이 남긴다.
    print(f"\n서로 다른 클립 {len({item['clip'] for item in picked}):,}개 "
          f"(프레임 {len(picked):,}장 — 프레임은 독립 표본이 아니다)")
    for key in sorted(buckets):
        sel = [i for i in picked if (i["major"], i["minor"], i["daynight"]) == key]
        if sel:
            print(f"  프레임 {len(sel):>4} · 클립 {len({i['clip'] for i in sel}):>4}   "
                  f"{key[0]} / {key[1]} / {key[2]}")
    print("\n이미지는 아직 꺼내지 않았다. manifest의 image_entry 로 VS.zip 에서 그때 읽는다.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="라벨 스키마를 눈으로 확인한다 (먼저 돌린다)")
    p.add_argument("--n", type=int, default=3)
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("stats", help="클래스·조건·bbox 분포")
    p.add_argument("--limit", type=int, default=0, help="앞에서 N건만 (빠른 확인용)")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("sample", help="층화 표본 manifest 생성")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--seed", type=int, default=20260919)
    p.add_argument("--out", default="track1-sample.json")
    p.set_defaults(func=cmd_sample)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
